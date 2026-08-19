"""
Lanceur d'application Desktop native pour Email AI Agent (via PyWebView et FastAPI).
Gestion robuste du port et attente active de démarrage du serveur local.
"""
import os
import sys
import threading
import time
import socket
import urllib.request
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
    config = uvicorn.Config(app, host="127.0.0.1", port=port, log_level="warning")
    server = uvicorn.Server(config)
    server.run()


def main():
    global PORT
    # Si le port 8000 est déjà occupé, chercher un port libre (8001..8010)
    if is_port_in_use(PORT):
        # Vérifier si c'est déjà notre serveur qui répond
        if not wait_for_server(PORT, max_retries=2, delay=0.1):
            for test_port in range(8001, 8020):
                if not is_port_in_use(test_port):
                    PORT = test_port
                    break

    # Lancement du serveur API dans un thread séparé
    server_thread = threading.Thread(target=start_api_server, args=(PORT,), daemon=True)
    server_thread.start()

    # Attente active que le serveur soit 100% opérationnel
    wait_for_server(PORT, max_retries=50, delay=0.2)

    # Création de la fenêtre Desktop native Windows
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
    webview.start(debug=False)


if __name__ == "__main__":
    main()
