# 📬 Email AI Agent - Local-First AI Email Triage, Auto-Drafts & Anti-Spam

[![GitHub Stars](https://img.shields.io/github/stars/Youbeu/email_ai_agent?style=flat-square)](https://github.com/Youbeu/email_ai_agent/stargazers)
[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg?style=flat-square)](LICENSE)
[![Python Version](https://img.shields.io/badge/Python-3.10%2B-3776AB.svg?style=flat-square&logo=python&logoColor=white)](https://www.python.org/)
[![Privacy: 100% Local](https://img.shields.io/badge/Privacy-100%25%20Local%20Ollama-success?style=flat-square&logo=ollama&logoColor=white)](SECURITY.md)
[![Security: Hardened](https://img.shields.io/badge/Security-SSRF%20Protected-brightgreen?style=flat-square&logo=security&logoColor=white)](SECURITY.md)
[![Author](https://img.shields.io/badge/Author-Youbeu-indigo.svg?style=flat-square)](https://github.com/Youbeu)

An autonomous, **100% local-first** AI email assistant and native Desktop application built in Python. It automatically triages your morning inbox, drafts contextual replies into your native email Drafts folder, and lets you clean spam and unsubscribe from newsletters with a single click using your **local Ollama models** (`qwen2.5-coder:7b`, `llama3`, `mistral`).

---

## 🌟 Core Features

- 📨 **Intelligent Morning Email Triage**: Automatically categorizes unread emails into meaningful badges (`🔥 Urgent / Client`, `💼 Action Required`, `🧾 Invoices / Accounting`, `📰 Newsletters`, `🗑️ Spam / Marketing`).
- ✍️ **Context-Aware Auto-Drafting**: Generates polite, personalized replies ready for review directly in your native **Drafts** folder. *Zero automatic sending without your explicit review.*
- 🚫 **1-Click Unsubscribe & Bulk Spam Cleaning**:
  - Automatically parses RFC 2369 & RFC 8058 `List-Unsubscribe` headers and HTML body unsubscribe links.
  - Visual audit of top senders with one-click safe unsubscribe requests and bulk deletion into trash.
- 🔒 **Privacy-First & Local-First (Default: Ollama)**:
  - Powered by your local Ollama instance (`qwen2.5-coder:7b`, `llama3`, `mistral`) at `http://localhost:11434`.
  - Your emails and personal data **never** leave your computer.
  - Instant heuristic offline rule engine fallback (0 ms) if Ollama is not yet started.
- 🛡️ **Enterprise-Grade Security Hardening**:
  - **Anti-SSRF Protection**: Strict IP/DNS resolver filtering blocking private networks (`10.x`, `192.168.x`, `172.x`), loopback (`127.0.0.1`), and cloud metadata (`169.254.169.254`).
  - **Prompt Injection Defense**: Untrusted email bodies are isolated inside `<untrusted_email>` blocks with strict system overrides.
  - **Zero Credential Leaks**: Strict `.gitignore` protecting all credentials and environment files.
- 🖥️ **Native Desktop Application**: Sleek dark glassmorphism interface powered by PyWebView & FastAPI. Includes 1-click Windows desktop shortcut.

---

## 🏗️ Architecture

```
email_ai_agent/
├── desktop_app.py            # Native Windows Desktop Application entry point (PyWebView)
├── server.py                 # Local FastAPI REST backend
├── email_agent.py            # CLI entry point (Morning scan, Spam audit, Setup wizard)
├── config.yaml               # Category rules & AI model configurations
├── .env.example              # Template for secure local credentials
├── core/
│   ├── email_client.py       # Universal IMAP/SMTP client with native Drafts synchronization
│   ├── ai_brain.py           # Secure AI engine (Ollama / Gemini / Heuristics)
│   ├── unsubscriber.py       # Hardened unsubscribe engine with SSRF validation
│   └── spam_cleaner.py       # Mailbox audit & bulk cleaning engine
├── ui/
│   └── dashboard.py          # Rich terminal dashboard UI
├── static/                   # Desktop UI assets (HTML5 / Vanilla CSS / Modern JS)
├── requirements.txt          # Minimal production dependencies
├── SECURITY.md               # Comprehensive security & privacy specifications
└── LICENSE                   # MIT License
```

---

## 🚀 Quick Start

### 1. Clone the Repository & Install Dependencies
```bash
git clone https://github.com/Youbeu/email_ai_agent.git
cd email_ai_agent
pip install -r requirements.txt
```

### 2. Configure Your Email Credentials
Copy the example environment file:
```bash
cp .env.example .env
```
Edit `.env` with your email and application password:
```env
EMAIL_ADDRESS=your_email@gmail.com
EMAIL_PASSWORD=your_app_password
```

> 💡 **Gmail Tip**: Enable 2-Step Verification in your Google Account, then generate an **App Password** (16 characters) under *Google Account > Security > App Passwords*.

### 3. Ensure Your Local Ollama Model is Running
```bash
ollama run qwen2.5-coder:7b
```
*(or `ollama run llama3` / `mistral`)*

---

## 🖥️ Usage

### Native Desktop Application
Double-click `Lancer_Application_Desktop.bat` or run:
```bash
python desktop_app.py
```

### Command-Line Interface (CLI)
- **Run in Demo Mode (No credentials required)**:
  ```bash
  python email_agent.py --demo
  ```
- **Run Morning Routine (Triage + Auto-Drafts)**:
  ```bash
  python email_agent.py --morning --live
  ```
- **Run Spam Audit & Unsubscribe Helper**:
  ```bash
  python email_agent.py --clean-spam --live
  ```
- **Interactive Configuration Wizard**:
  ```bash
  python email_agent.py --setup
  ```

---

## ⚙️ Configuration (`config.yaml`)

You can customize your AI engine, categories, and prompts in `config.yaml`:
```yaml
ai:
  provider: "ollama"           # "ollama" (Local), "gemini", "openai", "claude", "heuristic"
  model: "qwen2.5-coder:7b"     # Local Ollama model tag
  ollama_url: "http://localhost:11434"
  tone: "professional, polite, concise, and helpful"
  user_signature: "Best regards,\n[Your Name]"
```

---

## 🛡️ Security & Privacy

Please refer to [SECURITY.md](SECURITY.md) for full details regarding our SSRF prevention, prompt injection mitigation, and zero-knowledge data guarantees.

---

## 📄 License

Distributed under the MIT License. See [LICENSE](LICENSE) for more information.

---

## 👤 Author

**Youbeu**
- GitHub: [@Youbeu](https://github.com/Youbeu)
