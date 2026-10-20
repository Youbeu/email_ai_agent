"""
Lanceur d'application Desktop native Windows pour Email AI Agent v2.0 (PyWebView + FastAPI).
Compatible mode fenêtré sans console (console=False sous PyInstaller) avec redirection sûre des flux.
"""
import os
import sys
import multiprocessing
import threading
import time
import socket
import urllib.request
import traceback

# Multiprocessing freeze support requis sous Windows pour PyInstaller
multiprocessing.freeze_support()

if getattr(sys, "frozen", False):
    APP_DIR = os.path.dirname(sys.executable)
else:
    APP_DIR = os.path.dirname(os.path.abspath(__file__))

LOG_FILE = os.path.join(APP_DIR, "app_debug.log")


class SafeLogStream:
    """Flux de substitution lorsque sys.stdout / sys.stderr valent None (mode PyInstaller console=False)."""

    def __init__(self, path: str):
        self.path = path

    def write(self, data: str):
        if not data:
            return
        try:
            with open(self.path, "a", encoding="utf-8") as f:
                f.write(str(data))
        except Exception:
            pass

    def flush(self):
        pass

    def isatty(self) -> bool:
        return False


if sys.stdout is None:
    sys.stdout = SafeLogStream(LOG_FILE)
if sys.stderr is None:
    sys.stderr = SafeLogStream(LOG_FILE)


def log(msg: str):
    try:
        with open(LOG_FILE, "a", encoding="utf-8") as f:
            f.write(f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] {msg}\n")
    except Exception:
        pass


import uvicorn
import webview
from server import app

PORT = 8000


def is_port_in_use(port: int) -> bool:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        return s.connect_ex(("127.0.0.1", port)) == 0


def wait_for_server(port: int, max_retries: int = 50, delay: float = 0.15) -> bool:
    """Attend activement que le serveur local réponde 200 OK sur /api/status avant d'ouvrir la fenêtre."""
    url = f"http://127.0.0.1:{port}/api/status"
    for _ in range(max_retries):
        try:
            with urllib.request.urlopen(url, timeout=0.6) as response:
                if response.status == 200:
                    return True
        except Exception:
            time.sleep(delay)
    return False


def start_api_server(port: int):
    """Démarre le serveur FastAPI en tâche de fond sans dépendre d'un terminal."""
    try:
        log(f"Démarrage d'Uvicorn sur 127.0.0.1:{port}...")
        config = uvicorn.Config(
            app,
            host="127.0.0.1",
            port=port,
            log_level="warning",
            log_config=None,
        )
        server = uvicorn.Server(config)
        server.run()
    except Exception as e:
        log(f"Erreur Uvicorn : {e}\n{traceback.format_exc()}")


def main():
    global PORT
    log("=== Lancement de Email AI Agent v2.0 ===")

    try:
        if is_port_in_use(PORT):
            if not wait_for_server(PORT, max_retries=2, delay=0.1):
                for test_port in range(8001, 8025):
                    if not is_port_in_use(test_port):
                        PORT = test_port
                        break

        log(f"Port sélectionné : {PORT}")

        server_thread = threading.Thread(target=start_api_server, args=(PORT,), daemon=True)
        server_thread.start()

        is_ready = wait_for_server(PORT, max_retries=50, delay=0.15)
        log(f"Serveur API prêt : {is_ready}")

        log("Création de la fenêtre native PyWebView...")
        webview.create_window(
            title="📬 Email AI Agent v2.0 — Poste de Pilotage Intelligent & Anti-Spam",
            url=f"http://127.0.0.1:{PORT}",
            width=1340,
            height=850,
            min_size=(1024, 680),
            background_color="#0B0F19",
            text_select=True,
        )

        log("Démarrage de la boucle GUI native...")
        webview.start(debug=False)
        log("Fermeture normale de l'application.")
    except Exception as e:
        log(f"FATAL ERROR dans main() : {e}\n{traceback.format_exc()}")


if __name__ == "__main__":
    main()
