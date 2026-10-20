"""
Module sécurisé de détection et d'exécution du désabonnement (RFC 2369 List-Unsubscribe, RFC 8058 One-Click & Liens HTML).
Inclut une protection stricte contre le SSRF (IPv4 + IPv6 via getaddrinfo, blocage des redirections vers réseaux privés).
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

BLOCKED_HOSTNAMES = {
    "localhost",
    "127.0.0.1",
    "::1",
    "0.0.0.0",
    "instance-data",
    "metadata.google.internal",
    "metadata",
    "169.254.169.254",
}

MAX_REDIRECT_HOPS = 5


def is_safe_url_syntax(url: str) -> bool:
    """Vérification syntaxique rapide (0 ms) sans appel DNS bloquant."""
    if not url or not isinstance(url, str):
        return False
    try:
        parsed = urllib.parse.urlparse(url.strip())
        if parsed.scheme not in ("http", "https"):
            return False
        hostname = (parsed.hostname or "").lower().strip(".")
        if not hostname:
            return False
        if hostname in BLOCKED_HOSTNAMES:
            return False
        if hostname.endswith(".local") or hostname.endswith(".internal") or hostname.endswith(".lan"):
            return False
        # Si le hostname est directement une adresse IP littérale, la valider immédiatement
        try:
            ip_obj = ipaddress.ip_address(hostname)
            if not _is_public_ip(ip_obj):
                return False
        except ValueError:
            pass
        return True
    except Exception:
        return False


def _is_public_ip(ip_obj: ipaddress._BaseAddress) -> bool:
    """Vérifie qu'une adresse IPv4 ou IPv6 est strictement publique et routable."""
    if (
        ip_obj.is_private
        or ip_obj.is_loopback
        or ip_obj.is_link_local
        or ip_obj.is_reserved
        or ip_obj.is_multicast
        or ip_obj.is_unspecified
    ):
        return False
    # Vérification additionnelle pour les adresses IPv4 mappées dans IPv6 (ex: ::ffff:127.0.0.1)
    if isinstance(ip_obj, ipaddress.IPv6Address) and ip_obj.ipv4_mapped:
        return _is_public_ip(ip_obj.ipv4_mapped)
    return True


def is_safe_external_url(url: str) -> bool:
    """
    Vérification anti-SSRF stricte avec résolution DNS complète (IPv4 A + IPv6 AAAA).
    Refuse l'URL si au moins une IP résolue pointe vers une plage privée/interne.
    """
    if not is_safe_url_syntax(url):
        return False
    try:
        parsed = urllib.parse.urlparse(url.strip())
        hostname = parsed.hostname
        if not hostname:
            return False

        addr_info = socket.getaddrinfo(hostname, parsed.port or (443 if parsed.scheme == "https" else 80), proto=socket.IPPROTO_TCP)
        if not addr_info:
            return False

        for family, _, _, _, sockaddr in addr_info:
            ip_str = sockaddr[0]
            # Nettoyage d'un éventuel scope ID IPv6 (%eth0)
            ip_str = ip_str.split("%")[0]
            ip_obj = ipaddress.ip_address(ip_str)
            if not _is_public_ip(ip_obj):
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
        # Déduplication tout en préservant l'ordre
        seen_urls = set()
        clean_urls = []
        for u in urls:
            u_clean = u.strip()
            if is_safe_url_syntax(u_clean) and u_clean not in seen_urls:
                seen_urls.add(u_clean)
                clean_urls.append(u_clean)

        self.urls = clean_urls
        self.mailtos = [m.strip() for m in mailtos if m and "@" in m]
        self.one_click_post = (
            one_click_post.strip()
            if (one_click_post and is_safe_url_syntax(one_click_post.strip()))
            else None
        )
        self.source = source

    @property
    def has_unsubscribe(self) -> bool:
        return bool(self.urls or self.mailtos or self.one_click_post)

    @property
    def supports_rfc8058_one_click(self) -> bool:
        return bool(self.one_click_post)

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
            "supports_one_click": self.supports_rfc8058_one_click,
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
        """Détecte les méthodes de désabonnement (RFC 2369, RFC 8058 One-Click et liens HTML)."""
        urls: List[str] = []
        mailtos: List[str] = []
        one_click_post: Optional[str] = None

        # 1. En-têtes standards List-Unsubscribe (RFC 2369) & List-Unsubscribe-Post (RFC 8058)
        header_val = getattr(email_data, "list_unsubscribe", "") or ""
        post_header_val = getattr(email_data, "list_unsubscribe_post", "") or ""
        has_rfc8058_post = "list-unsubscribe=one-click" in post_header_val.lower()

        if header_val:
            # Extraction des URI entre chevrons <...> ou séparées par des virgules
            brackets = re.findall(r"<([^>]+)>", header_val)
            candidates = brackets if brackets else [p.strip() for p in header_val.split(",")]
            for item in candidates:
                item = item.strip()
                if item.lower().startswith(("http://", "https://")):
                    urls.append(item)
                elif item.lower().startswith("mailto:"):
                    mailtos.append(item[7:].split("?")[0].strip())

            if urls and has_rfc8058_post:
                # RFC 8058 requiert d'envoyer un POST sur l'URI HTTPS de List-Unsubscribe
                https_urls = [u for u in urls if u.lower().startswith("https://")]
                one_click_post = https_urls[0] if https_urls else urls[0]

            if urls or mailtos:
                return UnsubscribeInfo(
                    urls=urls,
                    mailtos=mailtos,
                    one_click_post=one_click_post,
                    source="header",
                )

        # 2. Analyse du corps HTML si présent
        if email_data.body_html:
            try:
                soup = BeautifulSoup(email_data.body_html[:30000], "html.parser")
                unsub_keywords = [
                    "désabonner", "desabonner", "désinscrire", "desinscrire",
                    "unsubscribe", "opt out", "opt-out", "se désabonner",
                    "manage preferences", "gérer mes préférences", "abbestellen",
                ]
                for a in soup.find_all("a", href=True):
                    href = a["href"].strip()
                    text = a.get_text(" ", strip=True).lower()
                    href_lower = href.lower()

                    is_unsub_text = any(kw in text for kw in unsub_keywords)
                    is_unsub_href = any(kw in href_lower for kw in ["unsubscribe", "unsub", "optout", "opt-out", "desabonnement", "desinscription"])

                    if is_unsub_text or is_unsub_href:
                        if href_lower.startswith(("http://", "https://")):
                            urls.append(href)
                        elif href_lower.startswith("mailto:"):
                            mailtos.append(href[7:].split("?")[0].strip())
            except Exception:
                pass

        return UnsubscribeInfo(
            urls=urls,
            mailtos=mailtos,
            one_click_post=None,
            source="body" if (urls or mailtos) else "none",
        )

    def _safe_request(self, method: str, url: str, data: Optional[Dict[str, str]] = None) -> requests.Response:
        """
        Exécute une requête HTTP avec suivi manuel des redirections et validation anti-SSRF à chaque saut.
        Empêche tout contournement SSRF par redirection 301/302 vers 127.0.0.1 ou 169.254.169.254.
        """
        current_url = url
        current_method = method.upper()
        current_data = data

        for _ in range(MAX_REDIRECT_HOPS + 1):
            if not is_safe_external_url(current_url):
                raise ValueError(f"URL bloquée par la politique de sécurité anti-SSRF : {current_url}")

            req_headers = dict(self.headers)
            resp = requests.request(
                method=current_method,
                url=current_url,
                data=current_data,
                headers=req_headers,
                timeout=8,
                allow_redirects=False,
            )

            if resp.status_code in (301, 302, 303, 307, 308):
                location = resp.headers.get("Location")
                if not location:
                    return resp
                current_url = urllib.parse.urljoin(current_url, location.strip())
                # Selon HTTP, 301/302/303 transforment généralement un POST en GET
                if resp.status_code in (301, 302, 303) and current_method == "POST":
                    current_method = "GET"
                    current_data = None
                continue

            return resp

        raise ValueError("Trop de redirections HTTP lors de la tentative de désabonnement.")

    def execute_one_click(self, unsub_info: UnsubscribeInfo) -> Dict[str, Any]:
        """Exécute la requête de désabonnement sécurisée avec validation DNS SSRF à chaque étape."""
        target_url = unsub_info.primary_action_url
        if not target_url:
            if unsub_info.mailtos:
                return {
                    "success": False,
                    "method": "mailto",
                    "mailto": unsub_info.mailtos[0],
                    "message": f"Désabonnement par email requis : {unsub_info.mailtos[0]}",
                }
            return {"success": False, "method": "none", "message": "Aucune URL de désabonnement disponible."}

        if not is_safe_external_url(target_url):
            return {
                "success": False,
                "method": "blocked",
                "error": "URL bloquée par la protection anti-SSRF (réseau privé ou invalide).",
                "message": "URL bloquée par la protection anti-SSRF.",
            }

        try:
            if unsub_info.one_click_post:
                resp = self._safe_request(
                    "POST",
                    target_url,
                    data={"List-Unsubscribe": "One-Click"},
                )
                # Si le serveur refuse le POST (405 Method Not Allowed), tenter un GET sécurisé
                if resp.status_code == 405:
                    resp = self._safe_request("GET", target_url)
            else:
                resp = self._safe_request("GET", target_url)

            if 200 <= resp.status_code < 300:
                return {
                    "success": True,
                    "method": "rfc8058_post" if unsub_info.one_click_post else "http_get",
                    "status_code": resp.status_code,
                    "message": f"Requête de désabonnement acceptée (HTTP {resp.status_code}).",
                }
            return {
                "success": False,
                "method": "http",
                "status_code": resp.status_code,
                "message": f"Le serveur distant a répondu HTTP {resp.status_code}. Une confirmation manuelle dans le navigateur peut être requise.",
            }
        except Exception as e:
            return {
                "success": False,
                "method": "http",
                "error": str(e),
                "message": f"Échec de la requête automatique : {e}",
            }

    def open_link_in_browser(self, unsub_info: UnsubscribeInfo) -> bool:
        """Ouvre le lien de désabonnement dans le navigateur par défaut après validation syntaxique."""
        target_url = unsub_info.primary_action_url
        if not target_url or not is_safe_url_syntax(target_url):
            return False
        try:
            webbrowser.open(target_url, new=2)
            return True
        except Exception:
            return False
