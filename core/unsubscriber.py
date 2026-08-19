"""
Module sécurisé de détection et d'exécution du désabonnement (List-Unsubscribe & Liens HTML).
Inclut une protection robuste contre le SSRF (Server-Side Request Forgery) optimisée pour la vitesse.
"""
import re
import socket
import ipaddress
import urllib.parse
from typing import Dict, Any, List, Optional
from bs4 import BeautifulSoup
import requests
from core.email_client import EmailMessageData


def is_safe_url_syntax(url: str) -> bool:
    """Vérification syntaxique ultra-rapide (0 ms) sans appel DNS bloquant."""
    if not url or not isinstance(url, str):
        return False
    try:
        parsed = urllib.parse.urlparse(url.strip())
        if parsed.scheme not in ["http", "https"]:
            return False
        hostname = (parsed.hostname or "").lower()
        if not hostname:
            return False
        if hostname in ["localhost", "127.0.0.1", "::1", "0.0.0.0", "instance-data", "metadata.google.internal"]:
            return False
        if hostname.endswith(".local") or hostname.endswith(".internal"):
            return False
        return True
    except Exception:
        return False


def is_safe_external_url(url: str) -> bool:
    """Vérification stricte avec résolution DNS exécutée uniquement lors du clic de désabonnement."""
    if not is_safe_url_syntax(url):
        return False
    try:
        parsed = urllib.parse.urlparse(url)
        hostname = parsed.hostname
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
        self.urls = [u for u in urls if is_safe_url_syntax(u)]
        self.mailtos = mailtos
        self.one_click_post = one_click_post if (one_click_post and is_safe_url_syntax(one_click_post)) else None
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
        """Détecte instantanément les méthodes de désabonnement sans blocage réseau."""
        urls: List[str] = []
        mailtos: List[str] = []
        one_click_post: Optional[str] = None

        # 1. Vérification de l'en-tête standard List-Unsubscribe
        header_val = email_data.list_unsubscribe
        if header_val:
            for item in re.findall(r"<([^>]+)>", header_val):
                item = item.strip()
                if item.startswith("http://") or item.startswith("https://"):
                    urls.append(item)
                elif item.startswith("mailto:"):
                    mailtos.append(item.replace("mailto:", ""))

            if urls or mailtos:
                return UnsubscribeInfo(urls=urls, mailtos=mailtos, one_click_post=one_click_post, source="header")

        # 2. Analyse rapide du corps HTML si présent
        if email_data.body_html:
            try:
                soup = BeautifulSoup(email_data.body_html[:15000], "html.parser")
                for a in soup.find_all("a", href=True):
                    href = a["href"].strip()
                    text = a.get_text().lower()
                    if any(kw in text for kw in ["désabonner", "desabonner", "unsubscribe", "opt out", "se désinscrire"]):
                        if href.startswith("http://") or href.startswith("https://"):
                            urls.append(href)
                        elif href.startswith("mailto:"):
                            mailtos.append(href.replace("mailto:", ""))
            except Exception:
                pass

        return UnsubscribeInfo(urls=urls, mailtos=mailtos, one_click_post=one_click_post, source="body" if urls else "none")

    def execute_one_click(self, unsub_info: UnsubscribeInfo) -> Dict[str, Any]:
        """Exécute la requête de désabonnement sécurisée avec validation DNS SSRF."""
        target_url = unsub_info.primary_action_url
        if not target_url or not is_safe_external_url(target_url):
            return {"success": False, "method": "none", "error": "URL non sécurisée ou invalide"}

        try:
            if unsub_info.one_click_post:
                resp = requests.post(
                    target_url,
                    data={"List-Unsubscribe": "One-Click"},
                    headers=self.headers,
                    timeout=8,
                    allow_redirects=True,
                )
            else:
                resp = requests.get(target_url, headers=self.headers, timeout=8, allow_redirects=True)

            if resp.status_code in [200, 202, 204]:
                return {"success": True, "method": "http", "status_code": resp.status_code}
            return {"success": False, "method": "http", "status_code": resp.status_code}
        except Exception as e:
            return {"success": False, "method": "http", "error": str(e)}
