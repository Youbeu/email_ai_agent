"""
Lanceur d'application Desktop native pour Email AI Agent (via PyWebView et FastAPI).
"""
import os
import sys
import threading
import time
import uvicorn
import webview

# Import de l'application FastAPI
from server import app


def start_api_server():
    """Démarre le serveur FastAPI en tâche de fond."""
    config = uvicorn.Config(app, host="127.0.0.1", port=8000, log_level="warning")
    server = uvicorn.Server(config)
    server.run()


def main():
    # Lancement du serveur API dans un thread séparé
    server_thread = threading.Thread(target=start_api_server, daemon=True)
    server_thread.start()

    # Petite pause pour s'assurer que le serveur est prêt
    time.sleep(1.0)

    # Création de la fenêtre Desktop native Windows
    window = webview.create_window(
        title="📬 Email AI Agent - Assistant Intelligent & Anti-Spam",
        url="http://127.0.0.1:8000",
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
