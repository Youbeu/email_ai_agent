"""
Client Email Universel (IMAP / SMTP) ultra-rapide et sécurisé.
Gère la Boîte de Réception, le dossier [Gmail]/Spam, la création de Brouillons,
la Restauration de spam vers INBOX et le déplacement vers la Corbeille.
"""
import os
import sys
import email
from email.header import decode_header
import imaplib
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from datetime import datetime, timedelta
from typing import List, Optional, Dict, Any, Tuple
from dataclasses import dataclass
import re

# Taille max de sécurité pour l'analyse
MAX_EMAIL_BODY_LENGTH = 15000


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


def decode_str(header_value: Optional[str]) -> str:
    """Décode les en-têtes email encodés selon RFC 2047."""
    if not header_value:
        return ""
    try:
        decoded_parts = decode_header(header_value)
        result = []
        for part, encoding in decoded_parts:
            if isinstance(part, bytes):
                try:
                    result.append(part.decode(encoding or "utf-8", errors="replace"))
                except Exception:
                    result.append(part.decode("latin1", errors="replace"))
            else:
                result.append(str(part))
        return "".join(result).strip()
    except Exception:
        return str(header_value).strip()


class UniversalEmailClient:
    """Client IMAP et SMTP universel avec support Gmail approfondi."""

    def __init__(self, config: Dict[str, Any], env_email: str = None, env_password: str = None):
        self.config = config
        self.email_address = env_email or os.getenv("EMAIL_ADDRESS", "")
        self.password = env_password or os.getenv("EMAIL_PASSWORD", "")
        self.imap_server = config.get("imap_server", "imap.gmail.com")
        self.imap_port = int(config.get("imap_port", 993))
        self.smtp_server = config.get("smtp_server", "smtp.gmail.com")
        self.smtp_port = int(config.get("smtp_port", 587))
        self.imap: Optional[imaplib.IMAP4_SSL] = None

    def connect(self) -> bool:
        """Établit la connexion IMAP sécurisée."""
        if not self.email_address or not self.password:
            raise ValueError("EMAIL_ADDRESS ou EMAIL_PASSWORD manquant dans .env")

        try:
            self.imap = imaplib.IMAP4_SSL(self.imap_server, self.imap_port)
            self.imap.login(self.email_address, self.password)
            return True
        except Exception as e:
            raise ConnectionError(f"Échec de connexion IMAP ({self.imap_server}:{self.imap_port}) : {e}")

    def disconnect(self):
        """Ferme proprement la connexion."""
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

    def _format_folder_name(self, folder: str) -> str:
        """Formate correctement le nom du dossier pour le protocole IMAP Gmail."""
        folder_clean = folder.replace('"', '').strip()
        return f'"{folder_clean}"'

    def _extract_body(self, msg: email.message.Message) -> Tuple[str, str]:
        """Extrait le texte brut et le contenu HTML d'un message."""
        body_text = ""
        body_html = ""

        if msg.is_multipart():
            for part in msg.walk():
                content_type = part.get_content_type()
                content_disposition = str(part.get("Content-Disposition", ""))

                if "attachment" in content_disposition:
                    continue

                try:
                    payload = part.get_payload(decode=True)
                    if payload:
                        charset = part.get_content_charset() or "utf-8"
                        text = payload.decode(charset, errors="replace")
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
                    text = payload.decode(charset, errors="replace")
                    if msg.get_content_type() == "text/html":
                        body_html = text
                    else:
                        body_text = text
            except Exception:
                pass

        if not body_text and body_html:
            clean_text = re.sub(r"<style.*?</style>", "", body_html, flags=re.DOTALL | re.IGNORECASE)
            clean_text = re.sub(r"<script.*?</script>", "", clean_text, flags=re.DOTALL | re.IGNORECASE)
            clean_text = re.sub(r"<[^>]+>", " ", clean_text)
            clean_text = re.sub(r"\s+", " ", clean_text)
            body_text = clean_text.strip()

        return body_text.strip()[:MAX_EMAIL_BODY_LENGTH], body_html.strip()

    def fetch_emails(
        self,
        folder: str = "INBOX",
        unread_only: bool = False,
        since_days: int = 30,
        limit: int = 30,
    ) -> List[EmailMessageData]:
        """Récupère les emails correspondant aux critères avec support des dossiers spéciaux."""
        if not self.imap:
            self.connect()

        folder_arg = self._format_folder_name(folder)
        status, _ = self.imap.select(folder_arg, readonly=True)
        if status != "OK":
            # Essai sans guillemets si échec
            status, _ = self.imap.select(folder.replace('"', ''), readonly=True)
            if status != "OK":
                return []

        # Recherche des emails
        data = None
        if unread_only:
            try:
                status, data = self.imap.search(None, "UNSEEN")
            except Exception:
                status = "ERROR"

        if not unread_only or not data or not data[0]:
            try:
                status, data = self.imap.search(None, "ALL")
            except Exception:
                return []

        if not data or not data[0]:
            return []

        message_numbers = data[0].split()
        selected_numbers = message_numbers[-limit:]
        messages: List[EmailMessageData] = []

        for num in reversed(selected_numbers):
            try:
                status, msg_data = self.imap.fetch(num, "(RFC822)")
                if status != "OK" or not msg_data:
                    continue

                raw_email = msg_data[0][1]
                msg = email.message_from_bytes(raw_email)

                subject = decode_str(msg.get("Subject", "(Sans objet)"))
                from_header = decode_str(msg.get("From", ""))
                date_str = msg.get("Date", "")
                list_unsub = msg.get("List-Unsubscribe", "")
                message_id = msg.get("Message-ID", "")
                references = msg.get("References", "") or message_id

                sender_email = ""
                sender_name = from_header
                email_match = re.search(r"<([^>]+)>", from_header)
                if email_match:
                    sender_email = email_match.group(1).lower().strip()
                    sender_name = from_header.split("<")[0].strip().replace('"', '')
                else:
                    sender_email = from_header.lower().strip()

                body_text, body_html = self._extract_body(msg)

                messages.append(
                    EmailMessageData(
                        uid=num.decode("utf-8") if isinstance(num, bytes) else str(num),
                        subject=subject,
                        sender_name=sender_name or sender_email,
                        sender_email=sender_email,
                        date_str=date_str,
                        date_obj=None,
                        body_text=body_text,
                        body_html=body_html,
                        list_unsubscribe=list_unsub,
                        message_id=message_id,
                        references=references,
                        raw_message=msg,
                    )
                )
            except Exception:
                continue

        return messages

    def fetch_spam_emails(self, limit: int = 50) -> List[EmailMessageData]:
        """Récupère l'intégralité des emails situés dans le dossier [Gmail]/Spam."""
        return self.fetch_emails(folder="[Gmail]/Spam", unread_only=False, limit=limit)

    def restore_to_inbox(self, uid: str, from_folder: str = "[Gmail]/Spam") -> bool:
        """Déplace un email du dossier Spam vers la boîte de réception principale (INBOX)."""
        if not self.imap:
            self.connect()

        folder_arg = self._format_folder_name(from_folder)
        try:
            self.imap.select(folder_arg)
            # Copier vers INBOX
            copy_status, _ = self.imap.copy(uid, "INBOX")
            if copy_status == "OK":
                self.imap.store(uid, "+FLAGS", "\\Deleted")
                self.imap.expunge()
                return True
        except Exception:
            pass
        return False

    def move_to_trash(self, uid: str, from_folder: str = "INBOX", dry_run: bool = False) -> bool:
        """Déplace un email vers la corbeille Gmail ou le supprime."""
        if dry_run:
            return True
        if not self.imap:
            self.connect()

        folder_arg = self._format_folder_name(from_folder)
        try:
            self.imap.select(folder_arg)
            trash_folder = self._format_folder_name(self.config.get("trash_folder", "[Gmail]/Corbeille"))
            copy_status, _ = self.imap.copy(uid, trash_folder)
            if copy_status == "OK":
                self.imap.store(uid, "+FLAGS", "\\Deleted")
                self.imap.expunge()
                return True
            else:
                self.imap.store(uid, "+FLAGS", "\\Deleted")
                self.imap.expunge()
                return True
        except Exception:
            return False

    def create_draft(
        self,
        original_msg: EmailMessageData,
        draft_body: str,
        draft_subject: str = "",
        dry_run: bool = False,
    ) -> bool:
        """Crée un brouillon de réponse dans le dossier [Gmail]/Brouillons."""
        if dry_run:
            return True

        if not self.imap:
            self.connect()

        msg = MIMEMultipart("alternative")
        msg["From"] = self.email_address
        msg["To"] = original_msg.sender_email
        msg["Subject"] = draft_subject or f"Re: {original_msg.subject}"

        if original_msg.message_id:
            msg["In-Reply-To"] = original_msg.message_id
            msg["References"] = f"{original_msg.references} {original_msg.message_id}".strip()

        msg.attach(MIMEText(draft_body, "plain", "utf-8"))

        drafts_folder = self._format_folder_name(self.config.get("drafts_folder", "[Gmail]/Brouillons"))
        try:
            raw_msg = msg.as_bytes()
            status, _ = self.imap.append(
                drafts_folder,
                "(\\Draft \\Seen)",
                imaplib.Time2Internaldate(datetime.now()),
                raw_msg,
            )
            return status == "OK"
        except Exception:
            # Essai avec le nom simple "Drafts"
            try:
                status, _ = self.imap.append(
                    '"Drafts"',
                    "(\\Draft \\Seen)",
                    imaplib.Time2Internaldate(datetime.now()),
                    msg.as_bytes(),
                )
                return status == "OK"
            except Exception:
                return False
