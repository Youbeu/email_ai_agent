"""
Module d'audit de boîte mail et de nettoyage ciblé des spams et newsletters récurrentes.
"""
from typing import List, Dict, Any, Optional
from collections import defaultdict
from core.email_client import UniversalEmailClient, EmailMessageData
from core.unsubscriber import Unsubscriber, UnsubscribeInfo


class SenderAuditInfo:
    def __init__(self, sender_email: str, sender_name: str):
        self.sender_email = sender_email
        self.sender_name = sender_name
        self.count = 0
        self.uids: List[str] = []
        self.sample_subjects: List[str] = []
        self.latest_date: str = ""
        self.unsubscribe_info: Optional[UnsubscribeInfo] = None

    def add_email(self, email_data: EmailMessageData, unsub_info: UnsubscribeInfo):
        self.count += 1
        self.uids.append(email_data.uid)
        if len(self.sample_subjects) < 3 and email_data.subject not in self.sample_subjects:
            self.sample_subjects.append(email_data.subject)
        if not self.latest_date:
            self.latest_date = email_data.date_str
        if unsub_info.has_unsubscribe and not self.unsubscribe_info:
            self.unsubscribe_info = unsub_info


class SpamCleaner:
    def __init__(self, email_client: UniversalEmailClient, unsubscriber: Optional[Unsubscriber] = None):
        self.client = email_client
        self.unsubscriber = unsubscriber or Unsubscriber()

    def audit_inbox(self, limit: int = 150) -> List[SenderAuditInfo]:
        """
        Scanne la boîte de réception pour regrouper les emails par expéditeur et identifier les newsletters/spams.
        """
        emails = self.client.fetch_emails(folder="INBOX", unread_only=False, since_days=30, limit=limit)
        senders_map: Dict[str, SenderAuditInfo] = {}

        for em in emails:
            key = em.sender_email.lower().strip()
            if not key:
                continue

            if key not in senders_map:
                senders_map[key] = SenderAuditInfo(sender_email=em.sender_email, sender_name=em.sender_name)

            unsub_info = self.unsubscriber.detect(em)
            senders_map[key].add_email(em, unsub_info)

        # Filtrer et trier par nombre d'emails décroissant
        sorted_senders = sorted(senders_map.values(), key=lambda s: s.count, reverse=True)
        return sorted_senders

    def clean_sender_emails(self, sender_info: SenderAuditInfo, dry_run: bool = False) -> int:
        """
        Supprime / Déplace vers la corbeille tous les emails d'un expéditeur donné.
        """
        deleted_count = 0
        for uid in sender_info.uids:
            if self.client.move_to_trash(uid, dry_run=dry_run):
                deleted_count += 1
        return deleted_count
