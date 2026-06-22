/**
 * Trợ lý AI CRM — PTT
 */
window.PttCrmAi = (function () {
  "use strict";

  const STORAGE_KEY = "ptt_crm_ai_history";
  let config = null;
  let history = [];
  let sending = false;
  let open = false;
  let caseId = null;
  const els = {};

  function $(id) {
    return document.getElementById(id);
  }

  function escapeHtml(s) {
    return String(s ?? "")
      .replace(/&/g, "&amp;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;")
      .replace(/"/g, "&quot;");
  }

  function canView() {
    if (window.PTT_ADMIN_FULL_ACCESS) return true;
    if (typeof window.PTT_ADMIN_CAN === "function") {
      return window.PTT_ADMIN_CAN("crm_assistant", "view");
    }
    return true;
  }

  function canCreate() {
    if (window.PTT_ADMIN_FULL_ACCESS) return true;
    if (typeof window.PTT_ADMIN_CAN === "function") {
      return window.PTT_ADMIN_CAN("crm_assistant", "create");
    }
    return true;
  }

  function detectCaseId() {
    const m = window.location.pathname.match(/\/crm\/cases\/(\d+)/);
    if (m) return Number(m[1]);
    const card = document.querySelector("[data-case-id].is-selected, .crm-case-detail[data-case-id]");
    if (card) {
      const id = Number(card.getAttribute("data-case-id"));
      if (Number.isFinite(id) && id > 0) return id;
    }
    const params = new URLSearchParams(window.location.search);
    const q = Number(params.get("case_id") || params.get("case"));
    return Number.isFinite(q) && q > 0 ? q : null;
  }

  function loadHistory() {
    try {
      const raw = sessionStorage.getItem(STORAGE_KEY);
      history = Array.isArray(JSON.parse(raw || "[]")) ? JSON.parse(raw || "[]") : [];
    } catch {
      history = [];
    }
  }

  function saveHistory() {
    try {
      sessionStorage.setItem(STORAGE_KEY, JSON.stringify(history.slice(-40)));
    } catch {
      /* ignore */
    }
  }

  function renderMarkdown(text) {
    let s = escapeHtml(text);
    s = s.replace(/\*\*(.+?)\*\*/g, "<strong>$1</strong>");
    s = s.replace(/^### (.+)$/gm, "<h4>$1</h4>");
    s = s.replace(/^## (.+)$/gm, "<h3>$1</h3>");
    s = s.replace(/^\|(.+)\|$/gm, (row) => {
      const cells = row.split("|").filter((c) => c.trim() !== "");
      if (cells.every((c) => /^[\s\-:]+$/.test(c))) return "";
      return `<tr>${cells.map((c) => `<td>${c.trim()}</td>`).join("")}</tr>`;
    });
    s = s.replace(/((?:<tr>[\s\S]*?<\/tr>)+)/g, (m) => `<table>${m}</table>`);
    s = s.replace(/^- (.+)$/gm, "<li>$1</li>");
    s = s.replace(/(<li>[\s\S]*?<\/li>)+/g, (m) => `<ul>${m}</ul>`);
    s = s.replace(/\n/g, "<br>");
    return s;
  }

  function appendMsg(role, text, files) {
    if (!els.msgs) return;
    const wrap = document.createElement("div");
    wrap.className = `ptt-crm-ai-msg ptt-crm-ai-msg--${role === "user" ? "user" : "bot"}`;
    const bubble = document.createElement("div");
    bubble.className = "ptt-crm-ai-msg__bubble";
    bubble.innerHTML = role === "user" ? escapeHtml(text).replace(/\n/g, "<br>") : renderMarkdown(text);
    wrap.appendChild(bubble);
    if (role !== "user" && Array.isArray(files) && files.length) {
      const fileRow = document.createElement("div");
      fileRow.className = "ptt-crm-ai-files";
      const cap = document.createElement("p");
      cap.className = "ptt-crm-ai-files__cap";
      cap.textContent = "File đính kèm";
      fileRow.appendChild(cap);
      files.forEach((file) => {
        const btn = document.createElement("button");
        btn.type = "button";
        btn.className = "ptt-crm-ai-file-btn";
        btn.textContent = file.label || file.filename || "Tải file";
        btn.addEventListener("click", () => downloadAttachment(file, btn));
        fileRow.appendChild(btn);
      });
      wrap.appendChild(fileRow);
    }
    els.msgs.appendChild(wrap);
    els.msgs.scrollTop = els.msgs.scrollHeight;
  }

  async function downloadAttachment(file, btn) {
    if (!file || !file.url) return;
    const prev = btn.textContent;
    btn.disabled = true;
    btn.textContent = "Đang tải…";
    try {
      const res = await fetch(file.url, { credentials: "same-origin" });
      if (!res.ok) {
        const data = await res.json().catch(() => ({}));
        throw new Error(data.error || "Không tải được file.");
      }
      const blob = await res.blob();
      const a = document.createElement("a");
      a.href = URL.createObjectURL(blob);
      a.download = file.filename || "bang-luong.xlsx";
      document.body.appendChild(a);
      a.click();
      a.remove();
      URL.revokeObjectURL(a.href);
      btn.textContent = "Đã tải ✓";
    } catch (err) {
      btn.textContent = prev;
      appendMsg("bot", err.message || "Lỗi tải file.");
    } finally {
      btn.disabled = false;
      window.setTimeout(() => {
        if (btn.textContent === "Đã tải ✓") btn.textContent = prev;
      }, 2500);
    }
  }

  function renderHistory() {
    if (!els.msgs) return;
    els.msgs.innerHTML = "";
    history.forEach((m) =>
      appendMsg(m.role === "user" ? "user" : "bot", m.text, m.files),
    );
  }

  function setOpen(next) {
    open = !!next;
    if (els.panel) {
      els.panel.hidden = false;
      els.panel.classList.toggle("is-open", open);
    }
  }

  async function fetchConfig() {
    const res = await fetch("/api/crm/assistant/config", { credentials: "same-origin" });
    if (!res.ok) throw new Error("config");
    config = await res.json();
    if (!config.enabled) return false;
    if (els.title) els.title.textContent = config.title || "Trợ lý CRM";
    if (els.subtitle) els.subtitle.textContent = config.subtitle || "";
    if (els.note) els.note.textContent = config.ai_note || "";
    if (els.ctx) {
      const line = config.context_summary || "";
      els.ctx.textContent = line;
      els.ctx.hidden = !line;
    }
    if (els.input && config.placeholder) els.input.placeholder = config.placeholder;
    renderChips(els.modules, config.modules || [], "prompt");
    renderChips(els.quick, config.quick_replies || [], "text");
    if (!history.length && config.welcome) {
      history.push({ role: "assistant", text: config.welcome });
      saveHistory();
    }
    renderHistory();
    return true;
  }

  function renderChips(container, items, field) {
    if (!container) return;
    container.innerHTML = "";
    items.forEach((item) => {
      const label = typeof item === "string" ? item : item.label || item.prompt || "";
      const value = typeof item === "string" ? item : item[field] || item.prompt || label;
      if (!label) return;
      const btn = document.createElement("button");
      btn.type = "button";
      btn.className = "ptt-crm-ai-chip";
      btn.textContent = label;
      btn.addEventListener("click", () => sendMessage(value));
      container.appendChild(btn);
    });
  }

  async function sendMessage(text) {
    const msg = String(text || "").trim();
    if (!msg || sending || !canCreate()) return;
    sending = true;
    if (els.send) els.send.disabled = true;
    if (els.typing) els.typing.hidden = false;
    history.push({ role: "user", text: msg });
    appendMsg("user", msg);
    saveHistory();
    if (els.input) els.input.value = "";

    try {
      const payload = {
        text: msg,
        messages: history.slice(-20),
      };
      if (caseId) payload.case_id = caseId;
      const res = await fetch("/api/crm/assistant/send", {
        method: "POST",
        credentials: "same-origin",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload),
      });
      const data = await res.json().catch(() => ({}));
      if (!res.ok) throw new Error(data.error || "Gửi thất bại.");
      const reply = String(data.reply || "").trim() || "Không nhận được phản hồi.";
      const files = Array.isArray(data.files) ? data.files : [];
      history.push({ role: "assistant", text: reply, files: files.length ? files : undefined });
      appendMsg("bot", reply, files);
      saveHistory();
    } catch (err) {
      appendMsg("bot", err.message || "Lỗi kết nối trợ lý CRM.");
    } finally {
      sending = false;
      if (els.send) els.send.disabled = false;
      if (els.typing) els.typing.hidden = true;
    }
  }

  async function exportMd() {
    if (!history.length) return;
    try {
      const res = await fetch("/api/crm/assistant/export", {
        method: "POST",
        credentials: "same-origin",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ format: "md", messages: history }),
      });
      if (!res.ok) return;
      const blob = await res.blob();
      const a = document.createElement("a");
      a.href = URL.createObjectURL(blob);
      a.download = `ptt-crm-assistant-${Date.now()}.md`;
      a.click();
      URL.revokeObjectURL(a.href);
    } catch {
      /* ignore */
    }
  }

  function clearChat() {
    history = [];
    saveHistory();
    if (config && config.welcome) {
      history.push({ role: "assistant", text: config.welcome });
      saveHistory();
    }
    renderHistory();
  }

  function bind() {
    els.launcher = $("pttCrmAiLauncher");
    els.fab = $("pttCrmAiFab");
    els.panel = $("pttCrmAiPanel");
    els.msgs = $("pttCrmAiMsgs");
    els.input = $("pttCrmAiInput");
    els.send = $("pttCrmAiSend");
    els.close = $("pttCrmAiClose");
    els.clear = $("pttCrmAiClear");
    els.exportMd = $("pttCrmAiExportMd");
    els.typing = $("pttCrmAiTyping");
    els.title = $("pttCrmAiTitle");
    els.subtitle = $("pttCrmAiSubtitle");
    els.note = $("pttCrmAiNote");
    els.ctx = $("pttCrmAiCtx");
    els.modules = $("pttCrmAiModules");
    els.quick = $("pttCrmAiQuick");

    if (els.fab) els.fab.addEventListener("click", () => setOpen(!open));
    if (els.close) els.close.addEventListener("click", () => setOpen(false));
    if (els.send) els.send.addEventListener("click", () => sendMessage(els.input && els.input.value));
    if (els.clear) els.clear.addEventListener("click", clearChat);
    if (els.exportMd) els.exportMd.addEventListener("click", exportMd);
    if (els.input) {
      els.input.addEventListener("keydown", (e) => {
        if (e.key === "Enter" && !e.shiftKey) {
          e.preventDefault();
          sendMessage(els.input.value);
        }
      });
    }
  }

  async function init() {
    if (!canView()) return;
    bind();
    caseId = detectCaseId();
    loadHistory();
    try {
      const ok = await fetchConfig();
      if (!ok || !els.launcher) return;
      els.launcher.hidden = false;
    } catch {
      /* assistant unavailable */
    }
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", init);
  } else {
    init();
  }

  return { open: () => setOpen(true), send: sendMessage };
})();
