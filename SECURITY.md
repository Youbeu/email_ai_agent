# Security & Privacy Policy 🛡️

This project is built with a **Security-First & Zero-Knowledge** architecture to guarantee maximum privacy and defense in depth.

---

## 1. Absolute Privacy (100% Local-First)
- **Zero-Cloud Leaks**: By default, the agent runs exclusively with your local **Ollama** model (`qwen2.5-coder:7b`, `llama3`, `mistral`, etc.) on `http://localhost:11434`.
- **Zero Third-Party Relays**: Your emails, drafts, and recipient data never leave your local machine.
- **Secure Credentials**: IMAP/SMTP credentials are stored exclusively in your local `.env` file, which is strictly ignored by Git via `.gitignore`.

---

## 2. Server-Side Request Forgery (SSRF) Protection
The automated unsubscribe engine (`core/unsubscriber.py`) enforces strict DNS and IP validation before dispatching any HTTP request:
- **Private Subnets Blocked**: All private ranges (`10.0.0.0/8`, `172.16.0.0/12`, `192.168.0.0/16`) are blocked.
- **Loopback & Localhost Blocked**: `127.0.0.1`, `localhost`, `::1`, `0.0.0.0` are rejected.
- **Cloud Metadata Endpoints Blocked**: `169.254.169.254` (AWS, GCP, Azure, OpenStack instance metadata) is strictly blocked.
- **Multicast & Link-Local Blocked**: All non-routable unicast public IPs are denied.

---

## 3. Prompt Injection & Jailbreak Defense
Incoming untrusted email content can potentially contain malicious instructions designed to hijack LLM behavior. The AI engine (`core/ai_brain.py`) implements:
- **Strict Boundary Delimitation**: Raw email bodies are isolated inside `<untrusted_email>` blocks.
- **System-Level Immunity Directives**: The system prompt explicitly instructs the LLM to treat the content solely as inert text for categorization/drafting and to ignore any commands or overrides contained within the body.

---

## 4. Reporting a Vulnerability
If you discover a security issue or vulnerability, please report it responsibly by contacting [@Youbeu](https://github.com/Youbeu) or by opening a private security advisory on GitHub.
