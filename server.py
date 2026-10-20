"""
Serveur API FastAPI pour l'application Desktop Email AI Agent.
Architecture propre, sécurisée et persistante :
- Aucun chemin personnel codé en dur
- Cache SQLite local pour le threading des brouillons (In-Reply-To / References) et la rapidité
- Génération et régénération de brouillons IA à la demande avec instructions personnalisées
- Opérations IMAP par lot (Batch UID) pour la restauration de faux positifs et la suppression de spams
"""
import os
import sys
import time
from collections import deque
from typing import Dict, Any, List, Optional, Deque
from fastapi import FastAPI, HTTPException, Query
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import uvicorn
import yaml
from dotenv import load_dotenv

# Résolution propre des répertoires de l'application (Code source ou Exécutable PyInstaller)
if getattr(sys, "frozen", False):
    EXEC_DIR = os.path.dirname(sys.executable)
    BUNDLE_DIR = getattr(sys, "_MEIPASS", EXEC_DIR)
else:
    EXEC_DIR = os.path.dirname(os.path.abspath(__file__))
    BUNDLE_DIR = EXEC_DIR

if EXEC_DIR not in sys.path:
    sys.path.insert(0, EXEC_DIR)


def get_env_file_path() -> str:
    """Retourne le chemin du fichier .env actif."""
    for candidate in [
        os.path.join(EXEC_DIR, ".env"),
        os.path.join(BUNDLE_DIR, ".env"),
    ]:
        if os.path.exists(candidate):
            return candidate
    return os.path.join(EXEC_DIR, ".env")


def get_config_file_path() -> str:
    """Retourne le chemin du fichier config.yaml actif."""
    for candidate in [
        os.path.join(EXEC_DIR, "config.yaml"),
        os.path.join(BUNDLE_DIR, "config.yaml"),
    ]:
        if os.path.exists(candidate):
            return candidate
    return os.path.join(EXEC_DIR, "config.yaml")


# Chargement initial du .env
load_dotenv(get_env_file_path(), override=True)

from core.email_client import UniversalEmailClient, EmailMessageData
from core.ai_brain import AIBrain
from core.unsubscriber import Unsubscriber, UnsubscribeInfo
from core.spam_cleaner import SpamCleaner
from core.database import LocalEmailStore

app = FastAPI(title="Email AI Agent Desktop API", version="2.0.0")

# Restriction CORS stricte aux origines locales uniquement (empêche les sites web tiers d'interroger l'API locale)
app.add_middleware(
    CORSMiddleware,
    allow_origin_regex=r"^https?://(127\.0\.0\.1|localhost)(:\d+)?$",
    allow_credentials=True,
    allow_methods=["GET", "POST", "OPTIONS"],
    allow_headers=["*"],
)

# Répertoire des fichiers statiques
STATIC_DIR = os.path.join(BUNDLE_DIR, "static")
if not os.path.exists(STATIC_DIR):
    STATIC_DIR = os.path.join(EXEC_DIR, "static")
os.makedirs(STATIC_DIR, exist_ok=True)

# Instance de persistance SQLite locale
store = LocalEmailStore(os.path.join(EXEC_DIR, "email_agent_cache.db"))

# Journal d'activité en temps réel de l'Agent (conservé en mémoire pour le Poste de Pilotage)
AGENT_LOGS: Deque[Dict[str, str]] = deque(maxlen=120)


def log_agent_event(message: str, level: str = "info"):
    AGENT_LOGS.appendleft({
        "time": time.strftime("%H:%M:%S"),
        "level": level,
        "message": message,
    })


log_agent_event("Serveur Email AI Agent v2.0 initialisé et prêt.", "success")


def get_config() -> Dict[str, Any]:
    cfg_path = get_config_file_path()
    if os.path.exists(cfg_path):
        try:
            with open(cfg_path, "r", encoding="utf-8") as f:
                return yaml.safe_load(f) or {}
        except Exception:
            return {}
    return {}


def save_config(cfg_data: Dict[str, Any]):
    cfg_path = os.path.join(EXEC_DIR, "config.yaml")
    with open(cfg_path, "w", encoding="utf-8") as f:
        yaml.safe_dump(cfg_data, f, allow_unicode=True, sort_keys=False, default_flow_style=False)


# =========================================================
# Modèles Pydantic
# =========================================================

class SaveDraftRequest(BaseModel):
    uid: str
    folder: str = "inbox"
    recipient: str
    subject: str
    body: str
    message_id: Optional[str] = None
    references: Optional[str] = None


class GenerateDraftRequest(BaseModel):
    uid: str
    folder: str = "inbox"
    custom_instruction: str = ""
    subject: Optional[str] = None
    sender_name: Optional[str] = None
    sender_email: Optional[str] = None
    body_text: Optional[str] = None


class RestoreSpamRequest(BaseModel):
    uid: str
    folder: Optional[str] = "[Gmail]/Spam"


class RestoreMultipleSpamRequest(BaseModel):
    uids: List[str]
    folder: Optional[str] = "[Gmail]/Spam"


class UnsubscribeRequest(BaseModel):
    url: Optional[str] = None
    one_click: bool = False
    mailto: Optional[str] = None
    sender_email: Optional[str] = None


class DeleteSpamRequest(BaseModel):
    sender_email: Optional[str] = None
    uids: List[str]
    folder: str = "INBOX"


class SettingsUpdateRequest(BaseModel):
    email_address: str
    email_password: Optional[str] = None
    ai_provider: str = "ollama"
    ai_model: Optional[str] = None
    gemini_key: Optional[str] = None
    openai_key: Optional[str] = None
    anthropic_key: Optional[str] = None
    tone: str = "professionnel, bienveillant, clair et concis"
    signature: str = "Cordialement,\n[Votre Nom]"


class AgentRoutineRequest(BaseModel):
    limit: int = 20
    unread_only: bool = True
    sync_drafts_to_imap: bool = False


# =========================================================
# Routes API
# =========================================================

@app.get("/api/status")
def get_status():
    load_dotenv(get_env_file_path(), override=True)
    config = get_config()
    ai_brain = AIBrain(config)

    email_addr = os.getenv("EMAIL_ADDRESS", "").strip()
    has_pwd = bool(os.getenv("EMAIL_PASSWORD", "").strip())
    ai_cfg = config.get("ai", {})

    cached_inbox = store.list_cached_emails("inbox", limit=100)
    cached_spam = store.list_cached_emails("spam", limit=100)

    return {
        "is_configured": bool(email_addr and has_pwd),
        "email_address": email_addr,
        "has_password": has_pwd,
        "ai_provider": ai_cfg.get("provider", "ollama"),
        "ai_model": ai_cfg.get("model", "qwen2.5-coder:7b"),
        "ai_active_label": ai_brain.get_active_engine_label(),
        "ai_available": ai_brain.is_ai_available(),
        "has_gemini_key": bool(os.getenv("GEMINI_API_KEY", "").strip()),
        "has_openai_key": bool(os.getenv("OPENAI_API_KEY", "").strip()),
        "has_anthropic_key": bool(os.getenv("ANTHROPIC_API_KEY", "").strip()),
        "tone": ai_brain.tone,
        "signature": ai_brain.signature,
        "cached_inbox_count": len(cached_inbox),
        "cached_spam_count": len(cached_spam),
        "app_version": "2.0.0",
    }


@app.get("/api/emails/cached")
def get_cached_emails(
    folder: str = Query("inbox", description="Dossier : inbox ou spam"),
    limit: int = Query(50, description="Nombre max d'emails en cache"),
):
    norm_folder = "spam" if folder.lower() == "spam" else "inbox"
    items = store.list_cached_emails(norm_folder, limit=limit)
    return {
        "is_cached": True,
        "folder": norm_folder,
        "total_scanned": len(items),
        "emails": items,
    }


@app.get("/api/emails/scan")
def scan_emails(
    folder: str = Query("inbox", description="Dossier : inbox ou spam"),
    limit: int = Query(25, description="Nombre d'emails à récupérer"),
    unread_only: bool = Query(False, description="Uniquement les emails non lus"),
    force_refresh: bool = Query(False, description="Forcer la réanalyse IA même si en cache"),
):
    load_dotenv(get_env_file_path(), override=True)
    config = get_config()
    ai_brain = AIBrain(config)
    unsubscriber = Unsubscriber()

    email_addr = os.getenv("EMAIL_ADDRESS", "").strip()
    email_pwd = os.getenv("EMAIL_PASSWORD", "").strip()
    is_spam_mode = folder.lower() == "spam"
    norm_folder = "spam" if is_spam_mode else "inbox"

    if not email_addr or not email_pwd:
        return {
            "is_live": False,
            "email_address": "",
            "folder": norm_folder,
            "total_scanned": 0,
            "emails": [],
            "error": "Identifiants email non configurés. Rendez-vous dans l'onglet Paramètres.",
        }

    try:
        email_cfg = config.get("email", {})
        client = UniversalEmailClient(email_cfg, env_email=email_addr, env_password=email_pwd)
        client.connect()

        if is_spam_mode:
            emails_to_process = client.fetch_spam_emails(limit=max(limit, 40))
        else:
            emails_to_process = client.fetch_emails(
                folder="INBOX",
                unread_only=unread_only,
                since_days=30,
                limit=limit,
            )

        client.disconnect()
    except Exception as e:
        # En cas d'erreur réseau temporaire, retourner le cache s'il existe avec l'erreur
        cached = store.list_cached_emails(norm_folder, limit=limit)
        return {
            "is_live": False,
            "email_address": email_addr,
            "folder": norm_folder,
            "total_scanned": len(cached),
            "emails": cached,
            "error": str(e),
        }

    results = []
    for em in emails_to_process:
        # Vérifier si cet email (même UID et même Message-ID) est déjà en cache SQLite
        cached_item = None if force_refresh else store.get_cached_email(norm_folder, em.uid)
        if cached_item and cached_item.get("message_id") == em.message_id and cached_item.get("subject") == em.subject:
            results.append(cached_item)
            continue

        analysis = ai_brain.classify_and_analyze(em, is_spam_folder=is_spam_mode)
        cat_key = analysis.get("category", "SPAM_PUB" if is_spam_mode else "A_TRAITER")
        needs_draft = bool(analysis.get("needs_draft", False))

        draft_content = None
        if needs_draft:
            subj, body = ai_brain.generate_draft(em, analysis)
            draft_content = {
                "subject": subj,
                "body": body,
                "to": f"{em.sender_name} <{em.sender_email}>",
            }

        unsub_info = unsubscriber.detect(em)
        is_false_pos = bool(analysis.get("is_false_positive", False))

        record = {
            "uid": em.uid,
            "folder": norm_folder,
            "message_id": em.message_id,
            "references": em.references,
            "reply_to": em.reply_to or em.sender_email,
            "category": cat_key,
            "category_label": config.get("categories", {}).get(cat_key, {}).get("label", cat_key),
            "sender_name": em.sender_name,
            "sender_email": em.sender_email,
            "subject": em.subject,
            "date": em.date_str,
            "summary": analysis.get("summary", em.subject),
            "body_text": em.body_text,
            "snippet": em.body_text[:220] if em.body_text else em.subject,
            "needs_draft": needs_draft,
            "draft": draft_content,
            "has_unsubscribe": unsub_info.has_unsubscribe,
            "unsubscribe_url": unsub_info.primary_action_url,
            "supports_one_click": unsub_info.supports_rfc8058_one_click,
            "unsubscribe_mailto": unsub_info.mailtos[0] if unsub_info.mailtos else None,
            "spam_score": analysis.get("spam_score", 0.9 if is_spam_mode else 0.0),
            "is_false_positive": is_false_pos,
        }
        store.upsert_email_record(norm_folder, record)
        results.append(record)

    return {
        "is_live": True,
        "email_address": email_addr,
        "folder": norm_folder,
        "total_scanned": len(results),
        "emails": results,
        "error": None,
    }


@app.get("/api/spam/scan")
def scan_spam(force_refresh: bool = Query(False)):
    """Fouille complète du dossier Spam."""
    return scan_emails(folder="spam", limit=50, unread_only=False, force_refresh=force_refresh)


@app.post("/api/drafts/generate")
def generate_custom_draft(req: GenerateDraftRequest):
    """Génère ou régénère à la demande un brouillon IA avec une consigne personnalisée."""
    config = get_config()
    ai_brain = AIBrain(config)
    norm_folder = "spam" if req.folder.lower() == "spam" else "inbox"

    cached = store.get_cached_email(norm_folder, req.uid)
    subject = (cached.get("subject") if cached else req.subject) or "(Sans objet)"
    sender_name = (cached.get("sender_name") if cached else req.sender_name) or ""
    sender_email = (cached.get("sender_email") if cached else req.sender_email) or ""
    body_text = (cached.get("body_text") if cached else req.body_text) or ""

    em_data = EmailMessageData(
        uid=req.uid,
        subject=subject,
        sender_name=sender_name,
        sender_email=sender_email,
        date_str="",
        date_obj=None,
        body_text=body_text,
        body_html="",
        list_unsubscribe="",
        message_id=cached.get("message_id", "") if cached else "",
        references=cached.get("references", "") if cached else "",
    )

    draft_subj, draft_body = ai_brain.generate_draft(
        em_data,
        custom_instruction=req.custom_instruction,
    )
    draft_obj = {
        "subject": draft_subj,
        "body": draft_body,
        "to": f"{sender_name} <{sender_email}>".strip(),
    }
    if cached:
        store.update_draft(norm_folder, req.uid, draft_obj)

    return {
        "success": True,
        "draft": draft_obj,
        "engine": ai_brain.get_active_engine_label(),
    }


@app.post("/api/drafts/save")
def save_draft(req: SaveDraftRequest):
    """Synchronise le brouillon dans le dossier Brouillons IMAP en conservant le fil de discussion (In-Reply-To / References)."""
    config = get_config()
    email_addr = os.getenv("EMAIL_ADDRESS", "").strip()
    email_pwd = os.getenv("EMAIL_PASSWORD", "").strip()

    if not email_addr or not email_pwd:
        raise HTTPException(status_code=400, detail="Identifiants email non configurés")

    norm_folder = "spam" if req.folder.lower() == "spam" else "inbox"
    cached = store.get_cached_email(norm_folder, req.uid)

    message_id = req.message_id or (cached.get("message_id", "") if cached else "")
    references = req.references or (cached.get("references", "") if cached else "")
    reply_to = (cached.get("reply_to", "") if cached else "") or req.recipient

    try:
        client = UniversalEmailClient(config.get("email", {}), env_email=email_addr, env_password=email_pwd)
        client.connect()

        orig_msg = EmailMessageData(
            uid=req.uid,
            subject=req.subject,
            sender_name=cached.get("sender_name", "") if cached else "",
            sender_email=req.recipient,
            date_str="",
            date_obj=None,
            body_text="",
            body_html="",
            list_unsubscribe="",
            message_id=message_id,
            references=references,
            reply_to=reply_to,
        )
        success = client.create_draft(orig_msg, draft_body=req.body, draft_subject=req.subject, dry_run=False)
        client.disconnect()

        if success:
            if cached:
                store.update_draft(norm_folder, req.uid, {"subject": req.subject, "body": req.body, "to": req.recipient})
            return {"success": True, "message": "Brouillon synchronisé dans votre dossier Brouillons (rattaché au fil de discussion) !"}
        raise HTTPException(status_code=500, detail="Échec de l'enregistrement du brouillon sur le serveur IMAP")
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/spam/restore")
def restore_spam_email(req: RestoreSpamRequest):
    """Déplace un email du dossier Spam vers la boîte de réception principale (INBOX)."""
    config = get_config()
    email_addr = os.getenv("EMAIL_ADDRESS", "").strip()
    email_pwd = os.getenv("EMAIL_PASSWORD", "").strip()

    if not email_addr or not email_pwd:
        raise HTTPException(status_code=400, detail="Identifiants non configurés")

    try:
        client = UniversalEmailClient(config.get("email", {}), env_email=email_addr, env_password=email_pwd)
        client.connect()
        success = client.restore_to_inbox(req.uid, from_folder=req.folder or "spam")
        client.disconnect()

        if success:
            store.delete_cached_uids("spam", [req.uid])
            return {
                "success": True,
                "message": "Email restauré et transféré dans votre Boîte de Réception !",
            }
        raise HTTPException(status_code=500, detail="Échec de la restauration vers la boîte de réception")
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/spam/restore-all")
def restore_multiple_spams(req: RestoreMultipleSpamRequest):
    """Restaure en lot (Batch UID) plusieurs emails du dossier Spam vers INBOX."""
    config = get_config()
    email_addr = os.getenv("EMAIL_ADDRESS", "").strip()
    email_pwd = os.getenv("EMAIL_PASSWORD", "").strip()

    if not email_addr or not email_pwd:
        raise HTTPException(status_code=400, detail="Identifiants non configurés")

    try:
        client = UniversalEmailClient(config.get("email", {}), env_email=email_addr, env_password=email_pwd)
        client.connect()
        restored = client.restore_to_inbox_batch(req.uids, from_folder=req.folder or "spam")
        client.disconnect()

        if restored > 0:
            store.delete_cached_uids("spam", req.uids)
        return {
            "success": restored > 0,
            "restored_count": restored,
            "message": f"{restored} email(s) restauré(s) avec succès dans la Boîte de Réception !",
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/spam/audit")
def spam_audit(limit: int = Query(120, description="Nombre d'emails à auditer")):
    unsubscriber = Unsubscriber()
    config = get_config()
    email_addr = os.getenv("EMAIL_ADDRESS", "").strip()
    email_pwd = os.getenv("EMAIL_PASSWORD", "").strip()

    if not email_addr or not email_pwd:
        return {"is_live": False, "error": "Identifiants email non configurés", "senders": []}

    try:
        client = UniversalEmailClient(config.get("email", {}), env_email=email_addr, env_password=email_pwd)
        client.connect()
        cleaner = SpamCleaner(client, unsubscriber)
        senders = cleaner.audit_inbox(limit=limit)
        client.disconnect()

        min_threshold = int(config.get("spam_cleaner", {}).get("min_emails_threshold", 2))
        items = []
        for s in senders:
            if s.count >= min_threshold:
                items.append({
                    "sender_name": s.sender_name,
                    "sender_email": s.sender_email,
                    "count": s.count,
                    "sample_subjects": s.sample_subjects,
                    "uids": s.uids,
                    "has_unsubscribe": bool(s.unsubscribe_info and s.unsubscribe_info.has_unsubscribe),
                    "unsubscribe_url": s.unsubscribe_info.primary_action_url if s.unsubscribe_info else None,
                    "supports_one_click": bool(s.unsubscribe_info and s.unsubscribe_info.supports_rfc8058_one_click),
                    "unsubscribe_mailto": (
                        s.unsubscribe_info.mailtos[0]
                        if (s.unsubscribe_info and s.unsubscribe_info.mailtos)
                        else None
                    ),
                })
        return {"is_live": True, "email_address": email_addr, "senders": items}
    except Exception as e:
        return {"is_live": False, "error": str(e), "senders": []}


@app.post("/api/spam/unsubscribe")
def execute_unsubscribe(req: UnsubscribeRequest):
    if not req.url and not req.mailto:
        raise HTTPException(status_code=400, detail="URL ou adresse mailto de désabonnement requise")

    unsub_info = UnsubscribeInfo(
        urls=[req.url] if req.url else [],
        mailtos=[req.mailto] if req.mailto else [],
        one_click_post=req.url if (req.url and req.one_click) else None,
    )
    unsubscriber = Unsubscriber()
    return unsubscriber.execute_one_click(unsub_info)


@app.post("/api/spam/delete")
def delete_spam_sender(req: DeleteSpamRequest):
    """Déplace un lot d'emails par UID vers la Corbeille en une seule commande IMAP."""
    config = get_config()
    email_addr = os.getenv("EMAIL_ADDRESS", "").strip()
    email_pwd = os.getenv("EMAIL_PASSWORD", "").strip()

    if not email_addr or not email_pwd:
        raise HTTPException(status_code=400, detail="Identifiants non configurés")

    try:
        client = UniversalEmailClient(config.get("email", {}), env_email=email_addr, env_password=email_pwd)
        client.connect()
        is_spam_folder = req.folder.lower() == "spam"
        target_folder = "spam" if is_spam_folder else "INBOX"
        deleted = client.move_to_trash_batch(req.uids, from_folder=target_folder, dry_run=False)
        client.disconnect()

        store.delete_cached_uids("spam" if is_spam_folder else "inbox", req.uids)
        return {
            "success": True,
            "deleted_count": deleted,
            "message": f"{deleted} email(s) déplacé(s) vers la corbeille avec succès",
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/settings")
def update_settings(req: SettingsUpdateRequest):
    """
    Sauvegarde proprement les identifiants dans .env (sans écraser les mots de passe/clés existants s'ils sont laissés vides)
    et met à jour config.yaml pour le moteur IA, le ton et la signature.
    """
    load_dotenv(get_env_file_path(), override=True)

    final_email = req.email_address.strip() or os.getenv("EMAIL_ADDRESS", "")
    final_pwd = req.email_password.strip() if (req.email_password and req.email_password.strip()) else os.getenv("EMAIL_PASSWORD", "")
    final_gemini = req.gemini_key.strip() if (req.gemini_key and req.gemini_key.strip()) else os.getenv("GEMINI_API_KEY", "")
    final_openai = req.openai_key.strip() if (req.openai_key and req.openai_key.strip()) else os.getenv("OPENAI_API_KEY", "")
    final_anthropic = req.anthropic_key.strip() if (req.anthropic_key and req.anthropic_key.strip()) else os.getenv("ANTHROPIC_API_KEY", "")

    env_content = (
        f"EMAIL_ADDRESS={final_email}\n"
        f"EMAIL_PASSWORD={final_pwd}\n"
        f"GEMINI_API_KEY={final_gemini}\n"
        f"OPENAI_API_KEY={final_openai}\n"
        f"ANTHROPIC_API_KEY={final_anthropic}\n"
    )

    env_path = os.path.join(EXEC_DIR, ".env")
    with open(env_path, "w", encoding="utf-8") as f:
        f.write(env_content)

    # Mise à jour immédiate de l'environnement du processus courant
    os.environ["EMAIL_ADDRESS"] = final_email
    os.environ["EMAIL_PASSWORD"] = final_pwd
    os.environ["GEMINI_API_KEY"] = final_gemini
    os.environ["OPENAI_API_KEY"] = final_openai
    os.environ["ANTHROPIC_API_KEY"] = final_anthropic

    # Mise à jour de config.yaml
    config = get_config()
    if "ai" not in config or not isinstance(config["ai"], dict):
        config["ai"] = {}
    config["ai"]["provider"] = req.ai_provider.strip().lower()
    if req.ai_model and req.ai_model.strip():
        config["ai"]["model"] = req.ai_model.strip()
    config["ai"]["tone"] = req.tone.strip()
    config["ai"]["user_signature"] = req.signature.strip()
    save_config(config)
    log_agent_event(f"Configuration mise à jour (Fournisseur IA : {req.ai_provider}).", "success")

    return {"success": True, "message": "Paramètres et configuration IA sauvegardés avec succès !"}


@app.post("/api/settings/test")
def test_connections():
    """Teste en direct la connexion IMAP et le moteur IA configuré."""
    load_dotenv(get_env_file_path(), override=True)
    config = get_config()
    ai_brain = AIBrain(config)

    email_addr = os.getenv("EMAIL_ADDRESS", "").strip()
    email_pwd = os.getenv("EMAIL_PASSWORD", "").strip()

    imap_ok = False
    imap_msg = "Identifiants email non renseignés."
    discovered_folders: Dict[str, str] = {}

    if email_addr and email_pwd:
        try:
            t0 = time.time()
            client = UniversalEmailClient(config.get("email", {}), env_email=email_addr, env_password=email_pwd)
            client.connect()
            discovered_folders = {
                "spam": client.resolve_folder("spam"),
                "drafts": client.resolve_folder("drafts"),
                "trash": client.resolve_folder("trash"),
            }
            client.disconnect()
            ms = int((time.time() - t0) * 1000)
            imap_ok = True
            imap_msg = f"Connexion IMAP réussie en {ms} ms ({email_addr})"
            log_agent_event(imap_msg, "success")
        except Exception as e:
            imap_msg = f"Échec IMAP : {e}"
            log_agent_event(imap_msg, "error")

    ai_ok = ai_brain.is_ai_available()
    ai_label = ai_brain.get_active_engine_label()
    log_agent_event(f"Test Moteur IA : {ai_label} ({'Actif' if ai_ok else 'Fallback Heuristique'})", "info")

    return {
        "imap_ok": imap_ok,
        "imap_message": imap_msg,
        "discovered_folders": discovered_folders,
        "ai_ok": ai_ok,
        "ai_label": ai_label,
    }


@app.post("/api/agent/run-routine")
def run_agent_autonomous_routine(req: AgentRoutineRequest):
    """
    Exécute la Routine Matinale Autonome de l'Agent :
    1. Scanne les emails (non lus ou récents)
    2. Trie et résume avec l'IA
    3. Génère les brouillons pour tous les emails URGENT_CLIENT / A_TRAITER
    4. Synchronise optionnellement les brouillons directement dans le dossier Brouillons Gmail/IMAP
    """
    log_agent_event(
        f"Démarrage de la Routine Autonome (limit={req.limit}, unread_only={req.unread_only}, sync_imap={req.sync_drafts_to_imap})...",
        "info",
    )
    scan_res = scan_emails(folder="inbox", limit=req.limit, unread_only=req.unread_only, force_refresh=True)
    if not scan_res.get("is_live"):
        err = scan_res.get("error") or "Impossible de se connecter à la boîte mail."
        log_agent_event(f"Routine interrompue : {err}", "error")
        return {"success": False, "error": err}

    emails_list = scan_res.get("emails", [])
    drafts_generated = 0
    drafts_synced = 0

    config = get_config()
    email_addr = os.getenv("EMAIL_ADDRESS", "").strip()
    email_pwd = os.getenv("EMAIL_PASSWORD", "").strip()

    client = None
    if req.sync_drafts_to_imap and email_addr and email_pwd:
        try:
            client = UniversalEmailClient(config.get("email", {}), env_email=email_addr, env_password=email_pwd)
            client.connect()
        except Exception as e:
            log_agent_event(f"Impossible d'ouvrir IMAP pour synchroniser les brouillons : {e}", "error")
            client = None

    try:
        for em in emails_list:
            if em.get("draft"):
                drafts_generated += 1
                if client:
                    orig_msg = EmailMessageData(
                        uid=em["uid"],
                        subject=em["subject"],
                        sender_name=em["sender_name"],
                        sender_email=em["sender_email"],
                        date_str=em["date"],
                        date_obj=None,
                        body_text="",
                        body_html="",
                        list_unsubscribe="",
                        message_id=em.get("message_id", ""),
                        references=em.get("references", ""),
                        reply_to=em.get("reply_to") or em["sender_email"],
                    )
                    if client.create_draft(
                        orig_msg,
                        draft_body=em["draft"]["body"],
                        draft_subject=em["draft"]["subject"],
                        dry_run=False,
                    ):
                        drafts_synced += 1
    finally:
        if client:
            client.disconnect()

    summary_msg = (
        f"Routine terminée : {len(emails_list)} email(s) trié(s), "
        f"{drafts_generated} brouillon(s) rédigé(s)"
        + (f", {drafts_synced} synchronisé(s) dans Gmail !" if req.sync_drafts_to_imap else ".")
    )
    log_agent_event(summary_msg, "success")
    return {
        "success": True,
        "total_scanned": len(emails_list),
        "drafts_generated": drafts_generated,
        "drafts_synced": drafts_synced,
        "emails": emails_list,
        "message": summary_msg,
    }


@app.get("/api/agent/logs")
def get_agent_logs():
    """Retourne le journal d'activité récent de l'agent."""
    return {"logs": list(AGENT_LOGS)}


# Servir l'application Frontend
app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")


@app.get("/")
def serve_index():
    index_file = os.path.join(STATIC_DIR, "index.html")
    if os.path.exists(index_file):
        return FileResponse(index_file)
    return JSONResponse({"message": "Frontend static/index.html introuvable."})


if __name__ == "__main__":
    uvicorn.run(app, host="127.0.0.1", port=8000, log_level="info")
