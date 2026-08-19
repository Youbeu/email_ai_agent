# Politique de Sécurité & Confidentialité 🛡️

Ce projet est conçu avec une approche **Security-First & Zero-Knowledge** :

## 1. Confidentialité Totale (100% Local par défaut)
- Par défaut, l'agent utilise votre modèle local **Ollama** (`qwen2.5-coder:7b`, `llama3`, `mistral`).
- Aucun contenu d'email ne transite par des serveurs tiers ou des clouds propriétaires.
- Les identifiants IMAP/SMTP sont stockés uniquement dans votre fichier local `.env` (exclu de Git via `.gitignore`).

## 2. Protection Anti-SSRF (Server-Side Request Forgery)
- Le module de désabonnement (`core/unsubscriber.py`) vérifie rigoureusement chaque URL avant d'exécuter une requête.
- Toutes les adresses IP privées (`10.0.0.0/8`, `172.16.0.0/12`, `192.168.0.0/16`), locales (`127.0.0.1`, `localhost`, `::1`), métadonnées cloud (`169.254.169.254`) et broadcast/multicast sont strictement bloquées.

## 3. Défense contre le Prompt Injection
- Les emails entrants non fiables sont encapsulés dans des balises de délimitation étanches (`<untrusted_email>`).
- Le prompt système applique une consigne stricte de non-exécution des instructions malveillantes contenues dans le corps des messages.

## 4. Signalement d'une vulnérabilité
Si vous découvrez une faille de sécurité, veuillez ouvrir une issue ou contacter le mainteneur en privé.
