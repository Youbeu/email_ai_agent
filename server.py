"""
Serveur API FastAPI pour l'application Desktop Email AI Agent.
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

from core.email_client import UniversalEmailClient, EmailMessageData
from core.ai_brain import AIBrain
from core.unsubscriber import Unsubscriber, UnsubscribeInfo
from core.spam_cleaner import SpamCleaner

load_dotenv()

app = FastAPI(title="Email AI Agent Desktop API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Chemin des fichiers statiques
STATIC_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "static")
os.makedirs(STATIC_DIR, exist_ok=True)

# Données de simulation pour le mode Démo
DEMO_EMAILS = [
    EmailMessageData(
        uid="101",
        subject="URGENT : Point d'avancement sur le projet et validation devis",
        sender_name="Sophie Martin (Directrice Marketing)",
        sender_email="sophie.martin@client-prestige.com",
        date_str="Aujourd'hui 07:15",
        date_obj=None,
        body_text="Bonjour, Pourriez-vous nous confirmer la livraison de la phase 2 pour ce vendredi ? Nous avons besoin de caler la réunion de cadrage au plus vite. Merci d'avance !",
        body_html="<p>Bonjour, Pourriez-vous nous confirmer la livraison...</p>",
        list_unsubscribe="",
        message_id="<msg-demo-101@client.com>",
        references="",
        raw_message=None,
    ),
    EmailMessageData(
        uid="102",
        subject="Votre facture mensuelle OVHcloud - Février 2026",
        sender_name="OVHcloud Facturation",
        sender_email="billing@ovhcloud.com",
        date_str="Aujourd'hui 06:40",
        date_obj=None,
        body_text="Cher client, Votre facture N° FR-2026-8890 d'un montant de 48,00 EUR TTC est disponible. Le prélèvement aura lieu sous 48h.",
        body_html="<p>Cher client, Votre facture N° FR-2026-8890...</p>",
        list_unsubscribe="<mailto:unsubscribe@ovhcloud.com>, <https://ovh.com/unsub>",
        message_id="<msg-demo-102@ovh.com>",
        references="",
        raw_message=None,
    ),
    EmailMessageData(
        uid="103",
        subject="⚡ Vente flash exceptionnelle -50% sur tout le catalogue jusqu'à minuit !",
        sender_name="Boutique Promo Deals",
        sender_email="news@promodeals-vip.com",
        date_str="Hier 23:30",
        date_obj=None,
        body_text="Profitez de nos remises exclusives dès maintenant. Cliquez ici pour voir les offres.",
        body_html="<p>Profitez de nos offres... <a href='https://promodeals-vip.com/unsubscribe?user=123'>Se désabonner</a></p>",
        list_unsubscribe="<https://promodeals-vip.com/unsub-oneclick>",
        message_id="<msg-demo-103@promo.com>",
        references="",
        raw_message=None,
    ),
    EmailMessageData(
        uid="104",
        subject="Demande de rendez-vous partenariat Q2",
        sender_name="Alexandre Dumas",
        sender_email="a.dumas@innovatech-labs.io",
        date_str="Hier 18:20",
        date_obj=None,
        body_text="Bonjour, J'aimerais échanger 15 minutes avec vous la semaine prochaine au sujet de nos synergies techniques. Êtes-vous disponible mardi à 14h ?",
        body_html="<p>Bonjour, J'aimerais échanger 15 minutes...</p>",
        list_unsubscribe="",
        message_id="<msg-demo-104@innovatech.io>",
        references="",
        raw_message=None,
    ),
    EmailMessageData(
        uid="105",
        subject="Sécurité de votre compte : Tentative de connexion suspecte évitée",
        sender_name="Service Sécurité Cloud",
        sender_email="security-alert@cloudservice.net",
        date_str="Hier 14:10",
        date_obj=None,
        body_text="Une nouvelle connexion a été détectée depuis une adresse IP inconnue. Si c'était vous, aucune action n'est requise.",
        body_html="<p>Une nouvelle connexion a été détectée...</p>",
        list_unsubscribe="",
        message_id="<msg-demo-105@security.com>",
        references="",
        raw_message=None,
    ),
]


def get_config() -> Dict[str, Any]:
    config_path = os.path.join(os.path.dirname(__file__), "config.yaml")
    if os.path.exists(config_path):
        with open(config_path, "r", encoding="utf-8") as f:
            return yaml.safe_load(f)
    return {}


# Modèles de requêtes Pydantic
class SaveDraftRequest(BaseModel):
    uid: str
    recipient: str
    subject: str
    body: str
    is_demo: bool = False


class UnsubscribeRequest(BaseModel):
    url: Optional[str] = None
    one_click: bool = True
    sender_email: Optional[str] = None


class DeleteSpamRequest(BaseModel):
    sender_email: str
    uids: List[str]
    is_demo: bool = False


class SettingsUpdateRequest(BaseModel):
    email_address: str
    email_password: Optional[str] = None
    ai_provider: str = "gemini"
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
    gemini_key = os.getenv("GEMINI_API_KEY", "")
    openai_key = os.getenv("OPENAI_API_KEY", "")
    anthropic_key = os.getenv("ANTHROPIC_API_KEY", "")
    ai_provider = config.get("ai", {}).get("provider", "gemini")

    return {
        "is_configured": bool(email_addr and has_pwd),
        "email_address": email_addr,
        "ai_provider": ai_provider,
        "ai_model": config.get("ai", {}).get("model", "gemini-2.5-flash"),
        "has_ai_key": bool(gemini_key or openai_key or anthropic_key or ai_provider == "ollama"),
        "app_version": "1.0.0",
    }


@app.get("/api/emails/scan")
def scan_emails(demo: bool = False):
    config = get_config()
    ai_brain = AIBrain(config)
    unsubscriber = Unsubscriber()

    emails_to_process = []
    is_live = False

    if not demo and os.getenv("EMAIL_ADDRESS") and os.getenv("EMAIL_PASSWORD"):
        try:
            client = UniversalEmailClient(config.get("email", {}))
            emails_to_process = client.fetch_emails(unread_only=True, since_days=2, limit=30)
            client.disconnect()
            is_live = True
        except Exception as e:
            # Fallback en mode démo si échec de connexion
            emails_to_process = DEMO_EMAILS
            is_live = False
    else:
        emails_to_process = DEMO_EMAILS

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
        "total_scanned": len(results),
        "emails": results,
    }


@app.post("/api/drafts/save")
def save_draft(req: SaveDraftRequest):
    if req.is_demo:
        return {"success": True, "message": "Brouillon enregistré avec succès (Mode Démo)"}

    config = get_config()
    client = UniversalEmailClient(config.get("email", {}))
    try:
        # Création d'un message minimal
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
            return {"success": True, "message": "Brouillon synchronisé avec succès dans votre boîte mail !"}
        raise HTTPException(status_code=500, detail="Échec de l'enregistrement IMAP")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/spam/audit")
def spam_audit(demo: bool = False):
    unsubscriber = Unsubscriber()

    if not demo and os.getenv("EMAIL_ADDRESS") and os.getenv("EMAIL_PASSWORD"):
        config = get_config()
        try:
            client = UniversalEmailClient(config.get("email", {}))
            cleaner = SpamCleaner(client, unsubscriber)
            senders = cleaner.audit_inbox(limit=100)
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
            return {"is_live": True, "senders": items}
        except Exception:
            pass

    # Données démo réalistes pour l'audit
    demo_senders = [
        {
            "sender_name": "Boutique Promo Deals",
            "sender_email": "news@promodeals-vip.com",
            "count": 14,
            "sample_subjects": ["⚡ Vente flash -50%", "Dernières heures pour en profiter", "Votre panier vous attend"],
            "uids": ["103", "201", "202", "203"],
            "has_unsubscribe": True,
            "unsubscribe_url": "https://promodeals-vip.com/unsubscribe?user=demo",
        },
        {
            "sender_name": "Offres Partenaires Finance",
            "sender_email": "contact@finance-direct-deals.net",
            "count": 9,
            "sample_subjects": ["Opportunité d'investissement", "Crédit au meilleur taux", "Simulateur gratuit"],
            "uids": ["301", "302", "303"],
            "has_unsubscribe": True,
            "unsubscribe_url": "https://finance-direct-deals.net/opt-out",
        },
        {
            "sender_name": "LinkedIn Notifications",
            "sender_email": "updates-noreply@linkedin.com",
            "count": 27,
            "sample_subjects": ["Vous avez 5 nouvelles vues de profil", "Alexandre a publié un post", "Offres d'emploi recommandées"],
            "uids": ["401", "402", "403"],
            "has_unsubscribe": True,
            "unsubscribe_url": "https://www.linkedin.com/psettings/guest-email-unsubscribe",
        },
        {
            "sender_name": "Marketing Pro News",
            "sender_email": "newsletter@mktg-weekly.io",
            "count": 6,
            "sample_subjects": ["Les 10 tendances du web", "Cas d'étude croissance"],
            "uids": ["501", "502"],
            "has_unsubscribe": True,
            "unsubscribe_url": "https://mktg-weekly.io/unsub",
        },
    ]
    return {"is_live": False, "senders": demo_senders}


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
    if req.is_demo:
        return {"success": True, "deleted_count": len(req.uids), "message": f"{len(req.uids)} emails déplacés vers la corbeille (Mode Démo)"}

    config = get_config()
    client = UniversalEmailClient(config.get("email", {}))
    try:
        deleted = 0
        for uid in req.uids:
            if client.move_to_trash(uid, dry_run=False):
                deleted += 1
        client.disconnect()
        return {"success": True, "deleted_count": deleted, "message": f"{deleted} emails supprimés avec succès"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/settings")
def update_settings(req: SettingsUpdateRequest):
    env_lines = [
        f"EMAIL_ADDRESS={req.email_address}\n",
    ]
    if req.email_password:
        env_lines.append(f"EMAIL_PASSWORD={req.email_password}\n")
    if req.gemini_key:
        env_lines.append(f"GEMINI_API_KEY={req.gemini_key}\n")
    if req.openai_key:
        env_lines.append(f"OPENAI_API_KEY={req.openai_key}\n")
    if req.anthropic_key:
        env_lines.append(f"ANTHROPIC_API_KEY={req.anthropic_key}\n")

    env_path = os.path.join(os.path.dirname(__file__), ".env")
    with open(env_path, "w", encoding="utf-8") as f:
        f.writelines(env_lines)

    # Mise à jour config.yaml
    config = get_config()
    if "ai" not in config:
        config["ai"] = {}
    config["ai"]["provider"] = req.ai_provider
    config["ai"]["tone"] = req.tone
    config["ai"]["user_signature"] = req.signature

    config_path = os.path.join(os.path.dirname(__file__), "config.yaml")
    with open(config_path, "w", encoding="utf-8") as f:
        yaml.dump(config, f, allow_unicode=True)

    return {"success": True, "message": "Paramètres sauvegardés avec succès !"}


# Servir l'application Frontend
app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")


@app.get("/")
def serve_index():
    index_file = os.path.join(STATIC_DIR, "index.html")
    if os.path.exists(index_file):
        return FileResponse(index_file)
    return JSONResponse({"message": "Frontend static/index.html en cours de création..."})


if __name__ == "__main__":
    uvicorn.run(app, host="127.0.0.1", port=8000, log_level="info")
