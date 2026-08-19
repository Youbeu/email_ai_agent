"""
Module sécurisé de détection et d'exécution du désabonnement (List-Unsubscribe & Liens HTML).
Inclut une protection robuste contre le SSRF (Server-Side Request Forgery).
"""
import re
import socket
import ipaddress
import urllib.parse
import webbrowser
from typing import Dict, Any, List, Optional
from bs4 import BeautifulSoup
import requests
from core.email_client import EmailMessageData


def is_safe_external_url(url: str) -> bool:
    """
    Vérifie qu'une URL est publique et sécurisée contre les attaques SSRF.
    Bloque localhost, 127.0.0.1, 169.254.169.254, 10.x, 192.168.x, 172.16-31.x, etc.
    """
    try:
        parsed = urllib.parse.urlparse(url)
        if parsed.scheme not in ["http", "https"]:
            return False

        hostname = parsed.hostname
        if not hostname:
            return False

        # Bloquer les noms d'hôtes réservés
        blocked_hosts = ["localhost", "127.0.0.1", "::1", "0.0.0.0", "instance-data", "metadata.google.internal"]
        if hostname.lower() in blocked_hosts or hostname.lower().endswith(".local"):
            return False

        # Résolution DNS et vérification IP
        ip_str = socket.gethostbyname(hostname)
        ip_obj = ipaddress.ip_address(ip_str)

        if ip_obj.is_private or ip_obj.is_loopback or ip_obj.is_link_local or ip_obj.is_reserved or ip_obj.is_multicast:
            return False

        return True
    except Exception:
        return False


class UnsubscribeInfo:
    def __init__(
        self,
        urls: List[str],
        mailtos: List[str],
        one_click_post: Optional[str] = None,
        source: str = "none",
    ):
        self.urls = [u for u in urls if is_safe_external_url(u)]
        self.mailtos = mailtos
        self.one_click_post = one_click_post if (one_click_post and is_safe_external_url(one_click_post)) else None
        self.source = source

    @property
    def has_unsubscribe(self) -> bool:
        return bool(self.urls or self.mailtos or self.one_click_post)

    @property
    def primary_action_url(self) -> Optional[str]:
        if self.one_click_post:
            return self.one_click_post
        if self.urls:
            return self.urls[0]
        return None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "has_unsubscribe": self.has_unsubscribe,
            "urls": self.urls,
            "mailtos": self.mailtos,
            "one_click_post": self.one_click_post,
            "source": self.source,
            "primary_url": self.primary_action_url,
        }


class Unsubscriber:
    def __init__(self, user_agent: str = "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"):
        self.headers = {
            "User-Agent": user_agent,
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        }

    def detect(self, email_data: EmailMessageData) -> UnsubscribeInfo:
        """
        Détecte les méthodes de désabonnement à partir des en-têtes RFC ou du corps HTML.
        """
        urls: List[str] = []
        mailtos: List[str] = []
        one_click_post: Optional[str] = None

        # 1. Vérification de l'en-tête standard List-Unsubscribe
        header_val = email_data.list_unsubscribe
        if header_val:
            matches = re.findall(r"<([^>]+)>", header_val)
            for m in matches:
                m_clean = m.strip()
                if m_clean.lower().startswith("mailto:"):
                    mailtos.append(m_clean)
                elif m_clean.lower().startswith("http") and is_safe_external_url(m_clean):
                    urls.append(m_clean)

            # Vérifier si List-Unsubscribe-Post existe (RFC 8058)
            post_header = str(email_data.raw_message.get("List-Unsubscribe-Post", "") if email_data.raw_message else "")
            if "List-Unsubscribe=One-Click" in post_header and urls:
                one_click_post = urls[0]

            if urls or mailtos:
                return UnsubscribeInfo(urls=urls, mailtos=mailtos, one_click_post=one_click_post, source="header")

        # 2. Recherche dans le corps HTML
        if email_data.body_html:
            try:
                soup = BeautifulSoup(email_data.body_html, "html.parser")
                unsub_keywords = [
                    "unsubscribe", "désabonner", "desabonner", "désinscrire", "desinscrire",
                    "désinscription", "desinscription", "se désinscrire", "se desabonner",
                    "opt-out", "opt out", "manage preferences", "préférences de communication",
                    "gérer mes abonnements", "cliquez ici pour ne plus recevoir"
                ]

                for a_tag in soup.find_all("a", href=True):
                    href = a_tag["href"].strip()
                    link_text = a_tag.get_text().strip().lower()
                    
                    if any(kw in link_text for kw in unsub_keywords) or any(kw in href.lower() for kw in ["unsub", "desabon", "optout"]):
                        if href.lower().startswith("http") and is_safe_external_url(href) and href not in urls:
                            urls.append(href)
                        elif href.lower().startswith("mailto:") and href not in mailtos:
                            mailtos.append(href)
            except Exception:
                pass

        if urls or mailtos:
            return UnsubscribeInfo(urls=urls, mailtos=mailtos, source="body_link")

        return UnsubscribeInfo(urls=[], mailtos=[], source="none")

    def execute_one_click(self, unsub_info: UnsubscribeInfo) -> Dict[str, Any]:
        """
        Tente un désabonnement sécurisé (HTTP POST One-Click ou GET).
        """
        if unsub_info.one_click_post:
            if not is_safe_external_url(unsub_info.one_click_post):
                return {"success": False, "message": "URL bloquée par la politique de sécurité SSRF."}
            try:
                resp = requests.post(
                    unsub_info.one_click_post,
                    data={"List-Unsubscribe": "One-Click"},
                    headers=self.headers,
                    timeout=8,
                    allow_redirects=False,
                )
                return {
                    "success": resp.status_code in [200, 202, 204, 302, 303],
                    "status_code": resp.status_code,
                    "method": "POST One-Click",
                    "message": "Désabonnement RFC 8058 One-Click envoyé avec succès."
                }
            except Exception as e:
                return {"success": False, "method": "POST One-Click", "message": f"Erreur requête : {e}"}

        if unsub_info.urls:
            target_url = unsub_info.urls[0]
            if not is_safe_external_url(target_url):
                return {"success": False, "message": "URL bloquée par la politique de sécurité SSRF."}
            try:
                resp = requests.get(target_url, headers=self.headers, timeout=8, allow_redirects=True)
                return {
                    "success": resp.status_code in [200, 204],
                    "status_code": resp.status_code,
                    "method": "HTTP GET",
                    "url": target_url,
                    "message": "Lien de désabonnement visité avec succès."
                }
            except Exception as e:
                return {"success": False, "method": "HTTP GET", "message": f"Erreur requête : {e}"}

        return {"success": False, "message": "Aucun lien HTTP direct sécurisé trouvé."}

    def open_link_in_browser(self, unsub_info: UnsubscribeInfo) -> bool:
        """Ouvre le lien de désabonnement vérifié dans le navigateur."""
        url = unsub_info.primary_action_url
        if url and is_safe_external_url(url):
            webbrowser.open(url)
            return True
        return False
