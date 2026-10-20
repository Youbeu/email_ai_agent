/* =========================================================
   EMAIL AI AGENT v2.0 - SECURE FRONTEND CONTROLLER (ZERO XSS)
   ========================================================= */

let currentFolder = "inbox";
let currentLimit = 25;
let currentEmails = [];
let selectedEmail = null;
let currentFilter = "ALL";
let spamEmailsList = [];
let hasLoadedSpam = false;
let hasLoadedAudit = false;

/**
 * Échappe strictement tout texte non fiable avant insertion HTML (Anti-XSS).
 */
function escapeHtml(unsafe) {
  if (unsafe === null || unsafe === undefined) return "";
  return String(unsafe)
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;")
    .replace(/'/g, "&#039;");
}

document.addEventListener("DOMContentLoaded", async () => {
  initTabs();
  initFolderSelector();
  initDepthSelector();
  initEventListeners();
  await loadAppStatusWithRetry(3);
  await loadCachedEmailsFirst(currentFolder, currentLimit);
  fetchEmails(currentFolder, currentLimit, false);
});

/* Toast Notification Utility (Safe DOM) */
function showToast(message, type = "success") {
  const container = document.getElementById("toast-container");
  if (!container) return;
  const toast = document.createElement("div");
  toast.className = `toast ${type}`;

  const iconSpan = document.createElement("span");
  iconSpan.textContent = type === "success" ? "✅" : (type === "error" ? "❌" : "ℹ️");

  const textSpan = document.createElement("span");
  textSpan.textContent = String(message || "");

  toast.appendChild(iconSpan);
  toast.appendChild(textSpan);

  container.appendChild(toast);
  setTimeout(() => {
    toast.style.opacity = "0";
    toast.style.transform = "translateX(100%)";
    toast.style.transition = "all 0.3s ease";
    setTimeout(() => toast.remove(), 300);
  }, 3500);
}

/* Helper Fetch avec Retry */
async function fetchWithRetry(url, options = {}, retries = 3, delay = 800) {
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
      fetchEmails("inbox", currentLimit, false);
    });
  }

  if (btnSpam) {
    btnSpam.addEventListener("click", () => {
      if (currentFolder === "spam") return;
      currentFolder = "spam";
      btnSpam.classList.add("active");
      if (btnInbox) btnInbox.classList.remove("active");
      updateFolderView();
      fetchEmails("spam", 45, false);
    });
  }
}

/* Depth Selector */
function initDepthSelector() {
  const depthBtns = document.querySelectorAll(".depth-btn");
  depthBtns.forEach(btn => {
    btn.addEventListener("click", () => {
      depthBtns.forEach(b => b.classList.remove("active"));
      btn.classList.add("active");
      currentLimit = parseInt(btn.getAttribute("data-limit"), 10) || 25;
      showToast(`Scan réglé sur les ${currentLimit} emails récents`, "info");
      fetchEmails(currentFolder, currentLimit, false);
    });
  });
}

function updateFolderView() {
  const titleEl = document.getElementById("page-title-text");
  const subEl = document.getElementById("page-subtitle-text");
  const paneTitle = document.getElementById("pane-folder-title");

  if (currentFolder === "spam") {
    if (titleEl) titleEl.textContent = "Inspection du Dossier Spam";
    if (subEl) subEl.textContent = "Analyse anti-phishing et détection des faux positifs légitimes.";
    if (paneTitle) paneTitle.textContent = "Dossier Spam";
  } else {
    if (titleEl) titleEl.textContent = "Tri des Emails & Brouillons";
    if (subEl) subEl.textContent = "Synchronisation IMAP directe et préparation des brouillons rattachés aux fils de discussion.";
    if (paneTitle) paneTitle.textContent = "Boîte de réception";
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

      if (tabId === "tab-spam" && !hasLoadedSpam) {
        hasLoadedSpam = true;
        fetchSpamFolderEmails(false);
      } else if (tabId === "tab-audit" && !hasLoadedAudit) {
        hasLoadedAudit = true;
        fetchSpamAudit();
      } else if (tabId === "tab-settings") {
        fetchAgentLogs();
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
    if (titleEl) titleEl.textContent = "Fouille Approfondie du Dossier Spam";
    if (subEl) subEl.textContent = "Détectez les faux positifs légitimes et supprimez ou désabonnez les spams.";
  } else if (tabId === "tab-audit") {
    if (titleEl) titleEl.textContent = "Audit des Expéditeurs Volumineux & Désabonnement";
    if (subEl) subEl.textContent = "Identifiez les newsletters récurrentes et nettoyez votre boîte en un clic.";
  } else if (tabId === "tab-settings") {
    if (titleEl) titleEl.textContent = "Paramètres & Configuration IA";
    if (subEl) subEl.textContent = "Configurez vos accès IMAP/SMTP et votre moteur d'intelligence artificielle.";
  }
}

/* Event Listeners */
function initEventListeners() {
  // Scan Button (Top Bar - Force Refresh)
  const btnScan = document.getElementById("btn-scan");
  if (btnScan) {
    btnScan.addEventListener("click", () => {
      btnScan.classList.add("loading");
      showToast(`Synchronisation IMAP (${currentFolder === "spam" ? "Spam" : "Réception"}) en cours...`, "info");
      fetchEmails(currentFolder, currentLimit, true);
    });
  }

  // Scan Spam Deep (Tab 2)
  const btnScanSpamDeep = document.getElementById("btn-scan-spam-deep");
  if (btnScanSpamDeep) {
    btnScanSpamDeep.addEventListener("click", () => {
      showToast("Fouille approfondie du dossier Spam en cours...", "info");
      fetchSpamFolderEmails(true);
    });
  }

  // Restore All False Positives Button (Tab 2)
  const btnRestoreAll = document.getElementById("btn-restore-all-false-pos");
  if (btnRestoreAll) {
    btnRestoreAll.addEventListener("click", restoreAllFalsePositives);
  }

  // Audit Senders (Tab 3)
  const btnAudit = document.getElementById("btn-audit-senders");
  if (btnAudit) {
    btnAudit.addEventListener("click", () => {
      showToast("Audit des expéditeurs volumineux en cours...", "info");
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

  // AI Intent Buttons (Generate / Regenerate Draft)
  const intentBtns = document.querySelectorAll(".btn-intent");
  intentBtns.forEach(btn => {
    btn.addEventListener("click", () => {
      const instruction = btn.getAttribute("data-instruction") || "";
      generateCustomDraft(instruction, btn);
    });
  });

  // Copy Draft Button
  const btnCopy = document.getElementById("btn-copy-draft");
  if (btnCopy) {
    btnCopy.addEventListener("click", () => {
      const body = document.getElementById("draft-body").value;
      if (body) {
        navigator.clipboard.writeText(body).then(() => {
          showToast("Brouillon copié dans le presse-papier !");
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

  // Test Connection Button
  const btnTestConn = document.getElementById("btn-test-conn");
  if (btnTestConn) {
    btnTestConn.addEventListener("click", testConnections);
  }

  // Autonomous Agent Routine Button
  const btnRoutine = document.getElementById("btn-agent-routine");
  if (btnRoutine) {
    btnRoutine.addEventListener("click", runAutonomousRoutine);
  }
}

/* Status & Initial Cache Load */
async function loadAppStatusWithRetry(retries = 3) {
  try {
    const res = await fetchWithRetry("/api/status", {}, retries, 600);
    const data = await res.json();

    const nameEl = document.getElementById("ai-current-name");
    const descEl = document.getElementById("ai-mode-desc");
    const aiDot = document.getElementById("ai-status-dot");
    const connDot = document.getElementById("conn-status-dot");
    const accountEl = document.getElementById("account-display");

    if (data.email_address) {
      if (accountEl) accountEl.textContent = data.email_address;
      const setEmail = document.getElementById("set-email");
      if (setEmail) setEmail.value = data.email_address;
    } else if (accountEl) {
      accountEl.textContent = "Compte non configuré";
    }

    if (connDot) {
      connDot.style.background = data.is_configured ? "var(--accent-green)" : "var(--accent-yellow)";
    }

    if (nameEl) {
      nameEl.textContent = data.ai_active_label || `Ollama (${data.ai_model || "Local"})`;
    }
    if (descEl) {
      descEl.textContent = data.ai_available ? "Moteur LLM Actif" : "Mode Heuristique Hors-Ligne";
    }
    if (aiDot) {
      aiDot.style.background = data.ai_available ? "var(--accent-green)" : "var(--accent-yellow)";
    }

    // Remplissage des champs de paramètres
    const setProvider = document.getElementById("set-ai-provider");
    if (setProvider && data.ai_provider) setProvider.value = data.ai_provider;

    const setModel = document.getElementById("set-ai-model");
    if (setModel && data.ai_model) setModel.value = data.ai_model;

    const setTone = document.getElementById("set-tone");
    if (setTone && data.tone) setTone.value = data.tone;

    const setSig = document.getElementById("set-signature");
    if (setSig && data.signature) setSig.value = data.signature;

    const pwdBadge = document.getElementById("pwd-status-badge");
    if (pwdBadge) {
      pwdBadge.textContent = data.has_password ? "(✅ Déjà enregistré)" : "(⚠️ Manquant)";
      pwdBadge.style.color = data.has_password ? "var(--accent-green)" : "var(--accent-yellow)";
    }

    const geminiBadge = document.getElementById("gemini-key-badge");
    if (geminiBadge) {
      geminiBadge.textContent = data.has_gemini_key ? "(✅ Clé enregistrée)" : "";
      geminiBadge.style.color = "var(--accent-green)";
    }

    if (typeof data.cached_spam_count === "number") {
      const badgeSpam = document.getElementById("badge-spam");
      if (badgeSpam) badgeSpam.textContent = data.cached_spam_count;
    }
  } catch (err) {
    console.warn("Statut non récupéré:", err);
  }
}

async function loadCachedEmailsFirst(folder = "inbox", limit = 25) {
  try {
    const res = await fetch(`/api/emails/cached?folder=${encodeURIComponent(folder)}&limit=${limit}`);
    if (!res.ok) return;
    const data = await res.json();
    if (data.emails && data.emails.length > 0 && currentEmails.length === 0) {
      currentEmails = data.emails;
      updateKpis();
      renderEmailsList();
      selectEmail(currentEmails[0]);
      const scanStatus = document.getElementById("scan-status-text");
      if (scanStatus) scanStatus.textContent = "Cache local chargé (Synchronisation...)";
    }
  } catch (_) {
    // Ignore cache load error
  }
}

async function fetchEmails(folder = "inbox", limit = 25, forceRefresh = false) {
  const scanStatus = document.getElementById("scan-status-text");
  if (scanStatus) {
    scanStatus.textContent = `Synchronisation ${folder === "spam" ? "Spam" : "INBOX"}...`;
  }

  try {
    const url = `/api/emails/scan?folder=${encodeURIComponent(folder)}&limit=${limit}&force_refresh=${forceRefresh}`;
    const res = await fetchWithRetry(url, {}, 2, 1000);
    const data = await res.json();
    currentEmails = data.emails || [];

    updateKpis();
    renderEmailsList();

    if (scanStatus) {
      scanStatus.textContent = data.is_live ? "Synchronisé ✅" : "Hors-ligne / Cache";
    }

    if (data.is_live) {
      showToast(`${currentEmails.length} email(s) analysé(s) (${folder === "spam" ? "Dossier Spam" : "Boîte de réception"}).`);
    } else if (data.error) {
      showToast(data.error, "error");
    }

    if (currentEmails.length > 0) {
      const prevUid = selectedEmail ? selectedEmail.uid : null;
      const match = prevUid ? currentEmails.find(e => e.uid === prevUid) : null;
      selectEmail(match || currentEmails[0]);
    } else {
      selectEmail(null);
    }
  } catch (err) {
    console.error(err);
    if (scanStatus) scanStatus.textContent = "Erreur réseau";
    showToast("Impossible de joindre le serveur local.", "error");
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
  document.getElementById("kpi-time").textContent = `${total * 3} min`;

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
  if (!container) return;
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
    const isSpamFolderBadge = em.folder === "spam"
      ? `<span class="badge-tag" style="background: rgba(239,68,68,0.2); color:#FCA5A5; font-size:10px;">Dossier Spam</span>`
      : ``;
    const isFalsePosBadge = em.is_false_positive
      ? `<span class="badge-tag" style="background: rgba(16,185,129,0.25); color:#A7F3D0; font-size:10px;">🔥 Faux Positif</span>`
      : ``;

    card.innerHTML = `
      <div class="email-top-row">
        <div style="display:flex; gap:6px; align-items:center; flex-wrap:wrap;">
          <span class="email-category-badge ${escapeHtml(badgeClass)}">${escapeHtml(em.category_label || em.category)}</span>
          ${isSpamFolderBadge}
          ${isFalsePosBadge}
        </div>
        <span class="email-date">${escapeHtml(em.date)}</span>
      </div>
      <div class="email-sender">${escapeHtml(em.sender_name)} <span style="font-size:11px; color:var(--text-dim); font-weight:400;">&lt;${escapeHtml(em.sender_email)}&gt;</span></div>
      <div class="email-subject">${escapeHtml(em.subject)}</div>
      <div class="email-summary">${escapeHtml(em.summary)}</div>
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
  const spamReason = document.getElementById("spam-banner-reason");

  if (!emailData) {
    if (emptyState) emptyState.style.display = "block";
    if (draftForm) draftForm.style.display = "none";
    return;
  }

  if (emptyState) emptyState.style.display = "none";
  if (draftForm) draftForm.style.display = "flex";

  if (categoryBadge) categoryBadge.textContent = emailData.category_label || emailData.category;
  document.getElementById("draft-recipient").value = `${emailData.sender_name} <${emailData.sender_email}>`;

  // Remplir le lecteur d'email complet
  const readerSender = document.getElementById("reader-sender-info");
  const readerDate = document.getElementById("reader-date-info");
  const readerBody = document.getElementById("reader-body-text");
  if (readerSender) readerSender.textContent = `De : ${emailData.sender_name} <${emailData.sender_email}>`;
  if (readerDate) readerDate.textContent = emailData.date || "";
  if (readerBody) readerBody.textContent = emailData.body_text || emailData.snippet || "(Aucun contenu texte)";

  // Afficher la bannière de restauration si l'email est dans Spam
  if (emailData.folder === "spam" || currentFolder === "spam") {
    if (spamBanner) spamBanner.style.display = "flex";
    if (spamReason) spamReason.textContent = emailData.summary || "Restaurez cet email pour le déplacer dans votre boîte de réception.";
  } else {
    if (spamBanner) spamBanner.style.display = "none";
  }

  if (emailData.draft) {
    document.getElementById("draft-subject").value = emailData.draft.subject;
    document.getElementById("draft-body").value = emailData.draft.body;
  } else {
    const subj = emailData.subject || "";
    document.getElementById("draft-subject").value = subj.toLowerCase().startsWith("re:") ? subj : `Re: ${subj}`;
    document.getElementById("draft-body").value = "";
    document.getElementById("draft-body").placeholder = "Cliquez sur un bouton « ✨ Rédiger avec l'IA » ci-dessus pour générer une réponse contextuelle, ou écrivez directement ici...";
  }
}

/* Génération / Régénération de Brouillon IA sur mesure */
async function generateCustomDraft(instruction, buttonEl) {
  if (!selectedEmail) return;

  const allIntentBtns = document.querySelectorAll(".btn-intent");
  allIntentBtns.forEach(b => (b.disabled = true));
  const origText = buttonEl ? buttonEl.textContent : "";
  if (buttonEl) buttonEl.textContent = "⏳ Rédaction IA...";

  try {
    const res = await fetch("/api/drafts/generate", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        uid: selectedEmail.uid,
        folder: selectedEmail.folder || currentFolder,
        custom_instruction: instruction,
        subject: selectedEmail.subject,
        sender_name: selectedEmail.sender_name,
        sender_email: selectedEmail.sender_email,
        body_text: selectedEmail.body_text || selectedEmail.snippet,
      }),
    });

    const data = await res.json();
    if (data.success && data.draft) {
      selectedEmail.draft = data.draft;
      document.getElementById("draft-subject").value = data.draft.subject;
      document.getElementById("draft-body").value = data.draft.body;
      const hint = document.getElementById("draft-engine-hint");
      if (hint && data.engine) hint.textContent = `Rédigé par ${data.engine}`;
      updateKpis();
      renderEmailsList();
      showToast(`Brouillon généré (${data.engine || "IA"}) !`);
    } else {
      showToast("Impossible de générer le brouillon.", "error");
    }
  } catch (err) {
    showToast("Erreur lors de la génération IA", "error");
  } finally {
    allIntentBtns.forEach(b => (b.disabled = false));
    if (buttonEl) buttonEl.textContent = origText;
  }
}

async function saveDraft() {
  if (!selectedEmail) return;

  const recipient = selectedEmail.reply_to || selectedEmail.sender_email;
  const subject = document.getElementById("draft-subject").value;
  const body = document.getElementById("draft-body").value;

  if (!body.trim()) {
    showToast("Le corps du brouillon est vide.", "error");
    return;
  }

  const btnSave = document.getElementById("btn-save-draft");
  if (btnSave) btnSave.disabled = true;

  try {
    const res = await fetch("/api/drafts/save", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        uid: selectedEmail.uid,
        folder: selectedEmail.folder || currentFolder,
        recipient: recipient,
        subject: subject,
        body: body,
        message_id: selectedEmail.message_id || "",
        references: selectedEmail.references || "",
      }),
    });

    const data = await res.json();
    if (res.ok && data.success) {
      selectedEmail.draft = { subject, body, to: recipient };
      updateKpis();
      renderEmailsList();
      showToast(data.message || "Brouillon enregistré dans votre dossier Brouillons !");
    } else {
      showToast(data.detail || "Erreur lors de l'enregistrement", "error");
    }
  } catch (err) {
    showToast("Erreur de connexion au serveur", "error");
  } finally {
    if (btnSave) btnSave.disabled = false;
  }
}

/* Restauration d'un email de Spam vers Inbox */
async function restoreEmailToInbox(uid) {
  try {
    const res = await fetch("/api/spam/restore", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ uid: String(uid), folder: "spam" }),
    });

    const data = await res.json();
    if (res.ok && data.success) {
      showToast("Email restauré et transféré vers votre Boîte de Réception ! 📥");
      spamEmailsList = spamEmailsList.filter(e => e.uid !== String(uid));
      renderSpamTable();
      if (currentFolder === "spam") {
        currentEmails = currentEmails.filter(e => e.uid !== String(uid));
        updateKpis();
        renderEmailsList();
        selectEmail(currentEmails[0] || null);
      }
    } else {
      showToast(data.detail || "Erreur de restauration", "error");
    }
  } catch (err) {
    showToast("Erreur serveur lors de la restauration", "error");
  }
}

/* Restauration en lot de tous les faux positifs */
async function restoreAllFalsePositives() {
  const falsePositives = spamEmailsList.filter(e => e.is_false_positive);
  if (falsePositives.length === 0) {
    showToast("Aucun faux positif détecté à restaurer.", "info");
    return;
  }

  const uids = falsePositives.map(e => e.uid);
  if (!confirm(`Voulez-vous restaurer les ${uids.length} faux positifs détectés vers votre boîte de réception ?`)) {
    return;
  }

  const btn = document.getElementById("btn-restore-all-false-pos");
  const btnText = document.getElementById("btn-restore-all-text");
  if (btn) btn.disabled = true;
  if (btnText) btnText.textContent = "Restauration en cours...";

  try {
    const res = await fetch("/api/spam/restore-all", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ uids: uids, folder: "spam" }),
    });
    const data = await res.json();
    if (res.ok && data.success) {
      showToast(data.message || `${data.restored_count} email(s) restauré(s) !`);
      await fetchSpamFolderEmails(false);
    } else {
      showToast(data.detail || "Erreur lors de la restauration en lot", "error");
    }
  } catch (err) {
    showToast("Erreur lors de la restauration en lot", "error");
  } finally {
    if (btn) btn.disabled = false;
  }
}

/* Fouille Approfondie du Dossier Spam (TAB 2) */
async function fetchSpamFolderEmails(forceRefresh = false) {
  const tbody = document.getElementById("spam-table-body");
  if (!tbody) return;

  tbody.innerHTML = `<tr><td colspan="4" style="text-align: center; color: var(--text-muted); padding: 30px;">Analyse du dossier Spam en cours...</td></tr>`;

  try {
    const res = await fetchWithRetry(`/api/spam/scan?force_refresh=${forceRefresh}`, {}, 2, 1000);
    const data = await res.json();
    spamEmailsList = data.emails || [];
    renderSpamTable();
  } catch (err) {
    console.error("Erreur chargement spam:", err);
    tbody.innerHTML = `<tr><td colspan="4" style="text-align: center; color: var(--accent-red); padding: 30px;">Erreur lors de la lecture du dossier Spam.</td></tr>`;
  }
}

function renderSpamTable() {
  const tbody = document.getElementById("spam-table-body");
  const countBadge = document.getElementById("spam-table-count");
  const navBadge = document.getElementById("badge-spam");
  const btnRestoreAllText = document.getElementById("btn-restore-all-text");

  if (!tbody) return;

  if (countBadge) countBadge.textContent = `${spamEmailsList.length} email(s)`;
  if (navBadge) navBadge.textContent = spamEmailsList.length;

  const falsePosCount = spamEmailsList.filter(e => e.is_false_positive).length;
  if (btnRestoreAllText) {
    btnRestoreAllText.textContent = `Restaurer les Faux Positifs (${falsePosCount})`;
  }

  tbody.innerHTML = "";

  if (spamEmailsList.length === 0) {
    tbody.innerHTML = `<tr><td colspan="4" style="text-align: center; color: var(--text-muted); padding: 30px;">Dossier Spam vide ou aucun message détecté.</td></tr>`;
    return;
  }

  spamEmailsList.forEach(em => {
    const tr = document.createElement("tr");

    const diagBadge = em.is_false_positive
      ? `<div style="display:flex; flex-direction:column; gap:3px;">
           <span class="badge-tag" style="background: rgba(16,185,129,0.25); color:#A7F3D0; font-weight:700;">🔥 Faux Positif Légitime</span>
           <span style="font-size:11px; color:var(--text-muted);">${escapeHtml(em.summary)}</span>
         </div>`
      : `<div style="display:flex; flex-direction:column; gap:3px;">
           <span class="badge-tag" style="background: rgba(239,68,68,0.2); color:#FCA5A5;">🗑️ Spam / Phishing</span>
           <span style="font-size:11px; color:var(--text-muted);">${escapeHtml(em.summary)}</span>
         </div>`;

    let unsubCell = `<span style="color:var(--text-dim); font-size:11px;">Aucun lien</span>`;
    if (em.has_unsubscribe && em.unsubscribe_url) {
      const label = em.supports_one_click ? "🚫 Désabo 1-Click" : "🌐 Lien Désabo";
      unsubCell = `<button class="btn btn-sm btn-secondary btn-unsub-spam" data-url="${escapeHtml(em.unsubscribe_url)}" data-oneclick="${em.supports_one_click ? "1" : "0"}">${label}</button>`;
    }

    tr.innerHTML = `
      <td>
        <div style="font-weight: 600; color: var(--text-main);">${escapeHtml(em.sender_name)} <span style="font-size:11px; color:var(--text-dim);">&lt;${escapeHtml(em.sender_email)}&gt;</span></div>
        <div style="font-size: 12.5px; color: var(--accent-cyan); margin-top:2px;">${escapeHtml(em.subject)}</div>
        <div style="font-size: 11px; color: var(--text-muted); max-width:320px; overflow:hidden; text-overflow:ellipsis; white-space:nowrap;">${escapeHtml(em.snippet)}</div>
      </td>
      <td>${diagBadge}</td>
      <td>${unsubCell}</td>
      <td>
        <div class="table-actions">
          <button class="btn btn-sm btn-success btn-restore-item" data-uid="${escapeHtml(em.uid)}">
            📥 Restaurer
          </button>
          <button class="btn btn-sm btn-danger btn-delete-item" data-uid="${escapeHtml(em.uid)}">
            🗑️ Supprimer
          </button>
        </div>
      </td>
    `;

    tbody.appendChild(tr);
  });

  tbody.querySelectorAll(".btn-restore-item").forEach(btn => {
    btn.addEventListener("click", () => {
      const uid = btn.getAttribute("data-uid");
      btn.textContent = "⏳...";
      btn.disabled = true;
      restoreEmailToInbox(uid);
    });
  });

  tbody.querySelectorAll(".btn-unsub-spam").forEach(btn => {
    btn.addEventListener("click", () => handleUnsubscribeClick(btn));
  });

  tbody.querySelectorAll(".btn-delete-item").forEach(btn => {
    btn.addEventListener("click", async () => {
      const uid = btn.getAttribute("data-uid");
      if (!confirm("Déplacer définitivement cet email du dossier Spam vers la Corbeille ?")) return;
      btn.textContent = "⏳...";
      btn.disabled = true;
      try {
        const res = await fetch("/api/spam/delete", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ uids: [uid], folder: "spam" }),
        });
        if (res.ok) {
          showToast("Email déplacé vers la corbeille !");
          spamEmailsList = spamEmailsList.filter(e => e.uid !== String(uid));
          renderSpamTable();
        }
      } catch (err) {
        showToast("Erreur lors de la suppression", "error");
        btn.disabled = false;
      }
    });
  });
}

async function handleUnsubscribeClick(btn) {
  const url = btn.getAttribute("data-url");
  const isOneClick = btn.getAttribute("data-oneclick") === "1";
  if (!url) return;

  btn.textContent = "⏳ Traitement...";
  btn.disabled = true;
  try {
    const res = await fetch("/api/spam/unsubscribe", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ url: url, one_click: isOneClick }),
    });
    const result = await res.json();
    if (result.success) {
      showToast(result.message || "Désabonnement exécuté avec succès !");
      btn.textContent = "✅ Désabonné";
    } else {
      showToast(result.message || "Ouverture dans le navigateur pour confirmation...", "info");
      window.open(url, "_blank", "noopener,noreferrer");
      btn.textContent = "🌐 Ouvert";
    }
  } catch (err) {
    showToast("Erreur lors du désabonnement", "error");
    btn.disabled = false;
  }
}

/* Audit des expéditeurs volumineux (TAB 3) */
async function fetchSpamAudit() {
  const tbody = document.getElementById("audit-table-body");
  const countBadge = document.getElementById("audit-table-count");
  const navBadge = document.getElementById("badge-audit");

  if (!tbody) return;
  tbody.innerHTML = `<tr><td colspan="4" style="text-align: center; color: var(--text-muted); padding: 30px;">Audit des expéditeurs récurrents en cours...</td></tr>`;

  try {
    const res = await fetchWithRetry("/api/spam/audit", {}, 2, 1000);
    const data = await res.json();
    const senders = data.senders || [];

    if (countBadge) countBadge.textContent = `${senders.length} expéditeur(s)`;
    if (navBadge) navBadge.textContent = senders.length;
    tbody.innerHTML = "";

    if (senders.length === 0) {
      tbody.innerHTML = `<tr><td colspan="4" style="text-align: center; color: var(--text-muted); padding: 30px;">Aucun expéditeur volumineux récurrent détecté.</td></tr>`;
      return;
    }

    senders.forEach(s => {
      const tr = document.createElement("tr");
      const samples = (s.sample_subjects || []).join(" | ");

      let unsubHtml = `<span style="color:var(--text-dim); font-size:11px;">Non détecté</span>`;
      if (s.has_unsubscribe && s.unsubscribe_url) {
        const label = s.supports_one_click ? "🚫 Désabo 1-Click" : "🌐 Lien Désabo";
        unsubHtml = `<button class="btn btn-sm btn-secondary btn-unsub-audit" data-url="${escapeHtml(s.unsubscribe_url)}" data-oneclick="${s.supports_one_click ? "1" : "0"}">${label}</button>`;
      }

      tr.innerHTML = `
        <td>
          <div style="font-weight: 600;">${escapeHtml(s.sender_name)}</div>
          <div style="font-size: 11.5px; color: var(--text-dim);">${escapeHtml(s.sender_email)}</div>
          <div style="font-size: 11px; color: var(--text-muted); margin-top: 2px;">${escapeHtml(samples)}</div>
        </td>
        <td><strong style="color: var(--accent-yellow);">${Number(s.count) || 0} emails</strong></td>
        <td>${unsubHtml}</td>
        <td>
          <button class="btn btn-sm btn-danger btn-del-sender">🗑️ Nettoyer (${Number(s.count) || 0})</button>
        </td>
      `;

      const delBtn = tr.querySelector(".btn-del-sender");
      if (delBtn) {
        delBtn.addEventListener("click", async () => {
          const uids = Array.isArray(s.uids) ? s.uids : [];
          if (!confirm(`Déplacer les ${uids.length} emails de « ${s.sender_email} » vers la corbeille ?`)) return;
          delBtn.textContent = "⏳ Nettoyage...";
          delBtn.disabled = true;
          try {
            const delRes = await fetch("/api/spam/delete", {
              method: "POST",
              headers: { "Content-Type": "application/json" },
              body: JSON.stringify({ sender_email: s.sender_email, uids: uids, folder: "inbox" }),
            });
            if (delRes.ok) {
              showToast(`${uids.length} emails de ${s.sender_email} déplacés vers la corbeille !`);
              tr.remove();
            }
          } catch (err) {
            showToast("Erreur lors du nettoyage", "error");
            delBtn.disabled = false;
          }
        });
      }

      tbody.appendChild(tr);
    });

    tbody.querySelectorAll(".btn-unsub-audit").forEach(btn => {
      btn.addEventListener("click", () => handleUnsubscribeClick(btn));
    });
  } catch (err) {
    console.error("Erreur spam audit:", err);
    tbody.innerHTML = `<tr><td colspan="4" style="text-align: center; color: var(--accent-red); padding: 30px;">Erreur lors de l'audit.</td></tr>`;
  }
}

/* Paramètres */
async function saveSettings() {
  const email = document.getElementById("set-email").value.trim();
  const password = document.getElementById("set-password").value;
  const provider = document.getElementById("set-ai-provider").value;
  const model = document.getElementById("set-ai-model").value.trim();
  const geminiKey = document.getElementById("set-gemini-key").value;
  const openaiKey = document.getElementById("set-openai-key").value;
  const anthropicKey = document.getElementById("set-anthropic-key").value;
  const tone = document.getElementById("set-tone").value.trim();
  const signature = document.getElementById("set-signature").value;

  try {
    const res = await fetch("/api/settings", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        email_address: email,
        email_password: password,
        ai_provider: provider,
        ai_model: model,
        gemini_key: geminiKey,
        openai_key: openaiKey,
        anthropic_key: anthropicKey,
        tone: tone,
        signature: signature,
      }),
    });

    const data = await res.json();
    if (res.ok && data.success) {
      // Vider les champs password après sauvegarde pour la sécurité visuelle
      document.getElementById("set-password").value = "";
      document.getElementById("set-gemini-key").value = "";
      document.getElementById("set-openai-key").value = "";
      document.getElementById("set-anthropic-key").value = "";

      showToast(data.message || "Paramètres sauvegardés avec succès !");
      await loadAppStatusWithRetry(2);
      await fetchAgentLogs();
    } else {
      showToast("Erreur lors de la sauvegarde des paramètres", "error");
    }
  } catch (err) {
    showToast("Erreur lors de la sauvegarde", "error");
  }
}

async function testConnections() {
  const btn = document.getElementById("btn-test-conn");
  const resultBox = document.getElementById("conn-test-result");
  if (btn) btn.disabled = true;
  if (resultBox) {
    resultBox.style.display = "block";
    resultBox.textContent = "⏳ Test de connexion IMAP et vérification du moteur IA en cours...";
  }

  // Si l'utilisateur vient de saisir des identifiants sans cliquer sur Enregistrer, sauvegarder d'abord
  const pendingPwd = document.getElementById("set-password").value;
  const pendingKey = document.getElementById("set-gemini-key").value;
  if (pendingPwd || pendingKey) {
    await saveSettings();
  }

  try {
    const res = await fetch("/api/settings/test", { method: "POST" });
    const data = await res.json();
    const folders = data.discovered_folders || {};
    const folderStr = folders.drafts
      ? `\n📂 Dossiers détectés : Brouillons="${folders.drafts}", Spam="${folders.spam}", Corbeille="${folders.trash}"`
      : "";
    const msg =
      `${data.imap_ok ? "✅" : "❌"} IMAP : ${data.imap_message}${folderStr}\n` +
      `${data.ai_ok ? "✅" : "ℹ️"} Moteur IA actif : ${data.ai_label}`;
    if (resultBox) resultBox.textContent = msg;
    showToast(data.imap_ok ? "Test de connexion réussi !" : "Échec de connexion IMAP", data.imap_ok ? "success" : "error");
    await fetchAgentLogs();
  } catch (err) {
    if (resultBox) resultBox.textContent = "❌ Erreur lors du test de connexion.";
  } finally {
    if (btn) btn.disabled = false;
  }
}

async function runAutonomousRoutine() {
  const syncImap = confirm(
    "Lancer la Routine Autonome de l'Agent ?\n\n" +
    "Cliquez sur OK pour analyser vos emails récents ET synchroniser automatiquement tous les brouillons générés dans votre dossier Brouillons Gmail."
  );

  const btn = document.getElementById("btn-agent-routine");
  if (btn) btn.disabled = true;
  showToast("🤖 Routine autonome de l'Agent en cours d'exécution...", "info");

  try {
    const res = await fetch("/api/agent/run-routine", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        limit: currentLimit,
        unread_only: false,
        sync_drafts_to_imap: syncImap,
      }),
    });
    const data = await res.json();
    if (res.ok && data.success) {
      currentFolder = "inbox";
      currentEmails = data.emails || [];
      updateKpis();
      renderEmailsList();
      if (currentEmails.length > 0) selectEmail(currentEmails[0]);
      showToast(data.message || "Routine autonome terminée avec succès !");
    } else {
      showToast(data.error || "Erreur pendant la routine autonome", "error");
    }
  } catch (err) {
    showToast("Erreur réseau pendant la routine autonome", "error");
  } finally {
    if (btn) btn.disabled = false;
  }
}

async function fetchAgentLogs() {
  const box = document.getElementById("agent-logs-box");
  if (!box) return;
  try {
    const res = await fetch("/api/agent/logs");
    if (!res.ok) return;
    const data = await res.json();
    const logs = data.logs || [];
    if (logs.length === 0) {
      box.textContent = "Aucun événement enregistré.";
      return;
    }
    box.textContent = logs.map(l => `[${l.time}] (${l.level.toUpperCase()}) ${l.message}`).join("\n");
  } catch (_) {
    // Ignore
  }
}
