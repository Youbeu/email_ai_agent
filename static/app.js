/* =========================================================
   EMAIL AI AGENT - FRONTEND CONTROLLER (ROBUST & RESILIENT)
   ========================================================= */

let currentFolder = "inbox";
let currentEmails = [];
let selectedEmail = null;
let currentFilter = "ALL";
let spamEmailsList = [];
let hasLoadedSpam = false;

document.addEventListener("DOMContentLoaded", () => {
  initTabs();
  initFolderSelector();
  initEventListeners();
  loadAppStatusWithRetry(3);
  fetchEmails(currentFolder);
});

/* Toast Notification Utility */
function showToast(message, type = "success") {
  const container = document.getElementById("toast-container");
  if (!container) return;
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

/* Helper Fetch avec Retry */
async function fetchWithRetry(url, options = {}, retries = 3, delay = 1000) {
  for (let i = 0; i < retries; i++) {
    try {
      const res = await fetch(url, options);
      if (res.ok) return res;
    } catch (err) {
      if (i === retries - 1) throw err;
      await new Promise(r => setTimeout(r, delay));
    }
  }
  throw new Error("Impossible de joindre le serveur local.");
}

/* Folder Selector */
function initFolderSelector() {
  const btnInbox = document.getElementById("btn-folder-inbox");
  const btnSpam = document.getElementById("btn-folder-spam");

  if (btnInbox) {
    btnInbox.addEventListener("click", () => {
      if (currentFolder === "inbox") return;
      currentFolder = "inbox";
      btnInbox.classList.add("active");
      if (btnSpam) btnSpam.classList.remove("active");
      updateFolderView();
      fetchEmails("inbox");
    });
  }

  if (btnSpam) {
    btnSpam.addEventListener("click", () => {
      if (currentFolder === "spam") return;
      currentFolder = "spam";
      btnSpam.classList.add("active");
      if (btnInbox) btnInbox.classList.remove("active");
      updateFolderView();
      fetchEmails("spam");
    });
  }
}

function updateFolderView() {
  const titleEl = document.getElementById("page-title-text");
  const subEl = document.getElementById("page-subtitle-text");
  const paneTitle = document.getElementById("pane-folder-title");

  if (currentFolder === "spam") {
    if (titleEl) titleEl.textContent = "Fouille du Dossier Spam ([Gmail]/Spam)";
    if (subEl) subEl.textContent = "Emails bloqués par le filtre Google Spam. Restaurez les faux positifs et désabonnez-vous.";
    if (paneTitle) paneTitle.textContent = "Dossier [Gmail]/Spam";
  } else {
    if (titleEl) titleEl.textContent = "Tri des Emails & Brouillons du Matin";
    if (subEl) subEl.textContent = "Boîte Gmail principale connectée et synchronisée en direct.";
    if (paneTitle) paneTitle.textContent = "Boîte de réception Gmail";
  }
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

      // Charger le dossier Spam au premier clic sur l'onglet
      if (tabId === "tab-spam" && !hasLoadedSpam) {
        hasLoadedSpam = true;
        fetchSpamFolderEmails();
      }
    });
  });
}

function updatePageTitle(tabId) {
  const titleEl = document.getElementById("page-title-text");
  const subEl = document.getElementById("page-subtitle-text");

  if (tabId === "tab-emails") {
    updateFolderView();
  } else if (tabId === "tab-spam") {
    titleEl.textContent = "Centre de Fouille Anti-Spam & Désabonnement";
    subEl.textContent = "Analysez tous les messages du dossier [Gmail]/Spam et déplacez les emails importants vers la boîte de réception.";
  } else if (tabId === "tab-settings") {
    titleEl.textContent = "Paramètres & Choix de l'IA";
    subEl.textContent = "Configurez vos accès messagerie et sélectionnez votre modèle d'intelligence artificielle.";
  }
}

/* Event Listeners */
function initEventListeners() {
  // Scan Button (Top Bar)
  const btnScan = document.getElementById("btn-scan");
  if (btnScan) {
    btnScan.addEventListener("click", () => {
      btnScan.classList.add("loading");
      showToast(`Scan du dossier ${currentFolder === 'spam' ? 'Spam' : 'Réception'} en cours...`, "info");
      fetchEmails(currentFolder);
    });
  }

  // Scan Spam Deep (Tab 2)
  const btnScanSpamDeep = document.getElementById("btn-scan-spam-deep");
  if (btnScanSpamDeep) {
    btnScanSpamDeep.addEventListener("click", () => {
      showToast("Fouille approfondie du dossier [Gmail]/Spam...", "info");
      fetchSpamFolderEmails();
    });
  }

  // Audit Senders (Tab 2)
  const btnAudit = document.getElementById("btn-audit-senders");
  if (btnAudit) {
    btnAudit.addEventListener("click", () => {
      showToast("Audit des expéditeurs volumineux...", "info");
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

  // Restore Spam to Inbox Button (Draft pane)
  const btnRestoreInbox = document.getElementById("btn-restore-to-inbox");
  if (btnRestoreInbox) {
    btnRestoreInbox.addEventListener("click", () => {
      if (selectedEmail) {
        restoreEmailToInbox(selectedEmail.uid);
      }
    });
  }

  // Save Settings Button
  const btnSaveSettings = document.getElementById("btn-save-settings");
  if (btnSaveSettings) {
    btnSaveSettings.addEventListener("click", saveSettings);
  }
}

/* API Calls */
async function loadAppStatusWithRetry(retries = 3) {
  try {
    const res = await fetchWithRetry("/api/status", {}, retries, 800);
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
    console.warn("Statut non récupéré immédiatement, en attente:", err);
  }
}

async function fetchEmails(folder = "inbox") {
  const container = document.getElementById("emails-list-container");
  const scanStatus = document.getElementById("scan-status-text");
  if (scanStatus) scanStatus.textContent = `Lecture ${folder === 'spam' ? '[Gmail]/Spam' : 'Gmail'}...`;

  try {
    const res = await fetchWithRetry(`/api/emails/scan?folder=${folder}`, {}, 2, 1000);
    const data = await res.json();
    currentEmails = data.emails || [];

    updateKpis();
    renderEmailsList();

    if (scanStatus) {
      scanStatus.textContent = data.is_live ? "Gmail Connecté ✅" : "Erreur connexion";
    }

    if (data.is_live) {
      showToast(`${currentEmails.length} emails synchronisés depuis ${folder === 'spam' ? 'le dossier Spam' : 'la boîte de réception'} !`);
    } else if (data.error) {
      showToast(`Erreur : ${data.error}`, "error");
    }

    if (currentEmails.length > 0) {
      selectEmail(currentEmails[0]);
    }
  } catch (err) {
    console.error(err);
    if (scanStatus) scanStatus.textContent = "Erreur serveur";
    showToast("Connexion au serveur local en cours...", "info");
  } finally {
    const btnScan = document.getElementById("btn-scan");
    if (btnScan) btnScan.classList.remove("loading");
  }
}

function updateKpis() {
  const total = currentEmails.length;
  const drafts = currentEmails.filter(e => e.draft).length;
  const urgent = currentEmails.filter(e => e.category === "URGENT_CLIENT" || e.is_false_positive).length;
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
        <p>Aucun email dans ce dossier / cette catégorie.</p>
      </div>`;
    return;
  }

  filtered.forEach(em => {
    const card = document.createElement("div");
    const isSelected = selectedEmail && selectedEmail.uid === em.uid;
    card.className = `email-card ${isSelected ? "active" : ""}`;

    const badgeClass = getBadgeClass(em.category);
    const hasDraftText = em.draft ? `<span class="draft-indicator">✍️ Brouillon prêt</span>` : ``;
    const isSpamFolderBadge = em.folder === "spam" ? `<span class="badge-tag" style="background: rgba(239,68,68,0.2); color:#FCA5A5; font-size:10px;">Dossier Spam</span>` : ``;

    card.innerHTML = `
      <div class="email-top-row">
        <div style="display:flex; gap:6px; align-items:center;">
          <span class="email-category-badge ${badgeClass}">${em.category_label || em.category}</span>
          ${isSpamFolderBadge}
        </div>
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
  const spamBanner = document.getElementById("spam-action-banner");

  if (!emailData) {
    emptyState.style.display = "block";
    draftForm.style.display = "none";
    return;
  }

  emptyState.style.display = "none";
  draftForm.style.display = "flex";

  categoryBadge.textContent = emailData.category_label || emailData.category;
  document.getElementById("draft-recipient").value = `${emailData.sender_name} <${emailData.sender_email}>`;

  // Display Restore Banner if email is in Spam folder
  if (emailData.folder === "spam" || currentFolder === "spam") {
    if (spamBanner) spamBanner.style.display = "flex";
  } else {
    if (spamBanner) spamBanner.style.display = "none";
  }

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
      showToast(data.message || "Brouillon enregistré dans votre dossier Brouillons !");
    } else {
      showToast(data.detail || "Erreur lors de l'enregistrement", "error");
    }
  } catch (err) {
    showToast("Erreur de connexion au serveur", "error");
  }
}

/* Restauration d'un email de Spam vers Inbox */
async function restoreEmailToInbox(uid) {
  try {
    const res = await fetch("/api/spam/restore", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ uid: uid, folder: "[Gmail]/Spam" })
    });

    const data = await res.json();
    if (data.success) {
      showToast("Email restauré vers votre Boîte de Réception avec succès ! 📥");
      fetchEmails(currentFolder);
      fetchSpamFolderEmails();
    } else {
      showToast(data.detail || "Erreur de restauration", "error");
    }
  } catch (err) {
    showToast("Erreur serveur lors de la restauration", "error");
  }
}

/* Fouille Approfondie du Dossier Spam (TAB 2) */
async function fetchSpamFolderEmails() {
  const tbody = document.getElementById("spam-table-body");
  const countBadge = document.getElementById("spam-table-count");
  const title = document.getElementById("spam-table-title");

  if (title) title.textContent = "Emails Détectés dans [Gmail]/Spam";
  if (!tbody) return;

  try {
    const res = await fetchWithRetry("/api/spam/scan", {}, 2, 1000);
    const data = await res.json();
    spamEmailsList = data.emails || [];

    if (countBadge) countBadge.textContent = `${spamEmailsList.length} email(s)`;
    document.getElementById("badge-spam").textContent = spamEmailsList.length;
    tbody.innerHTML = "";

    if (spamEmailsList.length === 0) {
      tbody.innerHTML = `<tr><td colspan="4" style="text-align: center; color: var(--text-muted); padding: 30px;">Dossier [Gmail]/Spam vide ou aucun spam récent détecté.</td></tr>`;
      return;
    }

    spamEmailsList.forEach(em => {
      const tr = document.createElement("tr");
      
      const isUrgentOrLegit = em.is_false_positive || em.category === "URGENT_CLIENT" || em.category === "A_TRAITER";
      const diagBadge = isUrgentOrLegit 
        ? `<span class="badge-tag" style="background: rgba(16,185,129,0.2); color:#A7F3D0;">🔥 Faux Positif (Important)</span>`
        : `<span class="badge-tag" style="background: rgba(239,68,68,0.2); color:#FCA5A5;">🗑️ Vrai Spam</span>`;

      const unsubBadge = em.has_unsubscribe 
        ? `<button class="btn btn-sm btn-secondary btn-unsub-item" data-url="${em.unsubscribe_url}">🚫 Désabo 1-Click</button>`
        : `<span style="color:var(--text-dim); font-size:11px;">Pas de lien auto</span>`;

      tr.innerHTML = `
        <td>
          <div style="font-weight: 600; color: var(--text-main);">${em.sender_name} <span style="font-size:11px; color:var(--text-dim);">&lt;${em.sender_email}&gt;</span></div>
          <div style="font-size: 12.5px; color: var(--accent-cyan); margin-top:2px;">${em.subject}</div>
          <div style="font-size: 11px; color: var(--text-muted); max-width:320px; overflow:hidden; text-overflow:ellipsis; white-space:nowrap;">${em.snippet}</div>
        </td>
        <td>${diagBadge}</td>
        <td>${unsubBadge}</td>
        <td>
          <div class="table-actions">
            <button class="btn btn-sm btn-success btn-restore-item" data-uid="${em.uid}" title="Déplacer vers la boîte de réception principale">
              📥 Restaurer dans Inbox
            </button>
            <button class="btn btn-sm btn-danger btn-delete-item" data-uid="${em.uid}">
              🗑️ Supprimer
            </button>
          </div>
        </td>
      `;

      tbody.appendChild(tr);
    });

    // Event listeners for action buttons
    document.querySelectorAll(".btn-restore-item").forEach(btn => {
      btn.addEventListener("click", () => {
        const uid = btn.getAttribute("data-uid");
        btn.textContent = "⏳ Restauration...";
        btn.disabled = true;
        restoreEmailToInbox(uid);
      });
    });

    document.querySelectorAll(".btn-unsub-item").forEach(btn => {
      btn.addEventListener("click", async () => {
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
            showToast("Désabonnement réussi !");
            btn.textContent = "✅ Désabonné";
          } else {
            window.open(url, "_blank");
            btn.textContent = "🌐 Vérifié";
          }
        } catch (err) {
          showToast("Erreur désabonnement", "error");
          btn.disabled = false;
        }
      });
    });

    document.querySelectorAll(".btn-delete-item").forEach(btn => {
      btn.addEventListener("click", async () => {
        const uid = btn.getAttribute("data-uid");
        if (confirm("Déplacer cet email du dossier Spam vers la corbeille ?")) {
          btn.textContent = "Suppression...";
          btn.disabled = true;
          try {
            await fetch("/api/spam/delete", {
              method: "POST",
              headers: { "Content-Type": "application/json" },
              body: JSON.stringify({ uids: [uid], folder: "spam" })
            });
            showToast("Email supprimé avec succès !");
            fetchSpamFolderEmails();
          } catch (err) {
            showToast("Erreur suppression", "error");
          }
        }
      });
    });

  } catch (err) {
    console.error("Erreur chargement spam:", err);
  }
}

/* Audit des expéditeurs volumineux */
async function fetchSpamAudit() {
  const tbody = document.getElementById("spam-table-body");
  const countBadge = document.getElementById("spam-table-count");
  const title = document.getElementById("spam-table-title");

  if (title) title.textContent = "Expéditeurs Volumineux & Publicités";
  if (!tbody) return;

  try {
    const res = await fetchWithRetry("/api/spam/audit", {}, 2, 1000);
    const data = await res.json();
    const senders = data.senders || [];

    if (countBadge) countBadge.textContent = `${senders.length} expéditeur(s)`;
    tbody.innerHTML = "";

    if (senders.length === 0) {
      tbody.innerHTML = `<tr><td colspan="4" style="text-align: center; color: var(--text-muted); padding: 30px;">Aucun expéditeur de spam volumineux détecté.</td></tr>`;
      return;
    }

    senders.forEach((s) => {
      const tr = document.createElement("tr");
      const samples = s.sample_subjects.join(" | ");

      tr.innerHTML = `
        <td>
          <div style="font-weight: 600;">${s.sender_name}</div>
          <div style="font-size: 11.5px; color: var(--text-dim);">${s.sender_email}</div>
          <div style="font-size: 11px; color: var(--text-muted);">${samples}</div>
        </td>
        <td><strong style="color: var(--accent-yellow);">${s.count} emails</strong></td>
        <td>${s.has_unsubscribe ? `<button class="btn btn-sm btn-secondary btn-unsub-item" data-url="${s.unsubscribe_url}">🚫 Désabo 1-Click</button>` : `<span style="color:var(--text-dim); font-size:11px;">Manuel</span>`}</td>
        <td>
          <button class="btn btn-sm btn-danger btn-del-sender" data-sender="${s.sender_email}" data-uids='${JSON.stringify(s.uids)}'>Nettoyer tout</button>
        </td>
      `;

      tbody.appendChild(tr);
    });

    document.querySelectorAll(".btn-del-sender").forEach(btn => {
      btn.addEventListener("click", async () => {
        const sender = btn.getAttribute("data-sender");
        const uids = JSON.parse(btn.getAttribute("data-uids"));

        if (confirm(`Déplacer les ${uids.length} emails de "${sender}" vers la corbeille ?`)) {
          btn.textContent = "Nettoyage...";
          btn.disabled = true;
          try {
            await fetch("/api/spam/delete", {
              method: "POST",
              headers: { "Content-Type": "application/json" },
              body: JSON.stringify({ sender_email: sender, uids: uids, folder: "inbox" })
            });
            showToast("Emails nettoyés avec succès !");
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
      loadAppStatusWithRetry(2);
      fetchEmails(currentFolder);
    }
  } catch (err) {
    showToast("Erreur lors de la sauvegarde", "error");
  }
}
