"""
Cerveau d'Intelligence Artificielle pour le tri d'emails et l'analyse anti-spam.
Compatible 100% Local (Ollama - Qwen 2.5 / Llama 3), Google Gemini, OpenAI et heuristique locale (0 ms).
"""
import os
import re
import json
import time
import requests
from typing import Dict, Any, Tuple, Optional
from core.email_client import EmailMessageData


class AIBrain:
    """Moteur IA pour la classification, la détection des faux positifs et la génération de brouillons."""

    def __init__(self, config: Dict[str, Any]):
        self.config = config
        self.ai_cfg = config.get("ai", {})
        self.provider = self.ai_cfg.get("provider", "ollama")
        self.model = self.ai_cfg.get("model", "qwen2.5-coder:7b")
        self.ollama_url = self.ai_cfg.get("ollama_url", "http://localhost:11434")

        self.gemini_key = os.getenv("GEMINI_API_KEY", "")
        self.openai_key = os.getenv("OPENAI_API_KEY", "")
        self.anthropic_key = os.getenv("ANTHROPIC_API_KEY", "")

        self.tone = self.config.get("drafting", {}).get("tone", "professionnel, bienveillant et concis")
        self.signature = self.config.get("drafting", {}).get("signature", "Cordialement,\n[Votre Nom]")
        self._ollama_alive_cache = None

    def _is_ollama_alive(self) -> bool:
        """Vérifie en 0.4s si le serveur Ollama est actif avec cache de 30s."""
        if self._ollama_alive_cache:
            cached_val, cached_time = self._ollama_alive_cache
            if time.time() - cached_time < 30:
                return cached_val
        try:
            r = requests.get(f"{self.ollama_url}/api/version", timeout=0.4)
            alive = (r.status_code == 200)
        except Exception:
            alive = False
        self._ollama_alive_cache = (alive, time.time())
        return alive

    def classify_and_analyze(self, email_data: EmailMessageData, is_spam_folder: bool = False) -> Dict[str, Any]:
        """Classifie un email et détecte les faux positifs si issu du dossier Spam."""
        # 1. Analyse spécifique pour les emails du dossier Spam
        if is_spam_folder:
            return self._analyze_spam_message(email_data)

        # 2. Heuristique locale instantanée par défaut
        analysis = self._heuristic_classify(email_data)

        # 3. Enrichissement IA si Ollama ou API disponible et pertinent
        if self._is_ollama_alive() and analysis.get("category") in ["URGENT_CLIENT", "A_TRAITER"]:
            prompt = f"""Tu es un assistant exécutif IA. Analyse brièvement cet email et renvoie un résumé en 1 phrase:
Expéditeur: {email_data.sender_name} <{email_data.sender_email}>
Sujet: {email_data.subject}
Contenu: {email_data.body_text[:500]}

Réponds UNIQUEMENT un JSON valide au format : {{"summary": "Résumé en 1 phrase", "category": "{analysis.get('category')}"}}"""
            try:
                ai_resp = self._query_ai_engine(prompt)
                if ai_resp:
                    match = re.search(r"\{.*\}", ai_resp, re.DOTALL)
                    if match:
                        parsed = json.loads(match.group(0))
                        analysis["summary"] = parsed.get("summary", analysis["summary"])
            except Exception:
                pass

        return analysis

    def _analyze_spam_message(self, email_data: EmailMessageData) -> Dict[str, Any]:
        """Analyse un message situé dans [Gmail]/Spam pour détecter les faux positifs."""
        text = f"{email_data.subject} {email_data.sender_name} {email_data.body_text}".lower()
        sender_email = email_data.sender_email.lower()

        # Liste de signaux légitimes (Faux Positifs potentiels)
        legit_signals = [
            "project", "test", "utest", "invitation", "account", "compte", "security", "sécurité",
            "facture", "invoice", "receipt", "reçu", "commande", "order", "github", "gitlab",
            "token", "supabase", "npm", "vercel", "devis", "candidature", "entretien"
        ]

        # Liste de signaux de vrai spam / arnaque
        scam_signals = [
            "casino", "bonus", "deposit bonus", "free spins", "iptv", "viagra", "crypto", "bitcoin",
            "hermes", "fortune", "prêt", "héritage", "urgent warning", "final warning", "gagnez"
        ]

        is_false_positive = False
        spam_score = 0.90
        summary = "Spam / Publicité commerciale intrusive"
        category = "SPAM_PUB"

        if any(sig in text or sig in sender_email for sig in legit_signals) and not any(scam in text for scam in ["casino", "free spins", "iptv"]):
            is_false_positive = True
            spam_score = 0.25
            category = "A_TRAITER"
            summary = f"🔥 Faux positif probable ({email_data.sender_name}) : projet ou notification légitime. Restauration recommandée."
        elif any(scam in text for scam in scam_signals):
            spam_score = 0.98
            summary = f"⚠️ Phishing / Scam détecté ({email_data.subject[:35]})"
        else:
            summary = f"Newsletter ou prospection filtrée par Gmail ({email_data.sender_name})"

        return {
            "category": category,
            "summary": summary,
            "needs_draft": is_false_positive,
            "confidence": 0.85,
            "spam_score": spam_score,
            "is_false_positive": is_false_positive,
        }

    def generate_draft(self, email_data: EmailMessageData, analysis: Dict[str, Any]) -> Tuple[str, str]:
        """Génère un brouillon de réponse poli et adapté."""
        subject = f"Re: {email_data.subject}"
        body = self._heuristic_draft(email_data)
        return subject, body

    def _query_ai_engine(self, prompt: str) -> Optional[str]:
        """Achemine la requête en priorité vers votre modèle local Ollama si actif."""
        if (self.provider == "ollama" or not (self.gemini_key or self.openai_key or self.anthropic_key)) and self._is_ollama_alive():
            try:
                model_name = self.model.replace("ollama/", "")
                resp = requests.post(
                    f"{self.ollama_url}/api/generate",
                    json={"model": model_name, "prompt": prompt, "stream": False},
                    timeout=5,
                )
                if resp.status_code == 200:
                    output = resp.json().get("response", "").strip()
                    if output:
                        return output
            except Exception:
                pass
        return None

    def _heuristic_classify(self, email_data: EmailMessageData) -> Dict[str, Any]:
        """Moteur local 100% hors-ligne instantané (0 ms)."""
        text = f"{email_data.subject} {email_data.body_text}".lower()
        has_unsub = bool(email_data.list_unsubscribe)

        # 1. Factures / Compta
        invoice_keywords = ["facture", "invoice", "reçu", "receipt", "quittance", "prélèvement", "paiement confirmé", "order confirmation", "votre commande"]
        if any(kw in text for kw in invoice_keywords):
            return {
                "category": "FACTURE_COMPTA",
                "summary": f"Facture / Document comptable ({email_data.sender_name})",
                "needs_draft": False,
                "confidence": 0.85,
                "spam_score": 0.05,
            }

        # 2. Spams / Démarchage agressif
        spam_keywords = ["gagnez", "viagra", "casino", "offre exclusive exceptionnelle", "urgent crypto", "fortune", "prêt d'argent", "héritage", "cliquez ici pour réclamer"]
        if any(kw in text for kw in spam_keywords) or (has_unsub and any(kw in text for kw in ["promo", "solde", "-50%", "-70%", "black friday"])):
            return {
                "category": "SPAM_PUB",
                "summary": "Publicité commerciale ou prospection non sollicitée",
                "needs_draft": False,
                "confidence": 0.80,
                "spam_score": 0.90,
            }

        # 3. Newsletters
        newsletter_keywords = ["newsletter", "hebdo", "digest", "infolettre", "désabonner", "unsubscribe", "view in browser", "voir dans le navigateur"]
        if has_unsub or any(kw in text for kw in newsletter_keywords):
            return {
                "category": "NEWSLETTER",
                "summary": f"Infolettre / Mise à jour ({email_data.sender_name})",
                "needs_draft": False,
                "confidence": 0.88,
                "spam_score": 0.20,
            }

        # 4. Urgent / Client
        urgent_keywords = ["urgent", "asap", "bloquant", "critique", "devis urgent", "problème client", "incident", "rappel urgent"]
        if any(kw in text for kw in urgent_keywords):
            return {
                "category": "URGENT_CLIENT",
                "summary": f"Message prioritaire nécessitant une attention rapide : {email_data.subject}",
                "needs_draft": True,
                "confidence": 0.75,
                "spam_score": 0.0,
            }

        # 5. Par défaut : À traiter
        return {
            "category": "A_TRAITER",
            "summary": f"Message de {email_data.sender_name} : {email_data.subject[:50]}",
            "needs_draft": True,
            "confidence": 0.70,
            "spam_score": 0.0,
        }

    def _heuristic_draft(self, email_data: EmailMessageData) -> str:
        """Génération de modèle de réponse par défaut."""
        first_name = email_data.sender_name.split()[0] if email_data.sender_name else "Bonjour"
        if first_name.lower() in ["bonjour", "madame", "monsieur", "'congratulations!'", "admin"]:
            greeting = "Bonjour,"
        else:
            greeting = f"Bonjour {first_name},"

        return f"""{greeting}

Merci pour votre retour concernant "{email_data.subject}".

J'ai bien pris note des éléments transmis et je reviens vers vous dès que possible.

{self.signature}"""
