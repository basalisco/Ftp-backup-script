import ftplib
import os
import sys
import threading
import time
import itertools
import getpass
from datetime import datetime
from queue import Queue
from tqdm import tqdm
import json

# Import per la crittografia
from cryptography.fernet import Fernet
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
from cryptography.hazmat.backends import default_backend
import base64

### --- CONFIGURAZIONE --- ###
BACKUP_FOLDER_PREFIX = "backup"
ENCRYPTED_CREDS_FILE = "credentials.enc"
PLAINTEXT_CREDS_FILE = "credentials.json"
####################################

STRINGS = {
    'it': {
        'APP_TITLE': "--- Utilità di Backup FTP ---",
        'PROMPT_LANG': "Scegli la lingua / Choose language (it/en): ",
        'PROMPT_HOST': "Inserisci l'host FTP (es. ftp.dominio.com): ",
        'PROMPT_USER': "Inserisci l'utente FTP: ",
        'PROMPT_PASS': "Inserisci la password FTP (non sarà visibile): ",
        'PROMPT_THREADS': "\nQuanti 'operai' (thread) vuoi usare? [Invio per 15]\n(Più thread = più velocità, ma più carico sul server): ",
        'PROMPT_DIRS': "\n👉 Inserisci i numeri delle cartelle (separati da virgola), oppure 'tutto': ",
        'PROMPT_USE_SAVED_ENC': "Trovate credenziali criptate. Vuoi usarle?",
        'PROMPT_USE_SAVED_PLAIN': "Trovate credenziali IN CHIARO non protette. Vuoi usarle?",
        'PROMPT_MASTER_PASS': "Inserisci la Master Password per decriptare: ",
        'PROMPT_SAVE_NEW': "\nVuoi salvare queste credenziali per futuri accessi?",
        'PROMPT_SAVE_HOW': "Come vuoi salvarle? [P]rotette (consigliato) / In [C]hiaro (non sicuro): ",
        'PROMPT_CREATE_MASTER_PASS': "Crea una Master Password per proteggere il file: ",
        'PROMPT_CONFIRM_MASTER_PASS': "Conferma la Master Password: ",
        'PROMPT_CONFIRM_PLAINTEXT': "ATTENZIONE! Stai per salvare la password in un file leggibile. Sei sicuro? (s/n): ",
        'STATUS_CONNECTING': "\n🔌 Connessione a {host}...",
        'OK_CONNECTED': "✅ Connessione FTP stabilita con successo.",
        'STATUS_SCANNING': "🔎 Scansione delle cartelle remote in corso...",
        'OK_SCAN_COMPLETE': "👍 Scansione completata.",
        'STATUS_DISCOVERING': " Analizzando file remoti (potrebbe volerci un po')... ",
        'LBL_AVAILABLE_DIRS': "\n--- Cartelle disponibili per il backup ---",
        'LBL_FILES_FOUND': "Trovati {count} file da scaricare.",
        'LBL_DOWNLOAD_START': "\nDownload dei file in corso...",
        'LBL_BACKUP_COMPLETE': "\n🎉 Backup completato!",
        'LBL_FILES_SAVED_TO': "I file sono stati salvati in: {path}",
        'LBL_DISCOVERY_SUMMARY': "Analisi completata: Trovati {file_count} file in {dir_count} cartelle.",
        'OK_DECRYPT': "Credenziali decriptate con successo!",
        'OK_SAVE': "Credenziali salvate e criptate con successo!",
        'OK_SAVE_PLAIN': "Credenziali salvate in chiaro nel file '{filename}'.",
        'ERR_CONNECTION': "❌ Errore di connessione: {e}",
        'ERR_SCAN_FAILED': "❌ Scansione cartelle fallita: {e}.",
        'ERR_NO_DIRS_FOUND': "Nessuna cartella trovata sul server o errore durante la scansione.",
        'ERR_INVALID_INPUT': "❌ Input non valido.",
        'ERR_INVALID_NUMBER': "Numero non valido, uso 15 thread.",
        'ERR_NOT_NUMERIC': "Input non numerico, uso 15 thread.",
        'ERR_DECRYPT_FAILED': "Master Password errata o file corrotto.",
        'ERR_PASS_MISMATCH': "Le password non coincidono. Riprova.",
        'ERR_EXPLORE_DIR': "⚠️ Impossibile esplorare {path}: {e}",
        'ERR_DOWNLOAD_FILE': "    ⚠️ Errore download '{filename}': {e}",
        'ERR_SYSTEM_SAVE': "    ⚠️ Errore di Sistema durante il salvataggio di '{filename}': {e}",
        'CHOICE_ALL': "tutto",
        'CHOICE_YES': 's',
        'CHOICE_PROTECTED': 'p',
        'CHOICE_PLAINTEXT': 'c',
        'BACKUP_PREFIX': "backup",
        'BACKUP_PART_FULL': "full-backup",
        'BACKUP_PART_MULTI': "multiple-dirs",
        'TQDM_TOTAL_BACKUP': "Backup Totale",
        'TQDM_FILE': "  -> {filename:<40}"
    },
    'en': {
        'APP_TITLE': "--- FTP Backup Utility ---",
        'PROMPT_LANG': "Scegli la lingua / Choose language (it/en): ",
        'PROMPT_HOST': "Enter FTP host (e.g., ftp.domain.com): ",
        'PROMPT_USER': "Enter FTP user: ",
        'PROMPT_PASS': "Enter FTP password (will not be visible): ",
        'PROMPT_THREADS': "\nHow many workers (threads) do you want to use? [Enter for 15]\n(More threads = more speed, but more server load): ",
        'PROMPT_DIRS': "\n👉 Enter folder numbers (comma-separated), or 'all': ",
        'PROMPT_USE_SAVED_ENC': "Encrypted credentials found. Do you want to use them?",
        'PROMPT_USE_SAVED_PLAIN': "Found UNPROTECTED plaintext credentials. Do you want to use them?",
        'PROMPT_MASTER_PASS': "Enter Master Password to decrypt: ",
        'PROMPT_SAVE_NEW': "\nDo you want to save these credentials for future use?",
        'PROMPT_SAVE_HOW': "How do you want to save them? [P]rotected (recommended) / [C]leartext (unsafe): ",
        'PROMPT_CREATE_MASTER_PASS': "Create a Master Password to protect the file: ",
        'PROMPT_CONFIRM_MASTER_PASS': "Confirm the Master Password: ",
        'PROMPT_CONFIRM_PLAINTEXT': "WARNING! You are about to save your password in a readable file. Are you sure? (y/n): ",
        'STATUS_CONNECTING': "\n🔌 Connecting to {host}...",
        'OK_CONNECTED': "✅ FTP connection established successfully.",
        'STATUS_SCANNING': "🔎 Scanning remote folders...",
        'OK_SCAN_COMPLETE': "👍 Scan complete.",
        'STATUS_DISCOVERING': " Analyzing remote files (this may take a while)... ",
        'LBL_AVAILABLE_DIRS': "\n--- Available folders for backup ---",
        'LBL_FILES_FOUND': "Found {count} files to download.",
        'LBL_DOWNLOAD_START': "\nDownloading files...",
        'LBL_BACKUP_COMPLETE': "\n🎉 Backup complete!",
        'LBL_FILES_SAVED_TO': "Files have been saved to: {path}",
        'LBL_DISCOVERY_SUMMARY': "Analysis complete: Found {file_count} files in {dir_count} folders.",
        'OK_DECRYPT': "Credentials decrypted successfully!",
        'OK_SAVE': "Credentials saved and encrypted successfully!",
        'OK_SAVE_PLAIN': "Credentials saved in plaintext to '{filename}'.",
        'ERR_CONNECTION': "❌ Connection error: {e}",
        'ERR_SCAN_FAILED': "❌ Folder scan failed: {e}.",
        'ERR_NO_DIRS_FOUND': "No folders found on server or scan error.",
        'ERR_INVALID_INPUT': "❌ Invalid input.",
        'ERR_INVALID_NUMBER': "Invalid number, using 15 threads.",
        'ERR_NOT_NUMERIC': "Non-numeric input, using 15 threads.",
        'ERR_DECRYPT_FAILED': "Wrong Master Password or corrupted file.",
        'ERR_PASS_MISMATCH': "Passwords do not match. Please try again.",
        'ERR_EXPLORE_DIR': "⚠️ Could not explore {path}: {e}",
        'ERR_DOWNLOAD_FILE': "    ⚠️ Error downloading '{filename}': {e}",
        'ERR_SYSTEM_SAVE': "    ⚠️ System Error while saving '{filename}': {e}",
        'CHOICE_ALL': "all",
        'CHOICE_YES': 'y',
        'CHOICE_PROTECTED': 'p',
        'CHOICE_PLAINTEXT': 'c',
        'BACKUP_PREFIX': "backup",
        'BACKUP_PART_FULL': "full-backup",
        'BACKUP_PART_MULTI': "multiple-dirs",
        'TQDM_TOTAL_BACKUP': "Total Backup",
        'TQDM_FILE': "  -> {filename:<40}"
    }
}
####################################

tqdm_lock = threading.Lock()
SCRIPT_DIR = os.path.dirname(os.path.realpath(__file__))

class Colors:
    GREEN = '\033[92m'
    RESET = '\033[0m'
    YELLOW = '\033[93m'
    RED = '\033[91m'

class CredentialsManager:
    # (Questa classe rimane identica, gestisce solo la crittografia)
    def __init__(self, filepath):
        self.filepath = filepath
    def _derive_key(self, password: bytes, salt: bytes) -> bytes:
        kdf = PBKDF2HMAC(algorithm=hashes.SHA256(), length=32, salt=salt, iterations=100000, backend=default_backend())
        return base64.urlsafe_b64encode(kdf.derive(password))
    def save(self, host, user, password, master_password):
        try:
            salt = os.urandom(16)
            key = self._derive_key(master_password.encode(), salt)
            fernet = Fernet(key)
            credentials_data = json.dumps({'host': host, 'user': user, 'pass': password}).encode()
            encrypted_data = fernet.encrypt(credentials_data)
            with open(self.filepath, 'wb') as f:
                f.write(salt + encrypted_data)
            return True
        except Exception: return False
    def load(self, master_password):
        try:
            with open(self.filepath, 'rb') as f: data = f.read()
            salt, encrypted_data = data[:16], data[16:]
            key = self._derive_key(master_password.encode(), salt)
            fernet = Fernet(key)
            decrypted_data = fernet.decrypt(encrypted_data)
            return json.loads(decrypted_data)
        except Exception: return None

def connect_ftp(host, user, password, t):
    try:
        ftp = ftplib.FTP(timeout=60)
        ftp.connect(host)
        ftp.login(user, password)
        ftp.set_pasv(True)
        return ftp
    except ftplib.all_errors as e:
        with tqdm_lock: tqdm.write(t['ERR_CONNECTION'].format(e=e))
        return None

def get_remote_dirs(ftp, t):
    print(t['STATUS_SCANNING'])
    remote_dirs = []
    try:
        items = ftp.mlsd()
        for name, facts in items:
            if facts.get('type') == 'dir' and name not in ['.', '..']:
                remote_dirs.append(name)
        print(t['OK_SCAN_COMPLETE'])
        return remote_dirs
    except Exception as e:
        print(t['ERR_SCAN_FAILED'].format(e=e))
        return []
def create_loading_bar_frames(width=10, char="■"):
    """Genera i fotogrammi per un'animazione a barra di caricamento."""
    frames = []
    for i in range(width + 1):
        bar = char * i
        padding = " " * (width - i)
        frames.append(f"[{bar}{padding}]")
    for i in range(width + 1):
        bar = char * (width - i)
        padding = " " * i
        frames.append(f"[{padding}{bar}]")
    return frames

def animate_discovery(stop_event, t):
    """Mostra un'animazione a barra di caricamento."""
    # Creiamo la sequenza di fotogrammi una sola volta
    loading_bar_frames = create_loading_bar_frames()
    spinner = itertools.cycle(loading_bar_frames)
    
    while not stop_event.is_set():
        try:
            spinner_text = f'\r {Colors.GREEN}{t["STATUS_DISCOVERING"]}{next(spinner)}{Colors.RESET}'
            sys.stdout.write(spinner_text)
            sys.stdout.flush()
            # Rallentiamo un po' l'animazione per renderla più visibile
            time.sleep(0.08) 
        except (ValueError, TypeError):
            break
            
    sys.stdout.write('\r' + ' ' * 60 + '\r')
    sys.stdout.flush()

def discover_files_recursive(ftp, remote_path, local_path, file_list, t):
    try:
        ftp.cwd(remote_path)
        os.makedirs(local_path, exist_ok=True)
        items = list(ftp.mlsd())
        for name, facts in items:
            if name in ['.', '..']: continue
            next_remote_path, next_local_path = f"{remote_path}/{name}", os.path.join(local_path, name)
            if facts.get('type') == 'dir':
                discover_files_recursive(ftp, next_remote_path, next_local_path, file_list, t)
            elif facts.get('type') == 'file':
                file_list.append((next_remote_path, next_local_path, int(facts.get('size', 0))))
    except Exception as e:
        with tqdm_lock: tqdm.write(t['ERR_EXPLORE_DIR'].format(path=remote_path, e=e))

def download_worker(q, pbar_overall, ftp_creds, t):
    ftp = connect_ftp(ftp_creds['host'], ftp_creds['user'], ftp_creds['pass'], t)
    if not ftp:
        try:
            q.get_nowait()
            q.task_done()
        except Queue.empty: pass
        return

    while not q.empty():
        try:
            remote_file_path, local_file_path, _ = q.get_nowait()
            try:
                os.makedirs(os.path.dirname(local_file_path), exist_ok=True)
                with open(local_file_path, 'wb') as f:
                    def callback(data):
                        f.write(data)
                        pbar_overall.update(len(data))
                    ftp.retrbinary(f'RETR {remote_file_path}', callback)
            except Exception as e:
                filename = os.path.basename(remote_file_path)
                with tqdm_lock: tqdm.write(t['ERR_DOWNLOAD_FILE'].format(filename=filename, e=e))
            finally:
                q.task_done()
        except Queue.empty: break
    ftp.quit()

def main():
    """Funzione principale che orchestra l'intero processo."""
    lang_choice = ""
    while lang_choice not in ['it', 'en']:
        lang_choice = input("Scegli la lingua / Choose language (it/en): ").lower().strip()
    t = STRINGS[lang_choice]

    print(t['APP_TITLE'])
    
    cred_manager = CredentialsManager(os.path.join(SCRIPT_DIR, ENCRYPTED_CREDS_FILE))
    plaintext_creds_path = os.path.join(SCRIPT_DIR, PLAINTEXT_CREDS_FILE)
    ftp_credentials = None
    use_saved = False

    if os.path.exists(cred_manager.filepath):
        choice = input(f"{Colors.YELLOW}{t['PROMPT_USE_SAVED_ENC']}{Colors.RESET} ({t['CHOICE_YES']}/n): ").lower().strip()
        if choice == t['CHOICE_YES']:
            master_pass = getpass.getpass(t['PROMPT_MASTER_PASS'])
            ftp_credentials = cred_manager.load(master_pass)
            if ftp_credentials:
                print(f"{Colors.GREEN}{t['OK_DECRYPT']}{Colors.RESET}")
                use_saved = True
            else:
                print(f"{Colors.RED}{t['ERR_DECRYPT_FAILED']}{Colors.RESET}")
    elif os.path.exists(plaintext_creds_path):
        choice = input(f"{Colors.RED}{t['PROMPT_USE_SAVED_PLAIN']}{Colors.RESET} ({t['CHOICE_YES']}/n): ").lower().strip()
        if choice == t['CHOICE_YES']:
            try:
                with open(plaintext_creds_path, 'r') as f:
                    ftp_credentials = json.load(f)
                use_saved = True
            except Exception as e:
                print(f"❌ Errore nel leggere il file di credenziali in chiaro: {e}")

    if not ftp_credentials:
        use_saved = False
        ftp_credentials = {
            'host': input(t['PROMPT_HOST']),
            'user': input(t['PROMPT_USER']),
            'pass': getpass.getpass(t['PROMPT_PASS'])
        }

    num_threads_input = input(t['PROMPT_THREADS'])
    try:
        num_threads = int(num_threads_input)
        if num_threads <= 0:
            print(t['ERR_INVALID_NUMBER'])
            num_threads = 15
    except ValueError:
        if num_threads_input != "": print(t['ERR_NOT_NUMERIC'])
        num_threads = 15

    print(t['STATUS_CONNECTING'].format(host=ftp_credentials['host']))
    ftp_main = connect_ftp(ftp_credentials['host'], ftp_credentials['user'], ftp_credentials['pass'], t)
    
    if not ftp_main: sys.exit(1)
    print(t['OK_CONNECTED'])

    if not use_saved:
        choice_save = input(f"\n{Colors.YELLOW}{t['PROMPT_SAVE_NEW']}{Colors.RESET} ({t['CHOICE_YES']}/n): ").lower().strip()
        if choice_save == t['CHOICE_YES']:
            choice_how = input(f"{Colors.YELLOW}{t['PROMPT_SAVE_HOW']}{Colors.RESET}").lower().strip()
            
            if choice_how == t['CHOICE_PROTECTED']:
                while True:
                    mp1 = getpass.getpass(t['PROMPT_CREATE_MASTER_PASS'])
                    mp2 = getpass.getpass(t['PROMPT_CONFIRM_MASTER_PASS'])
                    if mp1 == mp2:
                        if cred_manager.save(ftp_credentials['host'], ftp_credentials['user'], ftp_credentials['pass'], mp1):
                            print(f"{Colors.GREEN}{t['OK_SAVE']}{Colors.RESET}")
                            if os.path.exists(plaintext_creds_path): os.remove(plaintext_creds_path)
                        break
                    else:
                        print(f"{Colors.RED}{t['ERR_PASS_MISMATCH']}{Colors.RESET}")
            
            elif choice_how == t['CHOICE_PLAINTEXT']:
                confirm = input(f"{Colors.RED}{t['PROMPT_CONFIRM_PLAINTEXT']}{Colors.RESET}").lower().strip()
                if confirm == t['CHOICE_YES']:
                    try:
                        with open(plaintext_creds_path, 'w') as f:
                            json.dump(ftp_credentials, f, indent=4)
                        print(f"{Colors.GREEN}{t['OK_SAVE_PLAIN'].format(filename=PLAINTEXT_CREDS_FILE)}{Colors.RESET}")
                        if os.path.exists(cred_manager.filepath): os.remove(cred_manager.filepath)
                    except Exception as e:
                        print(f"❌ Errore durante il salvataggio in chiaro: {e}")

    available_dirs = get_remote_dirs(ftp_main, t)
    if not available_dirs:
        print(t['ERR_NO_DIRS_FOUND'])
        ftp_main.quit()
        return

    print(t['LBL_AVAILABLE_DIRS'])
    for i, dir_name in enumerate(available_dirs): print(f"  [{i + 1}] {dir_name}")
    print("------------------------------------------")
    selected_dirs, user_choice_raw = [], ""
    while True:
        try:
            user_choice_raw = input(t['PROMPT_DIRS'])
            choice = user_choice_raw.strip().lower()
            if choice == t['CHOICE_ALL']:
                selected_dirs = available_dirs
                break
            else:
                indices = [int(i.strip()) for i in choice.split(',')]
            if all(1 <= i <= len(available_dirs) for i in indices):
                selected_dirs = [available_dirs[i - 1] for i in indices]
                break
            else: print(t['ERR_INVALID_INPUT'])
        except ValueError: print(t['ERR_INVALID_INPUT'])

    timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
    if user_choice_raw.strip().lower() == t['CHOICE_ALL']: dynamic_name_part = t['BACKUP_PART_FULL']
    elif len(selected_dirs) == 1: dynamic_name_part = selected_dirs[0]
    else: dynamic_name_part = t['BACKUP_PART_MULTI']
    timestamped_folder_name = f"{t['BACKUP_PREFIX']}_{dynamic_name_part}_{timestamp}"
    local_backup_dir = os.path.join(SCRIPT_DIR, timestamped_folder_name)

    stop_spinner_event = threading.Event()
    spinner_thread = threading.Thread(target=animate_discovery, args=(stop_spinner_event, t))
    spinner_thread.daemon = True
    spinner_thread.start()

    files_to_download = []
    for dir_name in selected_dirs:
        remote_path, local_path = f"/{dir_name}", os.path.join(local_backup_dir, dir_name)
        discover_files_recursive(ftp_main, remote_path, local_path, files_to_download, t)
    
    stop_spinner_event.set()
    spinner_thread.join()
    ftp_main.quit()
    
    # --- NUOVA SEZIONE: Calcolo e Stampa del Riepilogo ---
    file_count = len(files_to_download)
    # Crea un set di percorsi di directory unici da tutti i file trovati
    unique_dirs = set(os.path.dirname(local_path) for _, local_path, _ in files_to_download)
    dir_count = len(unique_dirs)
    
    print(t['LBL_DISCOVERY_SUMMARY'].format(file_count=file_count, dir_count=dir_count))
    # --- FINE NUOVA SEZIONE ---

    if not files_to_download:
        print(t['LBL_BACKUP_COMPLETE'])
        return

    print(t['LBL_DOWNLOAD_START'])
    
    work_queue = Queue()
    for file_info in files_to_download: work_queue.put(file_info)

    total_backup_size = sum(size for _, _, size in files_to_download)
    pbar_overall = tqdm(total=total_backup_size, unit='B', unit_scale=True, desc=t['TQDM_TOTAL_BACKUP'])
    
    threads = []
    for _ in range(num_threads):
        thread = threading.Thread(target=download_worker, args=(work_queue, pbar_overall, ftp_credentials, t), daemon=True)
        thread.start()
        threads.append(thread)

    work_queue.join()
    pbar_overall.close()

    print(t['LBL_BACKUP_COMPLETE'])
    print(t['LBL_FILES_SAVED_TO'].format(path=local_backup_dir))

if __name__ == "__main__":
    main()