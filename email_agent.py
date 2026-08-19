"""
Email AI Agent - Assistant Principal de Tri, Rédaction de Brouillons & Désabonnement Anti-Spam
"""
import os
import sys
import yaml
import argparse
from typing import Dict, Any, List
from dotenv import load_dotenv

# Forcer l'encodage UTF-8 sur Windows
if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

# Ajout du chemin racine
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from core.email_client import UniversalEmailClient, EmailMessageData
from core.ai_brain import AIBrain
from core.unsubscriber import Unsubscriber, UnsubscribeInfo
from core.spam_cleaner import SpamCleaner
from ui.dashboard import print_banner, display_morning_digest, display_drafts_preview, display_spam_audit, console
from rich.prompt import Prompt, Confirm


def load_config() -> Dict[str, Any]:
    """Charge le fichier config.yaml et .env."""
    load_dotenv()
    config_path = os.path.join(os.path.dirname(__file__), "config.yaml")
    if os.path.exists(config_path):
        with open(config_path, "r", encoding="utf-8") as f:
            return yaml.safe_load(f)
    return {}


def run_demo_mode():
    """Mode Démonstration avec des emails simulés réalistes pour tester sans configuration."""
    console.print("\n[bold magenta]🚀 LANCEMENT DU MODE DÉMO (Simulations d'emails réels)[/bold magenta]\n")
    config = load_config()
    ai_brain = AIBrain(config)

    # Création d'échantillons réalistes
    demo_emails = [
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
    ]

    results = []
    drafts = []

    for em in demo_emails:
        analysis = ai_brain.classify_and_analyze(em)
        cat_key = analysis.get("category", "A_TRAITER")
        needs_draft = analysis.get("needs_draft", False) or config.get("categories", {}).get(cat_key, {}).get("generate_draft", False)

        draft_created = False
        if needs_draft:
            subj, body = ai_brain.generate_draft(em, analysis)
            drafts.append({
                "to": f"{em.sender_name} <{em.sender_email}>",
                "subject": subj,
                "body": body,
            })
            draft_created = True

        results.append({
            "uid": em.uid,
            "category": cat_key,
            "sender": em.sender_name,
            "subject": em.subject,
            "summary": analysis.get("summary", em.subject),
            "draft_created": draft_created,
        })

    display_morning_digest(results)
    display_drafts_preview(drafts)


def run_morning_routine(client: UniversalEmailClient, ai_brain: AIBrain, dry_run: bool = False):
    """Routine du matin : Tri des emails non lus et rédaction des brouillons."""
    console.print("\n[bold cyan]🔄 Récupération des emails non lus des dernières 24h...[/bold cyan]")
    emails = client.fetch_emails(unread_only=True, since_days=1, limit=30)

    if not emails:
        console.print("[green]✨ Votre boîte de réception est vide ou tous vos emails sont déjà lus ![/green]")
        return

    results = []
    drafts = []

    for em in emails:
        analysis = ai_brain.classify_and_analyze(em)
        cat_key = analysis.get("category", "A_TRAITER")
        needs_draft = analysis.get("needs_draft", False)

        draft_created = False
        if needs_draft:
            subj, body = ai_brain.generate_draft(em, analysis)
            if client.create_draft(em, draft_body=body, draft_subject=subj, dry_run=dry_run):
                draft_created = True
                drafts.append({
                    "to": f"{em.sender_name} <{em.sender_email}>",
                    "subject": subj,
                    "body": body,
                })

        results.append({
            "uid": em.uid,
            "category": cat_key,
            "sender": em.sender_name,
            "subject": em.subject,
            "summary": analysis.get("summary", em.subject),
            "draft_created": draft_created,
        })

    display_morning_digest(results)
    display_drafts_preview(drafts)


def run_spam_cleaner(client: UniversalEmailClient, unsubscriber: Unsubscriber, dry_run: bool = False):
    """Audit des spams et assistant de désabonnement interactif."""
    cleaner = SpamCleaner(client, unsubscriber)
    console.print("\n[bold cyan]🔍 Audit de votre boîte de réception en cours...[/bold cyan]")
    senders = cleaner.audit_inbox(limit=150)
    top_senders = display_spam_audit(senders, min_threshold=2)

    if not top_senders:
        return

    console.print("\n[bold yellow]💡 Actions disponibles :[/bold yellow]")
    console.print("1. [bold green]Se désabonner d'un expéditeur (1-Click)[/bold green]")
    console.print("2. [bold red]Nettoyer tous les emails d'un expéditeur[/bold red]")
    console.print("3. [bold cyan]Ouvrir le lien de désabonnement dans le navigateur[/bold cyan]")
    console.print("4. [dim]Quitter[/dim]")

    choice = Prompt.ask("\nVotre choix", choices=["1", "2", "3", "4"], default="4")

    if choice in ["1", "2", "3"]:
        num_str = Prompt.ask("Entrez le numéro # de l'expéditeur dans la liste ci-dessus")
        try:
            num = int(num_str)
            if 1 <= num <= len(top_senders):
                target = top_senders[num - 1]
                
                if choice == "1":
                    if target.unsubscribe_info and target.unsubscribe_info.has_unsubscribe:
                        res = unsubscriber.execute_one_click(target.unsubscribe_info)
                        if res.get("success"):
                            console.print(f"[bold green]✅ Succès : {res.get('message')}[/bold green]")
                        else:
                            console.print(f"[yellow]⚠️ {res.get('message')}[/yellow]")
                            if Confirm.ask("Voulez-vous ouvrir la page dans votre navigateur ?"):
                                unsubscriber.open_link_in_browser(target.unsubscribe_info)
                    else:
                        console.print("[red]Aucun lien de désabonnement automatique détecté pour cet expéditeur.[/red]")

                elif choice == "2":
                    if Confirm.ask(f"Confirmez-vous le déplacement vers la corbeille de {target.count} emails de '{target.sender_name}' ?"):
                        count = cleaner.clean_sender_emails(target, dry_run=dry_run)
                        console.print(f"[bold green]🗑️ {count} emails déplacés vers la corbeille.[/bold green]")

                elif choice == "3":
                    if target.unsubscribe_info and target.unsubscribe_info.has_unsubscribe:
                        unsubscriber.open_link_in_browser(target.unsubscribe_info)
                        console.print(f"[bold green]🌐 Page de désabonnement ouverte pour {target.sender_name}.[/bold green]")
                    else:
                        console.print("[red]Aucun lien détecté pour cet expéditeur.[/red]")
        except ValueError:
            console.print("[red]Numéro invalide.[/red]")


def interactive_setup():
    """Assistant de configuration des identifiants."""
    console.print("\n[bold cyan]⚙️ ASSISTANT DE CONFIGURATION EMAIL AI AGENT[/bold cyan]\n")
    email_addr = Prompt.ask("Votre adresse email (ex: prenom.nom@gmail.com)")
    console.print("\n[dim]Note Gmail : Générez un 'Mot de passe d'application' sur myaccount.google.com -> Sécurité -> Validation en 2 étapes -> Mots de passe d'application[/dim]")
    password = Prompt.ask("Votre mot de passe ou mot de passe d'application", password=True)
    gemini_key = Prompt.ask("Votre clé API Google Gemini (laisser vide si Ollama ou Heuristique locale)", default="")

    env_content = f"""EMAIL_ADDRESS={email_addr}
EMAIL_PASSWORD={password}
GEMINI_API_KEY={gemini_key}
"""
    env_path = os.path.join(os.path.dirname(__file__), ".env")
    with open(env_path, "w", encoding="utf-8") as f:
        f.write(env_content)
    console.print(f"[bold green]✅ Fichier .env créé avec succès ![/bold green]\n")


def main():
    parser = argparse.ArgumentParser(description="Email AI Agent - Tri, Brouillons & Anti-Spam")
    parser.add_argument("--morning", action="store_true", help="Lance la routine matinale (tri + brouillons)")
    parser.add_argument("--clean-spam", action="store_true", help="Lance l'audit et le nettoyage de spams")
    parser.add_argument("--demo", action="store_true", help="Lance le mode démonstration avec des exemples réalistes")
    parser.add_argument("--setup", action="store_true", help="Configure les identifiants et clés API")
    parser.add_argument("--dry-run", action="store_true", default=False, help="Mode simulation (aucun changement réel)")
    parser.add_argument("--live", action="store_true", help="Mode réel actif")

    args = parser.parse_args()
    config = load_config()

    is_dry_run = args.dry_run or (not args.live and not args.morning and not args.clean_spam)
    print_banner(dry_run=is_dry_run)

    if args.setup:
        interactive_setup()
        return

    if args.demo or (not args.morning and not args.clean_spam):
        # Si aucun argument ou --demo, lancer la démo avec menu
        run_demo_mode()
        console.print("\n[bold cyan]Astuce :[/bold cyan] Pour connecter votre vraie boîte mail, exécutez :")
        console.print("[yellow]python email_agent.py --setup[/yellow]")
        console.print("[yellow]python email_agent.py --morning --live[/yellow]")
        console.print("[yellow]python email_agent.py --clean-spam --live[/yellow]")
        return

    # Initialisation des composants
    ai_brain = AIBrain(config)
    unsubscriber = Unsubscriber()
    client = UniversalEmailClient(config.get("email", {}))

    try:
        if args.morning:
            run_morning_routine(client, ai_brain, dry_run=is_dry_run)
        elif args.clean_spam:
            run_spam_cleaner(client, unsubscriber, dry_run=is_dry_run)
    finally:
        client.disconnect()


if __name__ == "__main__":
    main()
