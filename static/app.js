/* =========================================================
   EMAIL AI AGENT - FRONTEND CONTROLLER (100% GMAIL DIRECT)
   ========================================================= */

let currentEmails = [];
let selectedEmail = null;
let currentFilter = "ALL";

document.addEventListener("DOMContentLoaded", () => {
  initTabs();
  initEventListeners();
  loadAppStatus();
  fetchEmails();
  fetchSpamAudit();
});

/* Toast Notification Utility */
function showToast(message, type = "success") {
  const container = document.getElementById("toast-container");
  const toast = document.createElement("div");
  toast.className = `toast ${type}`;
  
  const icon = type === "success" ? "✅" : (type === "error" ? "❌" : "ℹ️");
  toast.innerHTML = `<span>${icon}</span><span>${message}</span>`;
  
  container.appendChild(toast);
  setTimeout(() => {
    toast.style.opacity = "0";
    toast.style.transform = "translateX(100%)";
    toast.style.transition = "all 0.3s ease";
    setTimeout(() => toast.remove(), 300);
  }, 3500);
}

/* Tabs Navigation */
function initTabs() {
  const navItems = document.querySelectorAll(".nav-item");
  const tabContents = document.querySelectorAll(".tab-content");

  navItems.forEach(item => {
    item.addEventListener("click", () => {
      const tabId = item.getAttribute("data-tab");
      
      navItems.forEach(i => i.classList.remove("active"));
      tabContents.forEach(t => t.classList.remove("active"));

      item.classList.add("active");
      const target = document.getElementById(tabId);
      if (target) target.classList.add("active");

      updatePageTitle(tabId);
    });
  });
}

function updatePageTitle(tabId) {
  const titleEl = document.getElementById("page-title-text");
  const subEl = document.getElementById("page-subtitle-text");

  if (tabId === "tab-emails") {
    titleEl.textContent = "Tri des Emails & Brouillons du Matin";
    subEl.textContent = "Boîte Gmail connectée et synchronisée en direct.";
  } else if (tabId === "tab-spam") {
    titleEl.textContent = "Nettoyeur Anti-Spam & Désabonnement";
    subEl.textContent = "Désabonnez-vous des newsletters encombrantes et nettoyez votre boîte en 1 clic.";
  } else if (tabId === "tab-settings") {
    titleEl.textContent = "Paramètres & Choix de l'IA";
    subEl.textContent = "Configurez vos accès messagerie et sélectionnez votre modèle d'intelligence artificielle.";
  }
}

/* Event Listeners */
function initEventListeners() {
  // Scan Button
  const btnScan = document.getElementById("btn-scan");
  if (btnScan) {
    btnScan.addEventListener("click", () => {
      btnScan.classList.add("loading");
      showToast("Synchronisation avec Gmail en cours...", "info");
      fetchEmails();
    });
  }

  // Audit Spam Button
  const btnAudit = document.getElementById("btn-audit-spam");
  if (btnAudit) {
    btnAudit.addEventListener("click", () => {
      showToast("Audit anti-spam en cours...", "info");
      fetchSpamAudit();
    });
  }

  // Filter Chips
  const filterChips = document.querySelectorAll(".filter-chip");
  filterChips.forEach(chip => {
    chip.addEventListener("click", () => {
      filterChips.forEach(c => c.classList.remove("active"));
      chip.classList.add("active");
      currentFilter = chip.getAttribute("data-filter");
      renderEmailsList();
    });
  });

  // Copy Draft Button
  const btnCopy = document.getElementById("btn-copy-draft");
  if (btnCopy) {
    btnCopy.addEventListener("click", () => {
      const body = document.getElementById("draft-body").value;
      if (body) {
        navigator.clipboard.writeText(body).then(() => {
          showToast("Texte du brouillon copié dans le presse-papier !");
        });
      }
    });
  }

  // Save Draft Button
  const btnSaveDraft = document.getElementById("btn-save-draft");
  if (btnSaveDraft) {
    btnSaveDraft.addEventListener("click", saveDraft);
  }

  // Save Settings Button
  const btnSaveSettings = document.getElementById("btn-save-settings");
  if (btnSaveSettings) {
    btnSaveSettings.addEventListener("click", saveSettings);
  }
}

/* API Calls */
async function loadAppStatus() {
  try {
    const res = await fetch("/api/status");
    const data = await res.json();

    const nameEl = document.getElementById("ai-current-name");
    const accountEl = document.getElementById("account-display");
    const setEmail = document.getElementById("set-email");

    if (data.email_address) {
      if (accountEl) accountEl.textContent = data.email_address;
      if (setEmail) setEmail.value = data.email_address;
    }
    if (data.ai_provider && nameEl) {
      nameEl.textContent = `Ollama (${data.ai_model || 'Local'})`;
    }
  } catch (err) {
    console.error("Erreur chargement statut:", err);
  }
}

async function fetchEmails() {
  const container = document.getElementById("emails-list-container");
  const scanStatus = document.getElementById("scan-status-text");
  if (scanStatus) scanStatus.textContent = "Lecture Gmail...";

  try {
    const res = await fetch("/api/emails/scan");
    const data = await res.json();
    currentEmails = data.emails || [];

    updateKpis();
    renderEmailsList();

    if (scanStatus) {
      scanStatus.textContent = data.is_live ? "Gmail Connecté ✅" : "Erreur connexion";
    }

    if (data.is_live) {
      showToast(`${currentEmails.length} emails synchronisés avec succès depuis Gmail !`);
    } else if (data.error) {
      showToast(`Erreur Gmail : ${data.error}`, "error");
    }

    if (currentEmails.length > 0) {
      selectEmail(currentEmails[0]);
    }
  } catch (err) {
    showToast("Erreur de connexion au serveur local", "error");
  } finally {
    const btnScan = document.getElementById("btn-scan");
    if (btnScan) btnScan.classList.remove("loading");
  }
}

function updateKpis() {
  const total = currentEmails.length;
  const drafts = currentEmails.filter(e => e.draft).length;
  const urgent = currentEmails.filter(e => e.category === "URGENT_CLIENT").length;
  const todo = currentEmails.filter(e => e.category === "A_TRAITER").length;
  const invoice = currentEmails.filter(e => e.category === "FACTURE_COMPTA").length;
  const newsletter = currentEmails.filter(e => e.category === "NEWSLETTER").length;
  const spam = currentEmails.filter(e => e.category === "SPAM_PUB").length;

  document.getElementById("kpi-total").textContent = total;
  document.getElementById("kpi-drafts").textContent = drafts;
  document.getElementById("kpi-urgent").textContent = urgent;
  document.getElementById("kpi-time").textContent = `${total * 5} min`;

  document.getElementById("count-all").textContent = total;
  document.getElementById("count-urgent").textContent = urgent;
  document.getElementById("count-todo").textContent = todo;
  document.getElementById("count-invoice").textContent = invoice;
  document.getElementById("count-newsletter").textContent = newsletter;
  document.getElementById("count-spam").textContent = spam;

  document.getElementById("badge-drafts").textContent = drafts;
}

function renderEmailsList() {
  const container = document.getElementById("emails-list-container");
  container.innerHTML = "";

  const filtered = currentFilter === "ALL" 
    ? currentEmails 
    : currentEmails.filter(e => e.category === currentFilter);

  if (filtered.length === 0) {
    container.innerHTML = `
      <div class="empty-state" style="padding: 40px 0;">
        <div class="empty-icon">📭</div>
        <p>Aucun email dans cette catégorie.</p>
      </div>`;
    return;
  }

  filtered.forEach(em => {
    const card = document.createElement("div");
    const isSelected = selectedEmail && selectedEmail.uid === em.uid;
    card.className = `email-card ${isSelected ? "active" : ""}`;

    const badgeClass = getBadgeClass(em.category);
    const hasDraftText = em.draft ? `<span class="draft-indicator">✍️ Brouillon prêt</span>` : ``;

    card.innerHTML = `
      <div class="email-top-row">
        <span class="email-category-badge ${badgeClass}">${em.category_label || em.category}</span>
        <span class="email-date">${em.date}</span>
      </div>
      <div class="email-sender">${em.sender_name}</div>
      <div class="email-subject">${em.subject}</div>
      <div class="email-summary">${em.summary}</div>
      <div class="email-footer-row">
        ${hasDraftText}
      </div>
    `;

    card.addEventListener("click", () => selectEmail(em));
    container.appendChild(card);
  });
}

function getBadgeClass(category) {
  switch (category) {
    case "URGENT_CLIENT": return "badge-urgent";
    case "A_TRAITER": return "badge-todo";
    case "FACTURE_COMPTA": return "badge-invoice";
    case "NEWSLETTER": return "badge-newsletter";
    case "SPAM_PUB": return "badge-spam";
    default: return "badge-todo";
  }
}

function selectEmail(emailData) {
  selectedEmail = emailData;
  renderEmailsList();

  const emptyState = document.getElementById("draft-empty-state");
  const draftForm = document.getElementById("draft-form");
  const categoryBadge = document.getElementById("draft-category-badge");

  if (!emailData) {
    emptyState.style.display = "block";
    draftForm.style.display = "none";
    return;
  }

  emptyState.style.display = "none";
  draftForm.style.display = "flex";

  categoryBadge.textContent = emailData.category_label || emailData.category;
  document.getElementById("draft-recipient").value = `${emailData.sender_name} <${emailData.sender_email}>`;

  if (emailData.draft) {
    document.getElementById("draft-subject").value = emailData.draft.subject;
    document.getElementById("draft-body").value = emailData.draft.body;
  } else {
    document.getElementById("draft-subject").value = `Re: ${emailData.subject}`;
    document.getElementById("draft-body").value = `Bonjour ${emailData.sender_name.split(" ")[0]},\n\nMerci pour votre retour.\n\nCordialement,\n[Votre Nom]`;
  }
}

async function saveDraft() {
  if (!selectedEmail) return;

  const recipient = selectedEmail.sender_email;
  const subject = document.getElementById("draft-subject").value;
  const body = document.getElementById("draft-body").value;

  try {
    const res = await fetch("/api/drafts/save", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        uid: selectedEmail.uid,
        recipient: recipient,
        subject: subject,
        body: body
      })
    });

    const data = await res.json();
    if (data.success) {
      showToast(data.message || "Brouillon enregistré dans votre dossier Brouillons Gmail !");
    } else {
      showToast(data.detail || "Erreur lors de l'enregistrement", "error");
    }
  } catch (err) {
    showToast("Erreur de connexion au serveur", "error");
  }
}

/* Anti-Spam & Désabonnement */
async function fetchSpamAudit() {
  const tbody = document.getElementById("spam-table-body");
  if (!tbody) return;

  try {
    const res = await fetch("/api/spam/audit");
    const data = await res.json();
    const senders = data.senders || [];

    document.getElementById("badge-spam").textContent = senders.length;
    tbody.innerHTML = "";

    if (senders.length === 0) {
      tbody.innerHTML = `<tr><td colspan="5" style="text-align: center; color: var(--text-muted); padding: 30px;">Aucun expéditeur de spam volumineux détecté dans Gmail.</td></tr>`;
      return;
    }

    senders.forEach((s, idx) => {
      const tr = document.createElement("tr");
      const samples = s.sample_subjects.join(" | ");
      const unsubBadge = s.has_unsubscribe 
        ? `<span class="badge-tag" style="background: rgba(16,185,129,0.2); color:#A7F3D0;">✅ 1-Click Dispo</span>`
        : `<span class="badge-tag" style="background: rgba(245,158,11,0.2); color:#FDE68A;">⚠️ Manuel</span>`;

      tr.innerHTML = `
        <td>
          <div style="font-weight: 600;">${s.sender_name}</div>
          <div style="font-size: 11.5px; color: var(--text-dim);">${s.sender_email}</div>
        </td>
        <td><strong style="color: var(--accent-yellow);">${s.count}</strong> emails</td>
        <td style="color: var(--text-muted); font-size: 12px; max-width: 250px; overflow: hidden; text-overflow: ellipsis; white-space: nowrap;">${samples}</td>
        <td>${unsubBadge}</td>
        <td>
          <div class="table-actions">
            ${s.has_unsubscribe ? `<button class="btn btn-sm btn-success btn-unsub" data-url="${s.unsubscribe_url}">1-Click Désabo</button>` : ``}
            <button class="btn btn-sm btn-danger btn-del-spam" data-sender="${s.sender_email}" data-uids='${JSON.stringify(s.uids)}'>Nettoyer</button>
          </div>
        </td>
      `;

      tbody.appendChild(tr);
    });

    document.querySelectorAll(".btn-unsub").forEach(btn => {
      btn.addEventListener("click", async (e) => {
        const url = btn.getAttribute("data-url");
        btn.textContent = "⏳ Traitement...";
        btn.disabled = true;

        try {
          const res = await fetch("/api/spam/unsubscribe", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ url: url, one_click: true })
          });
          const result = await res.json();
          if (result.success) {
            showToast("Désabonnement réussi ! Vous ne recevrez plus ces emails.");
            btn.textContent = "✅ Désabonné";
          } else {
            showToast("Ouverture de la page de désabonnement...", "info");
            window.open(url, "_blank");
            btn.textContent = "🌐 Vérifié";
          }
        } catch (err) {
          showToast("Erreur désabonnement", "error");
          btn.disabled = false;
        }
      });
    });

    document.querySelectorAll(".btn-del-spam").forEach(btn => {
      btn.addEventListener("click", async () => {
        const sender = btn.getAttribute("data-sender");
        const uids = JSON.parse(btn.getAttribute("data-uids"));

        if (confirm(`Voulez-vous vraiment déplacer les emails de "${sender}" vers la corbeille Gmail ?`)) {
          btn.textContent = "Nettoyage...";
          btn.disabled = true;

          try {
            const res = await fetch("/api/spam/delete", {
              method: "POST",
              headers: { "Content-Type": "application/json" },
              body: JSON.stringify({ sender_email: sender, uids: uids })
            });
            const result = await res.json();
            showToast(result.message || "Emails nettoyés avec succès !");
            fetchSpamAudit();
          } catch (err) {
            showToast("Erreur lors du nettoyage", "error");
          }
        }
      });
    });

  } catch (err) {
    console.error("Erreur spam audit:", err);
  }
}

/* Paramètres */
async function saveSettings() {
  const email = document.getElementById("set-email").value;
  const password = document.getElementById("set-password").value;
  const provider = document.getElementById("set-ai-provider").value;
  const geminiKey = document.getElementById("set-gemini-key").value;
  const tone = document.getElementById("set-tone").value;
  const signature = document.getElementById("set-signature").value;

  try {
    const res = await fetch("/api/settings", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        email_address: email,
        email_password: password,
        ai_provider: provider,
        gemini_key: geminiKey,
        tone: tone,
        signature: signature
      })
    });

    const data = await res.json();
    if (data.success) {
      showToast("Paramètres sauvegardés avec succès !");
      loadAppStatus();
      fetchEmails();
    }
  } catch (err) {
    showToast("Erreur lors de la sauvegarde", "error");
  }
}
