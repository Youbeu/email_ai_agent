"""
Client Email Universel (IMAP / SMTP) robuste, rapide et sécurisé.
- Utilise exclusivement les vrais UIDs IMAP (RFC 3501) pour éviter tout décalage lors des suppressions/restaurations.
- Découverte automatique des dossiers spéciaux (RFC 6154 : \\Trash, \\Drafts, \\Junk) compatible toutes langues (FR/EN) et fournisseurs.
- Lecture non destructive via BODY.PEEK[] (ne marque pas les emails non lus comme lus lors du scan).
- Opérations par lot (Batch UID COPY/STORE) pour des performances optimales.
"""
import os
import re
import email
from email.header import decode_header
from email.utils import parsedate_to_datetime, parseaddr
import imaplib
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from datetime import datetime, timedelta
from typing import List, Optional, Dict, Any, Tuple
from dataclasses import dataclass, field

# Taille max de sécurité pour l'analyse du corps
MAX_EMAIL_BODY_LENGTH = 15000

# Mois anglais requis par la grammaire IMAP RFC 3501 (indépendant de la locale OS)
IMAP_MONTHS = [
    "", "Jan", "Feb", "Mar", "Apr", "May", "Jun",
    "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"
]


@dataclass
class EmailMessageData:
    uid: str
    subject: str
    sender_name: str
    sender_email: str
    date_str: str
    date_obj: Optional[datetime]
    body_text: str
    body_html: str
    list_unsubscribe: str
    message_id: str
    references: str
    raw_message: Optional[email.message.Message] = None
    list_unsubscribe_post: str = ""
    reply_to: str = ""
    folder: str = "INBOX"


def decode_str(header_value: Optional[str]) -> str:
    """Décode les en-têtes email encodés selon RFC 2047."""
    if not header_value:
        return ""
    try:
        decoded_parts = decode_header(str(header_value))
        result = []
        for part, encoding in decoded_parts:
            if isinstance(part, bytes):
                enc = encoding or "utf-8"
                if enc.lower() in ("unknown-8bit", "default"):
                    enc = "utf-8"
                try:
                    result.append(part.decode(enc, errors="replace"))
                except LookupError:
                    result.append(part.decode("latin1", errors="replace"))
            else:
                result.append(str(part))
        return "".join(result).strip()
    except Exception:
        return str(header_value).strip()


def format_imap_date(dt: datetime) -> str:
    """Formate une date au format strict IMAP RFC 3501 (ex: 20-Oct-2026)."""
    return f"{dt.day:02d}-{IMAP_MONTHS[dt.month]}-{dt.year}"


class UniversalEmailClient:
    """Client IMAP et SMTP universel avec support UID natif et détection dynamique des dossiers."""

    def __init__(self, config: Dict[str, Any], env_email: Optional[str] = None, env_password: Optional[str] = None):
        self.config = config or {}
        self.email_address = (env_email or os.getenv("EMAIL_ADDRESS", "")).strip()
        self.password = (env_password or os.getenv("EMAIL_PASSWORD", "")).strip()
        self.imap_server = self.config.get("imap_server", "imap.gmail.com")
        self.imap_port = int(self.config.get("imap_port", 993))
        self.smtp_server = self.config.get("smtp_server", "smtp.gmail.com")
        self.smtp_port = int(self.config.get("smtp_port", 465))
        self.imap: Optional[imaplib.IMAP4_SSL] = None
        self._special_folders_cache: Dict[str, str] = {}

    def connect(self) -> bool:
        """Établit la connexion IMAP sécurisée."""
        if not self.email_address or not self.password:
            raise ValueError("EMAIL_ADDRESS ou EMAIL_PASSWORD manquant dans la configuration (.env)")

        try:
            self.imap = imaplib.IMAP4_SSL(self.imap_server, self.imap_port)
            # Nettoyage des espaces éventuels dans les mots de passe d'application Gmail (xxxx xxxx xxxx xxxx)
            clean_pwd = self.password.replace(" ", "") if "gmail" in self.imap_server.lower() else self.password
            try:
                self.imap.login(self.email_address, self.password)
            except imaplib.IMAP4.error:
                if clean_pwd != self.password:
                    self.imap.login(self.email_address, clean_pwd)
                else:
                    raise
            self._discover_special_folders()
            return True
        except Exception as e:
            self.imap = None
            raise ConnectionError(f"Échec de connexion IMAP ({self.imap_server}:{self.imap_port}) : {e}")

    def disconnect(self):
        """Ferme proprement la connexion IMAP."""
        if self.imap:
            try:
                self.imap.close()
            except Exception:
                pass
            try:
                self.imap.logout()
            except Exception:
                pass
            self.imap = None

    def _discover_special_folders(self):
        """Découvre dynamiquement les dossiers Spam, Corbeille et Brouillons via RFC 6154 (LIST)."""
        if not self.imap or self._special_folders_cache:
            return
        try:
            status, folders = self.imap.list()
            if status != "OK" or not folders:
                return

            for item in folders:
                if not isinstance(item, bytes):
                    continue
                line = item.decode("utf-8", errors="replace")
                # Format: (\HasNoChildren \Junk) "/" "[Gmail]/Spam"
                match = re.match(r'\((?P<flags>[^)]*)\)\s+(?:"[^"]*"|NIL)\s+(?P<name>.+)$', line)
                if not match:
                    continue
                flags = match.group("flags").lower()
                raw_name = match.group("name").strip().strip('"')

                if "\\junk" in flags or "\\spam" in flags or any(k in raw_name.lower() for k in ["spam", "junk", "courrier indésirable"]):
                    self._special_folders_cache.setdefault("spam", raw_name)
                if "\\trash" in flags or any(k in raw_name.lower() for k in ["trash", "corbeille", "deleted", "éléments supprimés"]):
                    self._special_folders_cache.setdefault("trash", raw_name)
                if "\\drafts" in flags or any(k in raw_name.lower() for k in ["drafts", "brouillons"]):
                    self._special_folders_cache.setdefault("drafts", raw_name)
        except Exception:
            pass

    def resolve_folder(self, role_or_name: str) -> str:
        """Résout un rôle ('spam', 'trash', 'drafts', 'inbox') ou un nom de dossier vers le vrai dossier IMAP."""
        key = (role_or_name or "INBOX").strip()
        lower = key.lower()

        if lower in ("inbox", "boîte de réception"):
            return "INBOX"
        if lower in ("spam", "[gmail]/spam", "junk"):
            return self._special_folders_cache.get("spam") or self.config.get("spam_folder", "[Gmail]/Spam")
        if lower in ("trash", "[gmail]/corbeille", "[gmail]/trash", "corbeille"):
            return self._special_folders_cache.get("trash") or self.config.get("trash_folder", "[Gmail]/Corbeille")
        if lower in ("drafts", "[gmail]/brouillons", "[gmail]/drafts", "brouillons"):
            return self._special_folders_cache.get("drafts") or self.config.get("drafts_folder", "[Gmail]/Brouillons")
        return key

    def _format_folder_name(self, folder: str) -> str:
        """Formate correctement le nom du dossier pour le protocole IMAP."""
        resolved = self.resolve_folder(folder)
        folder_clean = resolved.replace('"', "").strip()
        if folder_clean.upper() == "INBOX":
            return "INBOX"
        return f'"{folder_clean}"'

    def _select_folder(self, folder: str, readonly: bool = True) -> bool:
        """Sélectionne un dossier IMAP avec fallback intelligent."""
        if not self.imap:
            self.connect()

        candidates = [
            self._format_folder_name(folder),
            folder.replace('"', "").strip(),
        ]
        # Fallbacks multi-langues si Gmail
        lower = folder.lower()
        if "spam" in lower or "junk" in lower:
            candidates.extend(['"[Gmail]/Spam"', '"[Gmail]/Junk"', '"Spam"', '"Junk"'])
        elif "corbeille" in lower or "trash" in lower:
            candidates.extend(['"[Gmail]/Corbeille"', '"[Gmail]/Trash"', '"Trash"', '"Deleted Items"'])
        elif "brouillon" in lower or "draft" in lower:
            candidates.extend(['"[Gmail]/Brouillons"', '"[Gmail]/Drafts"', '"Drafts"'])

        seen = set()
        for cand in candidates:
            if not cand or cand in seen:
                continue
            seen.add(cand)
            try:
                status, _ = self.imap.select(cand, readonly=readonly)
                if status == "OK":
                    return True
            except Exception:
                continue
        return False

    def _extract_body(self, msg: email.message.Message) -> Tuple[str, str]:
        """Extrait le texte brut et le contenu HTML d'un message sans charger les pièces jointes."""
        body_text = ""
        body_html = ""

        if msg.is_multipart():
            for part in msg.walk():
                content_type = part.get_content_type()
                content_disposition = str(part.get("Content-Disposition", "")).lower()

                if "attachment" in content_disposition:
                    continue

                if content_type not in ("text/plain", "text/html"):
                    continue

                try:
                    payload = part.get_payload(decode=True)
                    if payload:
                        charset = part.get_content_charset() or "utf-8"
                        try:
                            text = payload.decode(charset, errors="replace")
                        except LookupError:
                            text = payload.decode("utf-8", errors="replace")
                        if content_type == "text/plain" and not body_text:
                            body_text = text
                        elif content_type == "text/html" and not body_html:
                            body_html = text
                except Exception:
                    pass
        else:
            try:
                payload = msg.get_payload(decode=True)
                if payload:
                    charset = msg.get_content_charset() or "utf-8"
                    try:
                        text = payload.decode(charset, errors="replace")
                    except LookupError:
                        text = payload.decode("utf-8", errors="replace")
                    if msg.get_content_type() == "text/html":
                        body_html = text
                    else:
                        body_text = text
            except Exception:
                pass

        if not body_text and body_html:
            clean_text = re.sub(r"<style.*?</style>", " ", body_html, flags=re.DOTALL | re.IGNORECASE)
            clean_text = re.sub(r"<script.*?</script>", " ", clean_text, flags=re.DOTALL | re.IGNORECASE)
            clean_text = re.sub(r"<[^>]+>", " ", clean_text)
            clean_text = re.sub(r"\s+", " ", clean_text)
            body_text = clean_text.strip()

        return body_text.strip()[:MAX_EMAIL_BODY_LENGTH], body_html.strip()

    def _parse_sender(self, from_header: str) -> Tuple[str, str]:
        """Extrait proprement (sender_name, sender_email) depuis un en-tête From."""
        decoded = decode_str(from_header)
        name, addr = parseaddr(decoded)
        addr = (addr or "").lower().strip()
        name = (name or "").strip().strip('"').strip("'")
        if not addr and "@" in decoded:
            addr = decoded.lower().strip()
        if not name:
            name = addr.split("@")[0] if "@" in addr else decoded
        return name, addr

    def fetch_emails(
        self,
        folder: str = "INBOX",
        unread_only: bool = False,
        since_days: int = 30,
        limit: int = 30,
    ) -> List[EmailMessageData]:
        """Récupère les emails par UID IMAP sans modifier leur état de lecture (BODY.PEEK)."""
        if not self._select_folder(folder, readonly=True):
            return []

        # Construction des critères IMAP
        criteria_parts = []
        if unread_only:
            criteria_parts.append("UNSEEN")
        if since_days and since_days > 0:
            since_dt = datetime.now() - timedelta(days=since_days)
            criteria_parts.append(f'SINCE {format_imap_date(since_dt)}')

        search_query = f"({' '.join(criteria_parts)})" if criteria_parts else "ALL"

        try:
            status, data = self.imap.uid("SEARCH", None, search_query)
        except Exception:
            # Fallback simple si le serveur IMAP refuse la combinaison
            fallback_query = "UNSEEN" if unread_only else "ALL"
            try:
                status, data = self.imap.uid("SEARCH", None, fallback_query)
            except Exception:
                return []

        if status != "OK" or not data or not data[0]:
            # Contrairement à l'ancien code bogué, si unread_only=True et qu'il n'y a rien,
            # on retourne [] au lieu de télécharger toute la boîte !
            # En revanche, si on avait un filtre SINCE trop restrictif avec unread_only=False, on tente ALL.
            if not unread_only and since_days > 0:
                try:
                    status, data = self.imap.uid("SEARCH", None, "ALL")
                except Exception:
                    return []
            if status != "OK" or not data or not data[0]:
                return []

        all_uids = [u.decode("utf-8") if isinstance(u, bytes) else str(u) for u in data[0].split()]
        if not all_uids:
            return []

        selected_uids = all_uids[-limit:] if limit > 0 else all_uids
        messages: List[EmailMessageData] = []
        resolved_folder = self.resolve_folder(folder)

        # Récupération en ordre antéchronologique (les plus récents en premier)
        for uid in reversed(selected_uids):
            try:
                # BODY.PEEK[] garantit qu'on ne marque jamais un email comme lu par erreur
                status, msg_data = self.imap.uid("FETCH", uid, "(BODY.PEEK[])")
                if status != "OK" or not msg_data:
                    continue

                raw_email = None
                for item in msg_data:
                    if isinstance(item, tuple) and len(item) >= 2 and isinstance(item[1], (bytes, bytearray)):
                        raw_email = item[1]
                        break

                if not raw_email:
                    continue

                msg = email.message_from_bytes(raw_email)

                subject = decode_str(msg.get("Subject", "(Sans objet)")) or "(Sans objet)"
                from_header = msg.get("From", "")
                reply_to_header = msg.get("Reply-To", "")
                date_str = decode_str(msg.get("Date", ""))
                list_unsub = decode_str(msg.get("List-Unsubscribe", ""))
                list_unsub_post = decode_str(msg.get("List-Unsubscribe-Post", ""))
                message_id = decode_str(msg.get("Message-ID", ""))
                references = decode_str(msg.get("References", "")) or message_id

                date_obj = None
                if date_str:
                    try:
                        date_obj = parsedate_to_datetime(date_str)
                    except Exception:
                        date_obj = None

                sender_name, sender_email = self._parse_sender(from_header)
                _, reply_to_email = self._parse_sender(reply_to_header) if reply_to_header else ("", "")

                body_text, body_html = self._extract_body(msg)

                messages.append(
                    EmailMessageData(
                        uid=str(uid),
                        subject=subject,
                        sender_name=sender_name,
                        sender_email=sender_email,
                        date_str=date_str,
                        date_obj=date_obj,
                        body_text=body_text,
                        body_html=body_html,
                        list_unsubscribe=list_unsub,
                        list_unsubscribe_post=list_unsub_post,
                        message_id=message_id,
                        references=references,
                        raw_message=msg,
                        reply_to=reply_to_email or sender_email,
                        folder=resolved_folder,
                    )
                )
            except Exception:
                continue

        return messages

    def fetch_spam_emails(self, limit: int = 50) -> List[EmailMessageData]:
        """Récupère les emails situés dans le dossier Spam ([Gmail]/Spam ou équivalent RFC 6154)."""
        spam_folder = self.resolve_folder("spam")
        return self.fetch_emails(folder=spam_folder, unread_only=False, since_days=0, limit=limit)

    def restore_to_inbox_batch(self, uids: List[str], from_folder: str = "[Gmail]/Spam") -> int:
        """Déplace un lot d'emails par UID du dossier Spam vers INBOX en une seule opération atomique."""
        clean_uids = [str(u).strip() for u in uids if str(u).strip().isdigit()]
        if not clean_uids:
            return 0

        if not self._select_folder(from_folder, readonly=False):
            return 0

        uid_set = ",".join(clean_uids)
        try:
            copy_status, _ = self.imap.uid("COPY", uid_set, "INBOX")
            if copy_status == "OK":
                self.imap.uid("STORE", uid_set, "+FLAGS", "(\\Deleted)")
                self.imap.expunge()
                return len(clean_uids)
        except Exception:
            pass

        # Fallback unitaire par UID (les UIDs ne changent pas après expunge contrairement aux sequence numbers)
        restored = 0
        for uid in clean_uids:
            try:
                copy_status, _ = self.imap.uid("COPY", uid, "INBOX")
                if copy_status == "OK":
                    self.imap.uid("STORE", uid, "+FLAGS", "(\\Deleted)")
                    restored += 1
            except Exception:
                continue
        if restored > 0:
            try:
                self.imap.expunge()
            except Exception:
                pass
        return restored

    def restore_to_inbox(self, uid: str, from_folder: str = "[Gmail]/Spam") -> bool:
        """Déplace un email du dossier Spam vers la boîte de réception principale (INBOX)."""
        return self.restore_to_inbox_batch([uid], from_folder=from_folder) > 0

    def move_to_trash_batch(self, uids: List[str], from_folder: str = "INBOX", dry_run: bool = False) -> int:
        """Déplace un lot d'emails par UID vers la corbeille en une seule opération IMAP."""
        clean_uids = [str(u).strip() for u in uids if str(u).strip().isdigit()]
        if not clean_uids:
            return 0
        if dry_run:
            return len(clean_uids)

        if not self._select_folder(from_folder, readonly=False):
            return 0

        trash_folder = self._format_folder_name("trash")
        uid_set = ",".join(clean_uids)

        try:
            copy_status, _ = self.imap.uid("COPY", uid_set, trash_folder)
            if copy_status == "OK":
                self.imap.uid("STORE", uid_set, "+FLAGS", "(\\Deleted)")
                self.imap.expunge()
                return len(clean_uids)
        except Exception:
            pass

        # Fallback unitaire par UID
        deleted = 0
        for uid in clean_uids:
            try:
                copy_status, _ = self.imap.uid("COPY", uid, trash_folder)
                if copy_status == "OK":
                    self.imap.uid("STORE", uid, "+FLAGS", "(\\Deleted)")
                    deleted += 1
                else:
                    self.imap.uid("STORE", uid, "+FLAGS", "(\\Deleted)")
                    deleted += 1
            except Exception:
                continue

        if deleted > 0:
            try:
                self.imap.expunge()
            except Exception:
                pass
        return deleted

    def move_to_trash(self, uid: str, from_folder: str = "INBOX", dry_run: bool = False) -> bool:
        """Déplace un email vers la corbeille Gmail/IMAP ou le supprime."""
        return self.move_to_trash_batch([uid], from_folder=from_folder, dry_run=dry_run) > 0

    def create_draft(
        self,
        original_msg: EmailMessageData,
        draft_body: str,
        draft_subject: str = "",
        dry_run: bool = False,
    ) -> bool:
        """Crée un brouillon de réponse rattaché au fil de discussion (In-Reply-To / References)."""
        if dry_run:
            return True

        if not self.imap:
            self.connect()

        recipient = original_msg.reply_to or original_msg.sender_email
        subj = draft_subject.strip() if draft_subject else f"Re: {original_msg.subject}"
        if not subj.lower().startswith("re:"):
            subj = f"Re: {subj}"

        msg = MIMEMultipart("alternative")
        msg["From"] = self.email_address
        msg["To"] = recipient
        msg["Subject"] = subj

        if original_msg.message_id:
            msg["In-Reply-To"] = original_msg.message_id
            refs = f"{original_msg.references or ''} {original_msg.message_id}".strip()
            msg["References"] = refs

        msg.attach(MIMEText(draft_body, "plain", "utf-8"))
        raw_msg = msg.as_bytes()
        internal_date = imaplib.Time2Internaldate(datetime.now())

        candidate_folders = [
            self._format_folder_name("drafts"),
            self._format_folder_name(self.config.get("drafts_folder", "[Gmail]/Brouillons")),
            '"[Gmail]/Brouillons"',
            '"[Gmail]/Drafts"',
            '"Drafts"',
        ]

        seen = set()
        for folder_name in candidate_folders:
            if not folder_name or folder_name in seen:
                continue
            seen.add(folder_name)
            try:
                status, _ = self.imap.append(folder_name, "(\\Draft \\Seen)", internal_date, raw_msg)
                if status == "OK":
                    return True
            except Exception:
                continue
        return False
