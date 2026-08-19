"""
Lanceur d'application Desktop native pour Email AI Agent (via PyWebView et FastAPI).
Gestion robuste du port, freeze_support et journalisation des erreurs.
"""
import os
import sys
import multiprocessing
import threading
import time
import socket
import urllib.request
import traceback

# Multiprocessing freeze support pour Windows PyInstaller
multiprocessing.freeze_support()

# Gestion des chemins PyInstaller
if getattr(sys, 'frozen', False):
    APP_DIR = os.path.dirname(sys.executable)
else:
    APP_DIR = os.path.dirname(os.path.abspath(__file__))

LOG_FILE = os.path.join(APP_DIR, "app_debug.log")


def log(msg: str):
    try:
        with open(LOG_FILE, "a", encoding="utf-8") as f:
            f.write(f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] {msg}\n")
    except Exception:
        pass


import uvicorn
import webview

# Import de l'application FastAPI
from server import app

PORT = 8000


def is_port_in_use(port: int) -> bool:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        return s.connect_ex(('127.0.0.1', port)) == 0


def wait_for_server(port: int, max_retries: int = 40, delay: float = 0.2) -> bool:
    """Attend activement que le serveur local réponde 200 OK avant d'ouvrir la fenêtre."""
    url = f"http://127.0.0.1:{port}/api/status"
    for _ in range(max_retries):
        try:
            with urllib.request.urlopen(url, timeout=0.5) as response:
                if response.status == 200:
                    return True
        except Exception:
            time.sleep(delay)
    return False


def start_api_server(port: int):
    """Démarre le serveur FastAPI en tâche de fond sur le port spécifié."""
    try:
        log(f"Démarrage d'Uvicorn sur 127.0.0.1:{port}...")
        config = uvicorn.Config(app, host="127.0.0.1", port=port, log_level="warning")
        server = uvicorn.Server(config)
        server.run()
    except Exception as e:
        log(f"Erreur Uvicorn : {e}\n{traceback.format_exc()}")


def main():
    global PORT
    log("=== Lancement de Email AI Agent ===")

    try:
        # Si le port 8000 est déjà occupé, chercher un port libre (8001..8020)
        if is_port_in_use(PORT):
            if not wait_for_server(PORT, max_retries=2, delay=0.1):
                for test_port in range(8001, 8020):
                    if not is_port_in_use(test_port):
                        PORT = test_port
                        break

        log(f"Port sélectionné : {PORT}")

        # Lancement du serveur API dans un thread séparé
        server_thread = threading.Thread(target=start_api_server, args=(PORT,), daemon=True)
        server_thread.start()

        # Attente active que le serveur soit 100% opérationnel
        is_ready = wait_for_server(PORT, max_retries=50, delay=0.2)
        log(f"Serveur API prêt : {is_ready}")

        # Création de la fenêtre Desktop native Windows
        log("Création de la fenêtre PyWebView...")
        window = webview.create_window(
            title="📬 Email AI Agent - Assistant Intelligent & Anti-Spam",
            url=f"http://127.0.0.1:{PORT}",
            width=1280,
            height=820,
            min_size=(980, 650),
            background_color="#0F172A",
            text_select=True,
        )

        # Démarrage de la boucle GUI native
        log("Démarrage de la boucle GUI native webview...")
        webview.start(debug=False)
        log("Fermeture de l'application.")
    except Exception as e:
        log(f"FATAL ERROR dans main() : {e}\n{traceback.format_exc()}")


if __name__ == "__main__":
    main()
