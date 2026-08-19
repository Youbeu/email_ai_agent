"""
Interface visuelle terminal riche utilisant la bibliothèque Rich.
"""
from typing import List, Dict, Any
from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich.text import Text
from rich import box
from core.spam_cleaner import SenderAuditInfo

import sys
import os
import io

# Forcer UTF-8 sur Windows
if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

console = Console(force_terminal=True, legacy_windows=False)


def print_banner(dry_run: bool = False):
    """Affiche la bannière d'accueil."""
    mode_text = "[bold yellow]⚠️ MODE SIMULATION (DRY-RUN) - Aucun changement réel[/bold yellow]" if dry_run else "[bold green]⚡ MODE ACTIF (CONNECTÉ)[/bold green]"
    panel = Panel(
        Text.from_markup(
            f"[bold cyan]📬 EMAIL AI AGENT[/bold cyan] : Tri intelligent, Brouillons automatiques & Nettoyeur Anti-Spam\n"
            f"{mode_text}"
        ),
        box=box.ROUNDED,
        border_style="cyan",
        title="[bold]Antigravity Local Automations[/bold]",
        subtitle="[dim]100% Local & Sécurisé[/dim]"
    )
    console.print(panel)


def display_morning_digest(results: List[Dict[str, Any]]):
    """Affiche le tableau récapitulatif du tri matinal."""
    if not results:
        console.print("[yellow]Aucun email non lu trouvé pour la période sélectionnée.[/yellow]")
        return

    table = Table(title="[bold cyan]📨 TRI DES EMAILS DU MATIN[/bold cyan]", box=box.ROUNDED, header_style="bold magenta")
    table.add_column("#", style="dim", width=4)
    table.add_column("Catégorie", style="bold", width=22)
    table.add_column("Expéditeur", style="white", width=24)
    table.add_column("Sujet", style="cyan", width=30)
    table.add_column("Résumé IA", style="green")
    table.add_column("Brouillon", style="yellow", justify="center", width=12)

    cat_styles = {
        "URGENT_CLIENT": "[bold red]🔥 Urgent Client[/bold red]",
        "A_TRAITER": "[bold blue]💼 À Traiter[/bold blue]",
        "FACTURE_COMPTA": "[bold magenta]🧾 Facture/Compta[/bold magenta]",
        "NEWSLETTER": "[dim green]📰 Newsletter[/dim green]",
        "SPAM_PUB": "[dim red]🗑️ Spam / Pub[/dim red]",
    }

    for idx, item in enumerate(results, 1):
        cat_key = item.get("category", "A_TRAITER")
        cat_formatted = cat_styles.get(cat_key, cat_key)
        has_draft = "✅ Prêt" if item.get("draft_created") else "—"
        
        table.add_row(
            str(idx),
            cat_formatted,
            item.get("sender", "")[:24],
            item.get("subject", "")[:30],
            item.get("summary", "")[:60],
            has_draft,
        )

    console.print(table)


def display_drafts_preview(drafts: List[Dict[str, Any]]):
    """Affiche les aperçus des brouillons rédigés."""
    if not drafts:
        return

    console.print("\n[bold yellow]✍️ BROUILLONS ENREGISTRÉS DANS VOTRE BOÎTE (DOSSIER DRAFTS) :[/bold yellow]")
    for idx, d in enumerate(drafts, 1):
        content = (
            f"[bold cyan]Pour :[/bold cyan] {d.get('to')}\n"
            f"[bold cyan]Sujet :[/bold cyan] {d.get('subject')}\n\n"
            f"[italic white]{d.get('body')}[/italic white]"
        )
        console.print(Panel(content, title=f"[bold green]Brouillon #{idx}[/bold green]", border_style="green", box=box.ROUNDED))


def display_spam_audit(senders: List[SenderAuditInfo], min_threshold: int = 2):
    """Affiche l'audit des expéditeurs volumineux pour le nettoyage et désabonnement."""
    table = Table(
        title="[bold red]🚫 AUDIT DES SPAMS & NEWSLETTERS ENCOMBRANTES[/bold red]",
        box=box.ROUNDED,
        header_style="bold red"
    )
    table.add_column("#", style="dim", width=4)
    table.add_column("Expéditeur", style="bold white", width=28)
    table.add_column("Emails", style="bold yellow", justify="center", width=8)
    table.add_column("Exemples de sujets récents", style="dim cyan", width=40)
    table.add_column("Désabonnement détecté ?", justify="center", width=24)

    filtered = [s for s in senders if s.count >= min_threshold]

    if not filtered:
        console.print("[green]✅ Votre boîte de réception est remarquablement propre ! Aucun expéditeur spam volumineux détecté.[/green]")
        return []

    for idx, s in enumerate(filtered[:20], 1):
        unsub_status = "[bold green]✅ 1-Click Dispo[/bold green]" if s.unsubscribe_info and s.unsubscribe_info.has_unsubscribe else "[dim yellow]⚠️ Non standard[/dim yellow]"
        samples = " | ".join(s.sample_subjects[:2])
        if len(samples) > 38:
            samples = samples[:35] + "..."

        table.add_row(
            str(idx),
            f"{s.sender_name[:15]} <{s.sender_email[:25]}>",
            str(s.count),
            samples,
            unsub_status,
        )

    console.print(table)
    return filtered
