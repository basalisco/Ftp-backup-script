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

### --- DIZIONARIO MULTILINGUA --- ###
STRINGS = {
    'it': {
        'APP_TITLE': "--- Utilità di Backup FTP ---",
        'PROMPT_LANG': "Scegli la lingua / Choose language (it/en): ",
        'PROMPT_HOST': "Inserisci l'host FTP (es. ftp.dominio.com): ",
        'PROMPT_USER': "Inserisci l'utente FTP: ",
        'PROMPT_PASS': "Inserisci la password FTP (non sarà visibile): ",
        'PROMPT_THREADS': "\nQuanti 'operai' (thread) vuoi usare? [Invio per 15]\n(Più thread = più velocità, ma più carico sul server): ",
        'PROMPT_DIRS': "\n👉 Inserisci i numeri delle cartelle (separati da virgola), oppure 'tutto': ",
        'STATUS_CONNECTING': "\n🔌 Connessione a {host} per la scansione iniziale...",
        'OK_CONNECTED': "✅ Connessione FTP stabilita con successo.",
        'STATUS_SCANNING': "🔎 Scansione delle cartelle remote in corso...",
        'OK_SCAN_COMPLETE': "👍 Scansione completata.",
        'STATUS_DISCOVERING': " Scansione remota in corso potrebbe volerci un pò... ",
        'LBL_AVAILABLE_DIRS': "\n--- Cartelle disponibili per il backup ---",
        'LBL_FILES_FOUND': "Trovati {count} file da scaricare.",
        'LBL_DOWNLOAD_START': "\nDownload dei file in corso...",
        'LBL_BACKUP_COMPLETE': "\n🎉 Backup completato!",
        'LBL_FILES_SAVED_TO': "I file sono stati salvati in: {path}",
        'ERR_CONNECTION': "❌ Errore di connessione: {e}",
        'ERR_SCAN_FAILED': "❌ Scansione cartelle fallita: {e}.",
        'ERR_NO_DIRS_FOUND': "Nessuna cartella trovata sul server o errore durante la scansione.",
        'ERR_INVALID_INPUT': "❌ Input non valido.",
        'ERR_INVALID_NUMBER': "Numero non valido, uso 15 thread.",
        'ERR_NOT_NUMERIC': "Input non numerico, uso 15 thread.",
        'ERR_EXPLORE_DIR': "⚠️ Impossibile esplorare {path}: {e}",
        'ERR_DOWNLOAD_FILE': "    ⚠️ Errore download '{filename}': {e}",
        'ERR_SYSTEM_SAVE': "    ⚠️ Errore di Sistema durante il salvataggio di '{filename}': {e}",
        'CHOICE_ALL': "tutto",
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
        'STATUS_CONNECTING': "\n🔌 Connecting to {host} for initial scan...",
        'OK_CONNECTED': "✅ FTP connection established successfully.",
        'STATUS_SCANNING': "🔎 Scanning remote folders...",
        'OK_SCAN_COMPLETE': "👍 Scan complete.",
        'STATUS_DISCOVERING': " Remote scan in progress this may take a while... ",
        'LBL_AVAILABLE_DIRS': "\n--- Available folders for backup ---",
        'LBL_FILES_FOUND': "Found {count} files to download.",
        'LBL_DOWNLOAD_START': "\nDownloading files...",
        'LBL_BACKUP_COMPLETE': "\n🎉 Backup complete!",
        'LBL_FILES_SAVED_TO': "Files have been saved to: {path}",
        'ERR_CONNECTION': "❌ Connection error: {e}",
        'ERR_SCAN_FAILED': "❌ Folder scan failed: {e}.",
        'ERR_NO_DIRS_FOUND': "No folders found on server or scan error.",
        'ERR_INVALID_INPUT': "❌ Invalid input.",
        'ERR_INVALID_NUMBER': "Invalid number, using 15 threads.",
        'ERR_NOT_NUMERIC': "Non-numeric input, using 15 threads.",
        'ERR_EXPLORE_DIR': "⚠️ Could not explore {path}: {e}",
        'ERR_DOWNLOAD_FILE': "    ⚠️ Error downloading '{filename}': {e}",
        'ERR_SYSTEM_SAVE': "    ⚠️ System Error while saving '{filename}': {e}",
        'CHOICE_ALL': "all",
        'BACKUP_PREFIX': "backup",
        'BACKUP_PART_FULL': "full-backup",
        'BACKUP_PART_MULTI': "multiple-dirs",
        'TQDM_TOTAL_BACKUP': "Total Backup",
        'TQDM_FILE': "  -> {filename:<40}"
    }
}
####################################

# Una lock per rendere thread-safe la scrittura su console con tqdm
tqdm_lock = threading.Lock()
SCRIPT_DIR = os.path.dirname(os.path.realpath(__file__))

class Colors:
    GREEN = '\033[92m'
    RESET = '\033[0m'

def connect_ftp(host, user, password, t):
    try:
        ftp = ftplib.FTP(timeout=60)
        ftp.connect(host)
        ftp.login(user, password)
        ftp.set_pasv(True)
        return ftp
    except ftplib.all_errors as e:
        with tqdm_lock:
            tqdm.write(t['ERR_CONNECTION'].format(e=e))
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

def animate_discovery(stop_event, t):
    spinner = itertools.cycle(['⣾', '⣽', '⣻', '⢿', '⡿', '⣟', '⣯', '⣷'])
    while not stop_event.is_set():
        try:
            spinner_text = f'\r {Colors.GREEN}{t["STATUS_DISCOVERING"]}{next(spinner)}{Colors.RESET}'
            sys.stdout.write(spinner_text)
            sys.stdout.flush()
            time.sleep(0.1)
        except (ValueError, TypeError): break
    sys.stdout.write('\r' + ' ' * 60 + '\r')
    sys.stdout.flush()

def discover_files_recursive(ftp, remote_path, local_path, file_list, t):
    try:
        ftp.cwd(remote_path)
        os.makedirs(local_path, exist_ok=True)
        items = list(ftp.mlsd())
        for name, facts in items:
            if name in ['.', '..']: continue
            next_remote_path = f"{remote_path}/{name}"
            next_local_path = os.path.join(local_path, name)
            if facts.get('type') == 'dir':
                discover_files_recursive(ftp, next_remote_path, next_local_path, file_list, t)
            elif facts.get('type') == 'file':
                file_size = int(facts.get('size', 0))
                file_list.append((next_remote_path, next_local_path, file_size))
    except Exception as e:
        with tqdm_lock:
            tqdm.write(t['ERR_EXPLORE_DIR'].format(path=remote_path, e=e))

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
                with tqdm_lock:
                    tqdm.write(t['ERR_DOWNLOAD_FILE'].format(filename=filename, e=e))
            finally:
                q.task_done()
        except Queue.empty: break
            
    ftp.quit()

def main():
    # --- Selezione Lingua ---
    lang_choice = ""
    while lang_choice not in ['it', 'en']:
        lang_choice = input("Scegli la lingua / Choose language (it/en): ").lower().strip()
    t = STRINGS[lang_choice]

    print(t['APP_TITLE'])
    
    ftp_host = input(t['PROMPT_HOST'])
    ftp_user = input(t['PROMPT_USER'])
    ftp_pass = getpass.getpass(t['PROMPT_PASS'])
    
    num_threads_input = input(t['PROMPT_THREADS'])
    try:
        num_threads = int(num_threads_input)
        if num_threads <= 0:
            print(t['ERR_INVALID_NUMBER'])
            num_threads = 15
    except ValueError:
        if num_threads_input != "":
            print(t['ERR_NOT_NUMERIC'])
        num_threads = 15

    ftp_credentials = {'host': ftp_host, 'user': ftp_user, 'pass': ftp_pass}

    print(t['STATUS_CONNECTING'].format(host=ftp_host))
    ftp_main = connect_ftp(ftp_credentials['host'], ftp_credentials['user'], ftp_credentials['pass'], t)
    if not ftp_main: sys.exit(1)

    available_dirs = get_remote_dirs(ftp_main, t)
    if not available_dirs:
        print(t['ERR_NO_DIRS_FOUND'])
        ftp_main.quit()
        return

    print(t['LBL_AVAILABLE_DIRS'])
    for i, dir_name in enumerate(available_dirs):
        print(f"  [{i + 1}] {dir_name}")
    print("------------------------------------------")
    selected_dirs = []
    user_choice_raw = ""
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
            else:
                print(t['ERR_INVALID_INPUT'])
        except ValueError:
            print(t['ERR_INVALID_INPUT'])

    timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
    dynamic_name_part = ""
    if user_choice_raw.strip().lower() == t['CHOICE_ALL']:
        dynamic_name_part = t['BACKUP_PART_FULL']
    elif len(selected_dirs) == 1:
        dynamic_name_part = selected_dirs[0]
    else:
        dynamic_name_part = t['BACKUP_PART_MULTI']
    timestamped_folder_name = f"{t['BACKUP_PREFIX']}_{dynamic_name_part}_{timestamp}"
    local_backup_dir = os.path.join(SCRIPT_DIR, timestamped_folder_name)

    stop_spinner_event = threading.Event()
    spinner_thread = threading.Thread(target=animate_discovery, args=(stop_spinner_event, t))
    spinner_thread.daemon = True
    spinner_thread.start()

    files_to_download = []
    for dir_name in selected_dirs:
        remote_path = f"/{dir_name}"
        local_path = os.path.join(local_backup_dir, dir_name)
        discover_files_recursive(ftp_main, remote_path, local_path, files_to_download, t)
    
    stop_spinner_event.set()
    spinner_thread.join()
    ftp_main.quit()
    
    total_backup_size = sum(size for _, _, size in files_to_download)
    print(t['LBL_FILES_FOUND'].format(count=len(files_to_download)))

    if not files_to_download:
        print(t['LBL_BACKUP_COMPLETE'])
        return

    print(t['LBL_DOWNLOAD_START'])
    
    work_queue = Queue()
    for file_info in files_to_download:
        work_queue.put(file_info)

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