"""
Client Email universel IMAP/SMTP pour la lecture, le tri et la création de brouillons.
"""
import imaplib
import smtplib
import email
from email.header import decode_header
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from datetime import datetime, timedelta
from typing import List, Dict, Any, Optional
import time
import os
import re


def decode_str(header_value: Optional[str]) -> str:
    """Décode les en-têtes d'email encodés (ex: UTF-8, ISO-8859-1)."""
    if not header_value:
        return ""
    try:
        decoded_fragments = decode_header(header_value)
        result = []
        for fragment, encoding in decoded_fragments:
            if isinstance(fragment, bytes):
                if encoding:
                    try:
                        result.append(fragment.decode(encoding, errors="replace"))
                    except LookupError:
                        result.append(fragment.decode("utf-8", errors="replace"))
                else:
                    result.append(fragment.decode("utf-8", errors="replace"))
            else:
                result.append(str(fragment))
        return "".join(result)
    except Exception:
        return str(header_value)


class EmailMessageData:
    def __init__(
        self,
        uid: str,
        subject: str,
        sender_name: str,
        sender_email: str,
        date_str: str,
        date_obj: Optional[datetime],
        body_text: str,
        body_html: str,
        list_unsubscribe: str,
        message_id: str,
        references: str,
        raw_message: email.message.Message,
    ):
        self.uid = uid
        self.subject = subject
        self.sender_name = sender_name
        self.sender_email = sender_email
        self.date_str = date_str
        self.date_obj = date_obj
        self.body_text = body_text
        self.body_html = body_html
        self.list_unsubscribe = list_unsubscribe
        self.message_id = message_id
        self.references = references
        self.raw_message = raw_message

    def to_dict(self) -> Dict[str, Any]:
        return {
            "uid": self.uid,
            "subject": self.subject,
            "sender_name": self.sender_name,
            "sender_email": self.sender_email,
            "date": self.date_str,
            "snippet": self.body_text[:200].strip(),
            "has_unsubscribe": bool(self.list_unsubscribe),
            "list_unsubscribe": self.list_unsubscribe,
        }


class UniversalEmailClient:
    def __init__(self, config: Dict[str, Any], env_email: Optional[str] = None, env_password: Optional[str] = None):
        self.config = config
        self.email_address = env_email or os.getenv("EMAIL_ADDRESS", "")
        self.password = env_password or os.getenv("EMAIL_PASSWORD", "")
        self.imap_server = config.get("imap_server", "imap.gmail.com")
        self.imap_port = config.get("imap_port", 993)
        self.smtp_server = config.get("smtp_server", "smtp.gmail.com")
        self.smtp_port = config.get("smtp_port", 465)
        self.drafts_folder = config.get("drafts_folder", "[Gmail]/Brouillons")
        self.trash_folder = config.get("trash_folder", "[Gmail]/Corbeille")
        self.imap: Optional[imaplib.IMAP4_SSL] = None

    def connect(self) -> bool:
        """Établit la connexion IMAP sécurisée."""
        if not self.email_address or not self.password:
            raise ValueError("EMAIL_ADDRESS ou EMAIL_PASSWORD manquant dans l'environnement ou le fichier .env")

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

    def _extract_body(self, msg: email.message.Message) -> tuple[str, str]:
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

        # Si seul le HTML est disponible, créer une version texte nettoyée simple
        if not body_text and body_html:
            clean_text = re.sub(r"<style.*?</style>", "", body_html, flags=re.DOTALL | re.IGNORECASE)
            clean_text = re.sub(r"<script.*?</script>", "", clean_text, flags=re.DOTALL | re.IGNORECASE)
            clean_text = re.sub(r"<[^>]+>", " ", clean_text)
            clean_text = re.sub(r"\s+", " ", clean_text)
            body_text = clean_text.strip()

        return body_text.strip(), body_html.strip()

    def fetch_emails(
        self,
        folder: str = "INBOX",
        unread_only: bool = True,
        since_days: int = 7,
        limit: int = 15,
    ) -> List[EmailMessageData]:
        """Récupère les emails correspondant aux critères de manière ultra-rapide."""
        if not self.imap:
            self.connect()

        self.imap.select(folder, readonly=True)

        # Recherche optimisée
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

                # Extraction nom et email
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
                        uid=num.decode("utf-8", errors="ignore"),
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
            except Exception as e:
                continue

        return messages

    def create_draft(
        self,
        original_msg: EmailMessageData,
        draft_body: str,
        draft_subject: Optional[str] = None,
        dry_run: bool = False,
    ) -> bool:
        """Crée un brouillon de réponse dans le dossier Brouillons du compte."""
        if dry_run:
            return True

        if not self.imap:
            self.connect()

        try:
            subject = draft_subject or f"Re: {original_msg.subject}"
            if not subject.lower().startswith("re:"):
                subject = f"Re: {subject}"

            msg = MIMEMultipart()
            msg["From"] = self.email_address
            msg["To"] = original_msg.sender_email
            msg["Subject"] = subject
            msg["Date"] = email.utils.formatdate(localtime=True)

            if original_msg.message_id:
                msg["In-Reply-To"] = original_msg.message_id
                refs = f"{original_msg.references} {original_msg.message_id}".strip()
                msg["References"] = refs

            msg.attach(MIMEText(draft_body, "plain", "utf-8"))

            # Sélectionner le dossier des brouillons ou tenter de le localiser
            drafts_folder = self._find_drafts_folder()
            
            # Utiliser APPEND pour injecter le message avec le flag \Draft
            raw_bytes = msg.as_bytes()
            now = imaplib.Time2Internaldate(time.time())
            flags = "(\\Draft \\Seen)"

            status, _ = self.imap.append(drafts_folder, flags, now, raw_bytes)
            return status == "OK"
        except Exception as e:
            print(f"[Avertissement] Erreur lors de la création du brouillon : {e}")
            return False

    def _find_drafts_folder(self) -> str:
        """Détecte le nom exact du dossier Brouillons sur le serveur IMAP."""
        if not self.imap:
            self.connect()

        # Essai avec le dossier configuré
        configured = self.config.get("drafts_folder", "[Gmail]/Brouillons")
        try:
            status, _ = self.imap.select(f'"{configured}"', readonly=True)
            if status == "OK":
                return f'"{configured}"'
        except Exception:
            pass

        # Recherche dans la liste des dossiers
        status, folder_list = self.imap.list()
        if status == "OK" and folder_list:
            for item in folder_list:
                item_str = item.decode("utf-8", errors="ignore")
                # Recherche des noms communs
                for candidate in ["\\Drafts", "Drafts", "Brouillons", "[Gmail]/Brouillons", "[Gmail]/Drafts"]:
                    if candidate.lower() in item_str.lower():
                        # Extraction du nom du dossier
                        parts = item_str.split(' "/" ')
                        if len(parts) > 1:
                            return parts[-1].strip()
                        parts_space = item_str.split(' "')
                        if len(parts_space) > 1:
                            folder_name = parts_space[-1].rstrip('"')
                            return f'"{folder_name}"'

        return '"Drafts"'

    def _find_spam_folder(self) -> str:
        """Détecte le nom exact du dossier Spam sur le serveur IMAP."""
        if not self.imap:
            self.connect()

        configured = self.config.get("spam_folder", "[Gmail]/Spam")
        try:
            status, _ = self.imap.select(f'"{configured}"', readonly=True)
            if status == "OK":
                return f'"{configured}"'
        except Exception:
            pass

        status, folder_list = self.imap.list()
        if status == "OK" and folder_list:
            for item in folder_list:
                item_str = item.decode("utf-8", errors="ignore")
                for candidate in ["\\Junk", "Spam", "[Gmail]/Spam", "[Gmail]/Pourriel", "Junk Email", "Junk"]:
                    if candidate.lower() in item_str.lower():
                        parts = item_str.split(' "/" ')
                        if len(parts) > 1:
                            return parts[-1].strip()
                        parts_space = item_str.split(' "')
                        if len(parts_space) > 1:
                            folder_name = parts_space[-1].rstrip('"')
                            return f'"{folder_name}"'

        return '"[Gmail]/Spam"'

    def fetch_spam_emails(self, limit: int = 25) -> List[EmailMessageData]:
        """Récupère les emails situés dans le dossier Spam."""
        spam_folder = self._find_spam_folder().replace('"', '')
        return self.fetch_emails(folder=spam_folder, unread_only=False, limit=limit)

    def restore_to_inbox(self, uid: str, from_folder: Optional[str] = None) -> bool:
        """Déplace un email du dossier Spam vers la boîte de réception (INBOX)."""
        if not self.imap:
            self.connect()

        folder = from_folder or self._find_spam_folder()
        try:
            self.imap.select(folder)
            copy_status, _ = self.imap.copy(uid, "INBOX")
            if copy_status == "OK":
                self.imap.store(uid, "+FLAGS", "\\Deleted")
                self.imap.expunge()
                return True
        except Exception as e:
            pass
        return False

    def move_to_trash(self, uid: str, from_folder: str = "INBOX", dry_run: bool = False) -> bool:
        """Déplace un email vers la corbeille ou le marque pour suppression."""
        if dry_run:
            return True
        if not self.imap:
            self.connect()
        try:
            self.imap.select(from_folder)
            trash_folder = self.config.get("trash_folder", "[Gmail]/Corbeille")
            copy_status, _ = self.imap.copy(uid, trash_folder)
            if copy_status == "OK":
                self.imap.store(uid, "+FLAGS", "\\Deleted")
                self.imap.expunge()
                return True
            else:
                self.imap.store(uid, "+FLAGS", "\\Deleted")
                self.imap.expunge()
                return True
        except Exception as e:
            return False
