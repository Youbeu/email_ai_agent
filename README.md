# 📬 Email AI Agent - Assistant Local de Tri, Brouillons & Anti-Spam

[![Python Version](https://img.shields.io/badge/python-3.10%2B-blue.svg)](https://www.python.org/)
[![License: MIT](https://img.shields.io/badge/License-MIT-green.svg)](LICENSE)
[![Security Hardened](https://img.shields.io/badge/Security-SSRF%20Protected-brightgreen.svg)](SECURITY.md)
[![Privacy First](https://img.shields.io/badge/Privacy-100%25%20Local%20Ollama-orange.svg)](SECURITY.md)

Agent autonome et application Desktop 100% locale en Python pour trier votre boîte mail, préparer des brouillons de réponse le matin et nettoyer le spam / vous désabonner en 1 clic grâce à votre modèle IA local (Ollama / Qwen2.5 / Llama 3).

---

## 🌟 Fonctionnalités

- 📨 **Tri & Catégorisation du Matin** : Classe les emails reçus (`🔥 Urgent Client`, `💼 À Traiter`, `🧾 Facture/Compta`, `📰 Newsletter`, `🗑️ Spam/Pub`).
- ✍️ **Rédaction Automatique de Brouillons** : Prépare des réponses personnalisées et polies directement injectées dans votre dossier **Brouillons / Drafts** de votre boîte mail (aucun envoi automatique sans accord).
- 🚫 **Anti-Spam & Désabonnement 1-Click** :
  - Détection automatique des en-têtes officiels RFC `List-Unsubscribe` et des liens HTML de désinscription.
  - Audit visuel des plus gros expéditeurs et suppression en masse des courriers indésirables.
- 🛡️ **Sécurité & Confidentialité Totale** :
  - **Moteur IA Local par défaut** (Ollama / Qwen2.5 / Llama 3) : zéro donnée envoyée sur le cloud.
  - **Protection Anti-SSRF** intégrée contre le scan de réseaux privés lors des requêtes de désabonnement.
  - **Défense Anti-Prompt Injection** pour neutraliser les tentatives de manipulation via des emails frauduleux.
- 🖥️ **Application Desktop Native Windows** : Interface moderne et responsive (Dark mode / Glassmorphism) sans dépendance cloud.

---

## 🏗️ Architecture du Projet

```
email_ai_agent/
├── desktop_app.py            # Point d'entrée de l'application Desktop native Windows
├── server.py                 # Serveur API FastAPI local
├── email_agent.py            # Point d'entrée CLI (Morning routine, Anti-spam, Setup)
├── config.yaml               # Configuration des catégories et modèles IA
├── .env.example              # Gabarit pour identifiants sécurisés (hors Git)
├── core/
│   ├── email_client.py       # Client IMAP/SMTP robuste avec gestion des Brouillons
│   ├── ai_brain.py           # Analyseur IA sécurisé (Ollama / Gemini / Heuristique)
│   ├── unsubscriber.py       # Module de désabonnement durci avec protection Anti-SSRF
│   └── spam_cleaner.py       # Moteur d'audit et nettoyage de boîte
├── ui/
│   └── dashboard.py          # Interface terminal riche (Rich)
├── static/                   # Interface graphique Desktop (HTML / CSS / JS Vanilla)
└── run_morning_routine.bat   # Lanceur rapide Windows
```

---

## 🚀 Installation & Démarrage Rapide

### 1. Cloner le dépôt et installer les dépendances
```bash
git clone https://github.com/votre-nom/email_ai_agent.git
cd email_ai_agent
pip install -r requirements.txt
```

### 2. Configuration (.env)
Copiez le modèle d'environnement :
```bash
cp .env.example .env
```
Remplissez votre adresse email et votre mot de passe d'application dans `.env` :
```env
EMAIL_ADDRESS=votre_email@gmail.com
EMAIL_PASSWORD=votre_mot_de_passe_d_application
```

> **Note Gmail** : Activez la validation en 2 étapes sur votre compte Google, puis générez un **Mot de passe des applications** (16 caractères) dans *Compte Google > Sécurité > Mots de passe des applications*.

### 3. Lancer avec votre modèle IA local (Ollama)
Assurez-vous qu'Ollama tourne sur votre machine :
```bash
ollama run qwen2.5-coder:7b
```
*(ou `ollama run llama3` / `mistral`)*

---

## 🖥️ Utilisation

### Mode Desktop (Interface Graphique)
Double-cliquez sur `Lancer_Application_Desktop.bat` ou lancez :
```bash
python desktop_app.py
```

### Mode Ligne de Commande (CLI)
- **Tester en mode Démo (sans configuration)** :
  ```bash
  python email_agent.py --demo
  ```
- **Lancer le tri et la rédaction de brouillons du matin** :
  ```bash
  python email_agent.py --morning --live
  ```
- **Lancer l'audit de spams et l'assistant de désabonnement** :
  ```bash
  python email_agent.py --clean-spam --live
  ```

---

## 🛡️ Sécurité

Consultez [SECURITY.md](SECURITY.md) pour les détails sur la politique de sécurité et les défenses Anti-SSRF et Anti-Prompt Injection.

---

## 📄 Licence

Ce projet est sous licence MIT - voir le fichier [LICENSE](LICENSE) pour plus de détails.
