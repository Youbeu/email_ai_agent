"""
Persistance et cache local SQLite pour Email AI Agent.
Permet :
1. De conserver les métadonnées de fil de discussion (Message-ID, References, Reply-To) pour attacher les brouillons aux threads Gmail.
2. D'éviter de recalculer l'analyse LLM pour les emails déjà analysés lors des scans successifs.
3. De charger instantanément la dernière vue connue tout en rafraîchissant en arrière-plan.
"""
import os
import json
import sqlite3
import threading
import time
from typing import Dict, Any, List, Optional
from core.email_client import EmailMessageData


class LocalEmailStore:
    def __init__(self, db_path: Optional[str] = None):
        if not db_path:
            base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
            db_path = os.path.join(base_dir, "email_agent_cache.db")
        self.db_path = db_path
        self._lock = threading.Lock()
        self._init_db()

    def _get_conn(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path, timeout=10.0, check_same_thread=False)
        conn.row_factory = sqlite3.Row
        return conn

    def _init_db(self):
        with self._lock:
            conn = self._get_conn()
            try:
                conn.execute(
                    """
                    CREATE TABLE IF NOT EXISTS cached_emails (
                        folder TEXT NOT NULL,
                        uid TEXT NOT NULL,
                        message_id TEXT,
                        references_hdr TEXT,
                        reply_to TEXT,
                        sender_name TEXT,
                        sender_email TEXT,
                        subject TEXT,
                        date_str TEXT,
                        body_text TEXT,
                        category TEXT,
                        category_label TEXT,
                        summary TEXT,
                        needs_draft INTEGER DEFAULT 0,
                        spam_score REAL DEFAULT 0.0,
                        is_false_positive INTEGER DEFAULT 0,
                        has_unsubscribe INTEGER DEFAULT 0,
                        unsubscribe_url TEXT,
                        supports_one_click INTEGER DEFAULT 0,
                        unsubscribe_mailto TEXT,
                        draft_json TEXT,
                        updated_at REAL,
                        PRIMARY KEY (folder, uid)
                    )
                    """
                )
                conn.commit()
            finally:
                conn.close()

    def get_cached_email(self, folder: str, uid: str) -> Optional[Dict[str, Any]]:
        norm_folder = folder.lower().strip()
        with self._lock:
            conn = self._get_conn()
            try:
                row = conn.execute(
                    "SELECT * FROM cached_emails WHERE folder = ? AND uid = ?",
                    (norm_folder, str(uid)),
                ).fetchone()
                if not row:
                    return None
                return self._row_to_dict(row)
            finally:
                conn.close()

    def upsert_email_record(self, folder: str, record: Dict[str, Any]):
        norm_folder = folder.lower().strip()
        draft_json = json.dumps(record.get("draft")) if record.get("draft") else None
        with self._lock:
            conn = self._get_conn()
            try:
                conn.execute(
                    """
                    INSERT INTO cached_emails (
                        folder, uid, message_id, references_hdr, reply_to,
                        sender_name, sender_email, subject, date_str, body_text,
                        category, category_label, summary, needs_draft, spam_score,
                        is_false_positive, has_unsubscribe, unsubscribe_url,
                        supports_one_click, unsubscribe_mailto, draft_json, updated_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    ON CONFLICT(folder, uid) DO UPDATE SET
                        message_id=excluded.message_id,
                        references_hdr=excluded.references_hdr,
                        reply_to=excluded.reply_to,
                        sender_name=excluded.sender_name,
                        sender_email=excluded.sender_email,
                        subject=excluded.subject,
                        date_str=excluded.date_str,
                        body_text=excluded.body_text,
                        category=excluded.category,
                        category_label=excluded.category_label,
                        summary=excluded.summary,
                        needs_draft=excluded.needs_draft,
                        spam_score=excluded.spam_score,
                        is_false_positive=excluded.is_false_positive,
                        has_unsubscribe=excluded.has_unsubscribe,
                        unsubscribe_url=excluded.unsubscribe_url,
                        supports_one_click=excluded.supports_one_click,
                        unsubscribe_mailto=excluded.unsubscribe_mailto,
                        draft_json=excluded.draft_json,
                        updated_at=excluded.updated_at
                    """,
                    (
                        norm_folder,
                        str(record["uid"]),
                        record.get("message_id", ""),
                        record.get("references", ""),
                        record.get("reply_to", ""),
                        record.get("sender_name", ""),
                        record.get("sender_email", ""),
                        record.get("subject", ""),
                        record.get("date", ""),
                        record.get("body_text", ""),
                        record.get("category", "A_TRAITER"),
                        record.get("category_label", ""),
                        record.get("summary", ""),
                        1 if record.get("needs_draft") else 0,
                        float(record.get("spam_score", 0.0)),
                        1 if record.get("is_false_positive") else 0,
                        1 if record.get("has_unsubscribe") else 0,
                        record.get("unsubscribe_url"),
                        1 if record.get("supports_one_click") else 0,
                        record.get("unsubscribe_mailto"),
                        draft_json,
                        time.time(),
                    ),
                )
                conn.commit()
            finally:
                conn.close()

    def update_draft(self, folder: str, uid: str, draft: Dict[str, str]):
        norm_folder = folder.lower().strip()
        with self._lock:
            conn = self._get_conn()
            try:
                conn.execute(
                    "UPDATE cached_emails SET draft_json = ?, updated_at = ? WHERE folder = ? AND uid = ?",
                    (json.dumps(draft), time.time(), norm_folder, str(uid)),
                )
                conn.commit()
            finally:
                conn.close()

    def delete_cached_uids(self, folder: str, uids: List[str]):
        if not uids:
            return
        norm_folder = folder.lower().strip()
        placeholders = ",".join("?" for _ in uids)
        params = [norm_folder] + [str(u) for u in uids]
        with self._lock:
            conn = self._get_conn()
            try:
                conn.execute(
                    f"DELETE FROM cached_emails WHERE folder = ? AND uid IN ({placeholders})",
                    params,
                )
                conn.commit()
            finally:
                conn.close()

    def list_cached_emails(self, folder: str, limit: int = 50) -> List[Dict[str, Any]]:
        norm_folder = folder.lower().strip()
        with self._lock:
            conn = self._get_conn()
            try:
                rows = conn.execute(
                    "SELECT * FROM cached_emails WHERE folder = ? ORDER BY CAST(uid AS INTEGER) DESC LIMIT ?",
                    (norm_folder, limit),
                ).fetchall()
                return [self._row_to_dict(r) for r in rows]
            finally:
                conn.close()

    @staticmethod
    def _row_to_dict(row: sqlite3.Row) -> Dict[str, Any]:
        draft = None
        if row["draft_json"]:
            try:
                draft = json.loads(row["draft_json"])
            except Exception:
                draft = None
        body_text = row["body_text"] or ""
        return {
            "uid": str(row["uid"]),
            "folder": row["folder"],
            "message_id": row["message_id"] or "",
            "references": row["references_hdr"] or "",
            "reply_to": row["reply_to"] or row["sender_email"] or "",
            "sender_name": row["sender_name"] or "",
            "sender_email": row["sender_email"] or "",
            "subject": row["subject"] or "",
            "date": row["date_str"] or "",
            "body_text": body_text,
            "snippet": body_text[:220] if body_text else (row["subject"] or ""),
            "category": row["category"] or "A_TRAITER",
            "category_label": row["category_label"] or row["category"] or "A_TRAITER",
            "summary": row["summary"] or "",
            "needs_draft": bool(row["needs_draft"]),
            "spam_score": float(row["spam_score"] or 0.0),
            "is_false_positive": bool(row["is_false_positive"]),
            "has_unsubscribe": bool(row["has_unsubscribe"]),
            "unsubscribe_url": row["unsubscribe_url"],
            "supports_one_click": bool(row["supports_one_click"]),
            "unsubscribe_mailto": row["unsubscribe_mailto"],
            "draft": draft,
        }
