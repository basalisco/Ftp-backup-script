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
class Colors:
    GREEN = '\033[92m'  # Verde brillante
    RESET = '\033[0m'   # Resetta al colore di default
### --- CONFIGURAZIONE --- ###
# Prefisso per la cartella di backup. Verrà aggiunto il nome e data/ora.
BACKUP_FOLDER_PREFIX = "backup"
####################################

# Una lock per rendere thread-safe la scrittura su console con tqdm
tqdm_lock = threading.Lock()

# Determina il percorso assoluto della directory dello script
SCRIPT_DIR = os.path.dirname(os.path.realpath(__file__))

def connect_ftp(host, user, password):
    """Si connette al server FTP usando le credenziali fornite."""
    try:
        ftp = ftplib.FTP(timeout=60)
        ftp.connect(host)
        ftp.login(user, password)
        ftp.set_pasv(True)
        return ftp
    except ftplib.all_errors as e:
        with tqdm_lock:
            tqdm.write(f"❌ Errore di connessione: {e}")
        return None

def get_remote_dirs(ftp):
    """Restituisce una lista delle cartelle remote usando il comando efficiente MLSD."""
    print("🔎 Scansione delle cartelle remote in corso...")
    remote_dirs = []
    try:
        items = ftp.mlsd()
        for name, facts in items:
            if facts.get('type') == 'dir' and name not in ['.', '..']:
                remote_dirs.append(name)
        print("👍 Scansione completata.")
        return remote_dirs
    except Exception as e:
        print(f"❌ Scansione cartelle fallita: {e}.")
        return []

def animate_discovery(stop_event):
    """Mostra un'animazione 'spinner' moderna e colorata sulla console."""
    # Scegli la tua animazione preferita e inseriscila qui!
    spinner = itertools.cycle(['⣾', '⣽', '⣻', '⢿', '⡿', '⣟', '⣯', '⣷'])
    
    while not stop_event.is_set():
        try:
            spinner_text = f'\r {Colors.GREEN}Scansione remota in corso potrebbe volerci un pò... {next(spinner)}{Colors.RESET}'
            sys.stdout.write(spinner_text)
            sys.stdout.flush()
            time.sleep(0.1)
        except (ValueError, TypeError):
            break
            
    # Pulisce la riga alla fine
    sys.stdout.write('\r' + ' ' * 50 + '\r')
    sys.stdout.flush()

def discover_files_recursive(ftp, remote_path, local_path, file_list):
    """Esplora ricorsivamente le cartelle e crea una lista di tutti i file da scaricare."""
    try:
        ftp.cwd(remote_path)
        os.makedirs(local_path, exist_ok=True)
        items = list(ftp.mlsd())
        for name, facts in items:
            if name in ['.', '..']:
                continue
            next_remote_path = f"{remote_path}/{name}"
            next_local_path = os.path.join(local_path, name)
            if facts.get('type') == 'dir':
                discover_files_recursive(ftp, next_remote_path, next_local_path, file_list)
            elif facts.get('type') == 'file':
                file_size = int(facts.get('size', 0))
                file_list.append((next_remote_path, next_local_path, file_size))
    except Exception as e:
        with tqdm_lock:
            tqdm.write(f"⚠️ Impossibile esplorare {remote_path}: {e}")

def download_worker(q, pbar_overall, ftp_creds):
    """Funzione eseguita da ogni thread per scaricare i file."""
    ftp = connect_ftp(ftp_creds['host'], ftp_creds['user'], ftp_creds['pass'])
    if not ftp:
        try:
            q.get_nowait()
            q.task_done()
        except Queue.empty:
            pass
        return

    while not q.empty():
        try:
            remote_file_path, local_file_path, _ = q.get_nowait()
            try:
                # Crea la sotto-cartella locale se non esiste, appena prima del download
                os.makedirs(os.path.dirname(local_file_path), exist_ok=True)
                with open(local_file_path, 'wb') as f:
                    def callback(data):
                        f.write(data)
                        pbar_overall.update(len(data))
                    ftp.retrbinary(f'RETR {remote_file_path}', callback)
            except Exception as e:
                with tqdm_lock:
                    tqdm.write(f"    ⚠️ Errore download '{os.path.basename(remote_file_path)}': {e}")
            finally:
                q.task_done()
        except Queue.empty:
            break
            
    ftp.quit()

def main():
    """Funzione principale che orchestra l'intero processo."""
    print("--- Utilità di Backup FTP ---")
    
    # --- Richiesta dinamica delle credenziali e dei thread ---
    ftp_host = input("Inserisci l'host FTP (es. ftp.dominio.com): ")
    ftp_user = input("Inserisci l'utente FTP: ")
    ftp_pass = getpass.getpass("Inserisci la password FTP (non sarà visibile): ")

    num_threads_input = input("\nQuanti 'operai' (thread) vuoi usare? [Invio per 15]\n(Più thread = più velocità, ma più carico sul server): ")
    try:
        num_threads = int(num_threads_input)
        if num_threads <= 0:
            print("Numero non valido, uso 15 thread.")
            num_threads = 15
    except ValueError:
        print("Input non numerico, uso 15 thread.")
        num_threads = 15

    ftp_credentials = {'host': ftp_host, 'user': ftp_user, 'pass': ftp_pass}

    print(f"\n🔌 Connessione a {ftp_host} per la scansione iniziale...")
    ftp_main = connect_ftp(ftp_credentials['host'], ftp_credentials['user'], ftp_credentials['pass'])
    if not ftp_main:
        sys.exit(1)

    available_dirs = get_remote_dirs(ftp_main)

    if not available_dirs:
        print("Nessuna cartella trovata sul server o errore durante la scansione.")
        ftp_main.quit()
        return

    # --- Selezione utente ---
    print("\n--- Cartelle disponibili per il backup ---")
    for i, dir_name in enumerate(available_dirs):
        print(f"  [{i + 1}] {dir_name}")
    print("------------------------------------------")
    selected_dirs = []
    user_choice_raw = ""
    while True:
        try:
            user_choice_raw = input("\n👉 Inserisci i numeri delle cartelle (separati da virgola), oppure 'tutto': ")
            choice = user_choice_raw.strip().lower()
            if choice == 'tutto':
                selected_dirs = available_dirs
                break
            else:
                indices = [int(i.strip()) for i in choice.split(',')]
            if all(1 <= i <= len(available_dirs) for i in indices):
                selected_dirs = [available_dirs[i - 1] for i in indices]
                break
            else:
                print("❌ Input non valido.")
        except ValueError:
            print("❌ Input non valido.")

    # --- Creazione del nome della cartella di backup con nome dinamico, data e ora ---
    timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
    dynamic_name_part = ""
    if user_choice_raw.strip().lower() == 'tutto':
        dynamic_name_part = "full-backup"
    elif len(selected_dirs) == 1:
        dynamic_name_part = selected_dirs[0]
    else:
        dynamic_name_part = "multiple-dirs"

    timestamped_folder_name = f"{BACKUP_FOLDER_PREFIX}_{dynamic_name_part}_{timestamp}"
    local_backup_dir = os.path.join(SCRIPT_DIR, timestamped_folder_name)
    # --- Fine modifica ---

    stop_spinner_event = threading.Event()
    spinner_thread = threading.Thread(target=animate_discovery, args=(stop_spinner_event,))
    spinner_thread.daemon = True
    spinner_thread.start()

    files_to_download = []
    for dir_name in selected_dirs:
        remote_path = f"/{dir_name}"
        # La base per i percorsi locali ora è la cartella con timestamp
        local_path = os.path.join(local_backup_dir, dir_name)
        discover_files_recursive(ftp_main, remote_path, local_path, files_to_download)
    
    stop_spinner_event.set()
    spinner_thread.join()
    ftp_main.quit()
    
    total_backup_size = sum(size for _, _, size in files_to_download)
    print(f"Trovati {len(files_to_download)} file da scaricare.")

    if not files_to_download:
        print("Nessun file da scaricare. Backup completato.")
        return

    print(f"\nDownload dei file in corso...")
    
    work_queue = Queue()
    for file_info in files_to_download:
        work_queue.put(file_info)

    pbar_overall = tqdm(total=total_backup_size, unit='B', unit_scale=True, desc="Backup Totale")
    
    threads = []
    for _ in range(num_threads):
        thread = threading.Thread(target=download_worker, args=(work_queue, pbar_overall, ftp_credentials), daemon=True)
        thread.start()
        threads.append(thread)

    work_queue.join()
    pbar_overall.close()

    print("\n🎉 Backup completato!")
    print(f"I file sono stati salvati in: {local_backup_dir}")

if __name__ == "__main__":
    main()