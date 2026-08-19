"""
Serveur API FastAPI pour l'application Desktop Email AI Agent.
Connecté en direct à votre compte Email via .env sécurisé.
"""
import os
import sys
from typing import Dict, Any, List, Optional
from fastapi import FastAPI, HTTPException
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import uvicorn
import yaml
from dotenv import load_dotenv

# Ajout du chemin parent
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# Chargement de l'environnement depuis le fichier local .env
for env_path in [
    os.path.join(os.path.dirname(os.path.abspath(__file__)), ".env"),
    os.path.join(os.path.dirname(sys.executable), ".env") if getattr(sys, 'frozen', False) else None,
    r"C:\Users\LENOVO\Documents\github\email_ai_agent\.env",
    r"C:\Users\LENOVO\.gemini\antigravity-ide\scratch\email_ai_agent\.env",
]:
    if env_path and os.path.exists(env_path):
        load_dotenv(env_path, override=True)

from core.email_client import UniversalEmailClient, EmailMessageData
from core.ai_brain import AIBrain
from core.unsubscriber import Unsubscriber, UnsubscribeInfo
from core.spam_cleaner import SpamCleaner

if getattr(sys, 'frozen', False):
    BASE_DIR = getattr(sys, '_MEIPASS', os.path.dirname(sys.executable))
else:
    BASE_DIR = os.path.dirname(os.path.abspath(__file__))

app = FastAPI(title="Email AI Agent Desktop API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Chemin des fichiers statiques
STATIC_DIR = os.path.join(BASE_DIR, "static")
if not os.path.exists(STATIC_DIR) and getattr(sys, 'frozen', False):
    STATIC_DIR = os.path.join(os.path.dirname(sys.executable), "static")
os.makedirs(STATIC_DIR, exist_ok=True)


def get_config() -> Dict[str, Any]:
    for cfg in [
        os.path.join(os.path.dirname(os.path.abspath(__file__)), "config.yaml"),
        os.path.join(os.path.dirname(sys.executable), "config.yaml") if getattr(sys, 'frozen', False) else None,
        os.path.join(getattr(sys, '_MEIPASS', ''), "config.yaml") if getattr(sys, 'frozen', False) else None,
        r"C:\Users\LENOVO\Documents\github\email_ai_agent\config.yaml",
    ]:
        if cfg and os.path.exists(cfg):
            with open(cfg, "r", encoding="utf-8") as f:
                return yaml.safe_load(f)
    return {}


# Modèles de requêtes Pydantic
class SaveDraftRequest(BaseModel):
    uid: str
    recipient: str
    subject: str
    body: str


class UnsubscribeRequest(BaseModel):
    url: Optional[str] = None
    one_click: bool = True
    sender_email: Optional[str] = None


class DeleteSpamRequest(BaseModel):
    sender_email: str
    uids: List[str]


class SettingsUpdateRequest(BaseModel):
    email_address: str
    email_password: Optional[str] = None
    ai_provider: str = "ollama"
    gemini_key: Optional[str] = None
    openai_key: Optional[str] = None
    anthropic_key: Optional[str] = None
    tone: str = "professionnel, bienveillant et concis"
    signature: str = "Cordialement,\n[Votre Nom]"


@app.get("/api/status")
def get_status():
    config = get_config()
    email_addr = os.getenv("EMAIL_ADDRESS", "")
    has_pwd = bool(os.getenv("EMAIL_PASSWORD", ""))
    ai_provider = config.get("ai", {}).get("provider", "ollama")
    ai_model = config.get("ai", {}).get("model", "qwen2.5-coder:7b")

    return {
        "is_configured": bool(email_addr and has_pwd),
        "email_address": email_addr,
        "ai_provider": ai_provider,
        "ai_model": ai_model,
        "app_version": "1.0.0",
    }


@app.get("/api/emails/scan")
def scan_emails():
    config = get_config()
    ai_brain = AIBrain(config)
    unsubscriber = Unsubscriber()

    email_addr = os.getenv("EMAIL_ADDRESS", "")
    email_pwd = os.getenv("EMAIL_PASSWORD", "")

    if not email_addr or not email_pwd:
        return {
            "is_live": False,
            "email_address": "",
            "total_scanned": 0,
            "emails": [],
            "error": "Identifiants email non configurés dans le fichier local .env",
        }

    emails_to_process = []
    is_live = False
    error_msg = None

    try:
        email_cfg = config.get("email", {})
        client = UniversalEmailClient(email_cfg, env_email=email_addr, env_password=email_pwd)
        client.connect()
        
        # Récupération instantanée des 10 emails les plus récents
        emails_to_process = client.fetch_emails(unread_only=False, since_days=30, limit=10)
        client.disconnect()
        is_live = True
    except Exception as e:
        error_msg = str(e)
        is_live = False

    results = []
    for em in emails_to_process:
        analysis = ai_brain.classify_and_analyze(em)
        cat_key = analysis.get("category", "A_TRAITER")
        needs_draft = analysis.get("needs_draft", False)

        draft_content = None
        if needs_draft:
            subj, body = ai_brain.generate_draft(em, analysis)
            draft_content = {
                "subject": subj,
                "body": body,
                "to": f"{em.sender_name} <{em.sender_email}>",
            }

        unsub_info = unsubscriber.detect(em)

        results.append({
            "uid": em.uid,
            "category": cat_key,
            "category_label": config.get("categories", {}).get(cat_key, {}).get("label", cat_key),
            "sender_name": em.sender_name,
            "sender_email": em.sender_email,
            "subject": em.subject,
            "date": em.date_str,
            "summary": analysis.get("summary", em.subject),
            "snippet": em.body_text[:180],
            "draft": draft_content,
            "has_unsubscribe": unsub_info.has_unsubscribe,
            "unsubscribe_url": unsub_info.primary_action_url,
            "spam_score": analysis.get("spam_score", 0.0),
        })

    return {
        "is_live": is_live,
        "email_address": email_addr,
        "total_scanned": len(results),
        "emails": results,
        "error": error_msg,
    }


@app.post("/api/drafts/save")
def save_draft(req: SaveDraftRequest):
    config = get_config()
    email_addr = os.getenv("EMAIL_ADDRESS", "")
    email_pwd = os.getenv("EMAIL_PASSWORD", "")

    try:
        client = UniversalEmailClient(config.get("email", {}), env_email=email_addr, env_password=email_pwd)
        client.connect()

        dummy_msg = EmailMessageData(
            uid=req.uid,
            subject=req.subject,
            sender_name="",
            sender_email=req.recipient,
            date_str="",
            date_obj=None,
            body_text="",
            body_html="",
            list_unsubscribe="",
            message_id="",
            references="",
            raw_message=None,
        )
        success = client.create_draft(dummy_msg, draft_body=req.body, draft_subject=req.subject, dry_run=False)
        client.disconnect()
        if success:
            return {"success": True, "message": "Brouillon synchronisé dans votre dossier Brouillons !"}
        raise HTTPException(status_code=500, detail="Échec de l'enregistrement du brouillon")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/spam/audit")
def spam_audit():
    unsubscriber = Unsubscriber()
    config = get_config()
    email_addr = os.getenv("EMAIL_ADDRESS", "")
    email_pwd = os.getenv("EMAIL_PASSWORD", "")

    if not email_addr or not email_pwd:
        return {"is_live": False, "error": "Identifiants email non configurés dans .env", "senders": []}

    try:
        client = UniversalEmailClient(config.get("email", {}), env_email=email_addr, env_password=email_pwd)
        cleaner = SpamCleaner(client, unsubscriber)
        senders = cleaner.audit_inbox(limit=120)
        client.disconnect()

        items = []
        for s in senders:
            if s.count >= 2:
                items.append({
                    "sender_name": s.sender_name,
                    "sender_email": s.sender_email,
                    "count": s.count,
                    "sample_subjects": s.sample_subjects,
                    "uids": s.uids,
                    "has_unsubscribe": bool(s.unsubscribe_info and s.unsubscribe_info.has_unsubscribe),
                    "unsubscribe_url": s.unsubscribe_info.primary_action_url if s.unsubscribe_info else None,
                })
        return {"is_live": True, "email_address": email_addr, "senders": items}
    except Exception as e:
        return {"is_live": False, "error": str(e), "senders": []}


@app.post("/api/spam/unsubscribe")
def execute_unsubscribe(req: UnsubscribeRequest):
    if not req.url:
        raise HTTPException(status_code=400, detail="URL de désabonnement requise")

    unsub_info = UnsubscribeInfo(urls=[req.url], mailtos=[], one_click_post=req.url if req.one_click else None)
    unsubscriber = Unsubscriber()
    result = unsubscriber.execute_one_click(unsub_info)
    return result


@app.post("/api/spam/delete")
def delete_spam_sender(req: DeleteSpamRequest):
    config = get_config()
    email_addr = os.getenv("EMAIL_ADDRESS", "")
    email_pwd = os.getenv("EMAIL_PASSWORD", "")

    try:
        client = UniversalEmailClient(config.get("email", {}), env_email=email_addr, env_password=email_pwd)
        client.connect()
        deleted = 0
        for uid in req.uids:
            if client.move_to_trash(uid, dry_run=False):
                deleted += 1
        client.disconnect()
        return {"success": True, "deleted_count": deleted, "message": f"{deleted} emails déplacés vers la corbeille"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/settings")
def update_settings(req: SettingsUpdateRequest):
    env_content = f"""EMAIL_ADDRESS={req.email_address}
EMAIL_PASSWORD={req.email_password or ''}
GEMINI_API_KEY={req.gemini_key or ''}
OPENAI_API_KEY={req.openai_key or ''}
ANTHROPIC_API_KEY={req.anthropic_key or ''}
"""
    for target_env in [
        os.path.join(os.path.dirname(os.path.abspath(__file__)), ".env"),
        r"C:\Users\LENOVO\Documents\github\email_ai_agent\.env",
        r"C:\Users\LENOVO\Documents\github\email_ai_agent\dist\Email_AI_Agent\.env",
    ]:
        try:
            with open(target_env, "w", encoding="utf-8") as f:
                f.write(env_content)
        except Exception:
            pass

    return {"success": True, "message": "Paramètres sauvegardés avec succès !"}


# Servir l'application Frontend
app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")


@app.get("/")
def serve_index():
    index_file = os.path.join(STATIC_DIR, "index.html")
    if os.path.exists(index_file):
        return FileResponse(index_file)
    return JSONResponse({"message": "Frontend static/index.html en cours de chargement..."})


if __name__ == "__main__":
    uvicorn.run(app, host="127.0.0.1", port=8000, log_level="info")
