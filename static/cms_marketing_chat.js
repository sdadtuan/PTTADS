/**
 * Chatbox chiến lược marketing chuyên sâu — CMS PTT
 * Hỗ trợ Markdown, Mermaid, Chart.js, xuất MD/HTML/JSON
 */
window.PttMkChat = (function () {
  "use strict";

  const STORAGE_KEY = "ptt_cms_mk_chat_history";
  const TEASER_KEY = "ptt_cms_mk_chat_teaser_closed";

  let config = null;
  let history = [];
  let teaserTimer = null;
  let sending = false;
  let kpiFlow = null; // null | "awaiting_brief" | "awaiting_clarification"
  let kpiBriefParts = [];
  let mermaidReady = false;
  let stickToBottom = true;
  let scrollRaf = 0;
  let scrollLockUntil = 0;
  let chartScrollRaf = 0;
  const chartInstances = [];
  const els = {};

  const KPI_BRIEF_FALLBACK =
    "📋 **Tạo bộ KPI & KHMKT theo chiến dịch**\n\n" +
    "Vui lòng mô tả **dự án / chiến dịch marketing** (tên, mục tiêu, ICP, thời gian, ngân sách, kênh ưu tiên) " +
    "để trợ lý phân tích và tạo file **KHMKT.xlsx** + **KPI.xlsx** tương ứng.";

  const CHART_SCROLL_PLUGIN = {
    id: "pttMkChartScroll",
    afterDraw() {
      if (chartScrollRaf) return;
      chartScrollRaf = requestAnimationFrame(() => {
        chartScrollRaf = 0;
        scheduleScrollToBottom(true);
      });
    },
  };

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

  function isNearBottom(threshold = 64) {
    if (!els.msgs) return true;
    const gap = els.msgs.scrollHeight - els.msgs.scrollTop - els.msgs.clientHeight;
    return gap <= threshold;
  }

  function ensureScrollAnchor() {
    if (!els.msgs) return null;
    let anchor = els.scrollAnchor;
    if (!anchor || !els.msgs.contains(anchor)) {
      anchor = document.createElement("div");
      anchor.className = "ptt-mk-chat-scroll-anchor";
      anchor.setAttribute("aria-hidden", "true");
      els.scrollAnchor = anchor;
    }
    if (anchor.parentNode !== els.msgs || anchor !== els.msgs.lastElementChild) {
      els.msgs.appendChild(anchor);
    }
    return anchor;
  }

  /** Chỉ cuộn container tin nhắn — không dùng scrollIntoView (tránh cuộn cả trang CMS). */
  function scrollToBottom({ force = false } = {}) {
    if (!els.msgs) return;
    if (!force && !stickToBottom && !isNearBottom()) return;
    ensureScrollAnchor();
    if (scrollRaf) cancelAnimationFrame(scrollRaf);
    scrollRaf = requestAnimationFrame(() => {
      scrollRaf = 0;
      const el = els.msgs;
      el.scrollTop = el.scrollHeight;
    });
  }

  function scheduleScrollToBottom(force = false) {
    if (!force && !stickToBottom && !isNearBottom()) return;
    if (force) {
      stickToBottom = true;
      scrollLockUntil = Date.now() + 1200;
    }
    scrollToBottom({ force: true });
    window.setTimeout(() => scrollToBottom({ force: Date.now() < scrollLockUntil }), 16);
    window.setTimeout(() => scrollToBottom({ force: Date.now() < scrollLockUntil }), 120);
  }

  function bindScrollGuard() {
    if (!els.msgs || els.msgs.dataset.scrollGuard) return;
    els.msgs.dataset.scrollGuard = "1";
    els.msgs.addEventListener(
      "scroll",
      () => {
        if (Date.now() < scrollLockUntil) return;
        stickToBottom = isNearBottom();
      },
      { passive: true }
    );
  }

  function loadHistory() {
    try {
      const raw = sessionStorage.getItem(STORAGE_KEY);
      const parsed = raw ? JSON.parse(raw) : [];
      history = Array.isArray(parsed) ? parsed : [];
    } catch {
      history = [];
    }
  }

  function saveHistory() {
    try {
      sessionStorage.setItem(STORAGE_KEY, JSON.stringify(history.slice(-60)));
    } catch {
      /* ignore */
    }
  }

  function inlineMarkdown(text) {
    let s = escapeHtml(text);
    s = s.replace(/\*\*(.+?)\*\*/g, "<strong>$1</strong>");
    s = s.replace(/^### (.+)$/gm, "<h4 class='ptt-mk-md-h4'>$1</h4>");
    s = s.replace(/^## (.+)$/gm, "<h3 class='ptt-mk-md-h3'>$1</h3>");
    s = s.replace(/^\|(.+)\|$/gm, (row) => {
      const cells = row.split("|").filter((c) => c.trim() !== "");
      if (cells.every((c) => /^[\s\-:]+$/.test(c))) return "";
      const tag = cells.some((c) => c.includes("---")) ? "" : "td";
      if (!tag) return "";
      return `<tr>${cells.map((c) => `<td>${c.trim()}</td>`).join("")}</tr>`;
    });
    s = s.replace(/((?:<tr>[\s\S]*?<\/tr>)+)/g, (m) => `<table class="ptt-mk-md-table">${m}</table>`);
    s = s.replace(/^- (.+)$/gm, "<li>$1</li>");
    s = s.replace(/(<li>[\s\S]*?<\/li>)+/g, (m) => `<ul class='ptt-mk-md-ul'>${m}</ul>`);
    s = s.replace(/\n/g, "<br>");
    return s;
  }

  function renderChartBlock(spec, container) {
    if (!window.Chart || !spec || !Array.isArray(spec.labels) || !Array.isArray(spec.values)) return null;
    const canvas = document.createElement("canvas");
    container.appendChild(canvas);
    const type = ["bar", "pie", "line", "doughnut"].includes(spec.type) ? spec.type : "bar";
    const colors = ["#398b43", "#8cc63f", "#4a9d52", "#2f7238", "#66758f", "#13233f"];
    const inst = new window.Chart(canvas, {
      type,
      plugins: [CHART_SCROLL_PLUGIN],
      data: {
        labels: spec.labels,
        datasets: [
          {
            label: spec.title || "Giá trị",
            data: spec.values,
            backgroundColor: type === "line" ? "rgba(57,139,67,0.2)" : colors.slice(0, spec.labels.length),
            borderColor: "#398b43",
            borderWidth: type === "line" ? 2 : 1,
            tension: 0.3,
            fill: type === "line",
          },
        ],
      },
      options: {
        responsive: true,
        maintainAspectRatio: false,
        animation: false,
        layout: { padding: 0 },
        plugins: { legend: { display: type === "pie" || type === "doughnut" } },
      },
    });
    chartInstances.push(inst);
    scheduleScrollToBottom(true);
    return inst;
  }

  function renderRichContent(text, target) {
    target.innerHTML = "";
    const parts = String(text || "").split(/(```[\s\S]*?```)/g);
    parts.forEach((part) => {
      if (!part.trim()) return;
      const mermaidMatch = part.match(/^```mermaid\s*([\s\S]*?)```$/i);
      const chartMatch = part.match(/^```chart-json\s*([\s\S]*?)```$/i);
      const codeMatch = part.match(/^```(\w*)\s*([\s\S]*?)```$/);

      if (mermaidMatch) {
        const wrap = document.createElement("div");
        wrap.className = "ptt-mk-mermaid-wrap";
        const pre = document.createElement("pre");
        pre.className = "mermaid";
        pre.textContent = mermaidMatch[1].trim();
        wrap.appendChild(pre);
        target.appendChild(wrap);
        return;
      }
      if (chartMatch) {
        try {
          const spec = JSON.parse(chartMatch[1].trim());
          const wrap = document.createElement("div");
          wrap.className = "ptt-mk-chart-wrap";
          if (spec.title) {
            const t = document.createElement("p");
            t.className = "ptt-mk-chart-title";
            t.textContent = spec.title;
            wrap.appendChild(t);
          }
          renderChartBlock(spec, wrap);
          target.appendChild(wrap);
        } catch {
          const err = document.createElement("p");
          err.className = "ptt-mk-chart-err";
          err.textContent = "Không đọc được dữ liệu biểu đồ (chart-json).";
          target.appendChild(err);
        }
        return;
      }
      if (codeMatch && !mermaidMatch && !chartMatch) {
        const pre = document.createElement("pre");
        pre.className = "ptt-mk-code";
        pre.textContent = codeMatch[2].trim();
        target.appendChild(pre);
        return;
      }
      const div = document.createElement("div");
      div.className = "ptt-mk-md";
      div.innerHTML = inlineMarkdown(part);
      target.appendChild(div);
    });
  }

  async function renderMermaidIn(root) {
    if (!window.mermaid || !root) return;
    const nodes = root.querySelectorAll("pre.mermaid:not([data-processed])");
    if (!nodes.length) return;
    try {
      if (!mermaidReady) {
        window.mermaid.initialize({ startOnLoad: false, theme: "neutral", securityLevel: "loose" });
        mermaidReady = true;
      }
      await window.mermaid.run({ nodes: [...nodes] });
      nodes.forEach((n) => n.setAttribute("data-processed", "1"));
    } catch {
      /* ignore render errors */
    }
  }

  function appendMessage(role, text, { skipScroll = false } = {}) {
    if (!els.msgs || !text) return null;
    const div = document.createElement("div");
    div.className = "ptt-mk-chat-msg " + (role === "user" ? "ptt-mk-chat-msg--user" : "ptt-mk-chat-msg--bot");
    const label = role === "user" ? "Bạn" : "Trợ lý MK";
    const head = document.createElement("div");
    head.className = "ptt-mk-chat-msg__head";
    head.innerHTML = `<span class="ptt-mk-chat-msg__meta">${label}</span>`;
    if (role !== "user") {
      const actions = document.createElement("div");
      actions.className = "ptt-mk-chat-msg__actions";
      const copyBtn = document.createElement("button");
      copyBtn.type = "button";
      copyBtn.className = "ptt-mk-msg-btn";
      copyBtn.textContent = "Copy";
      copyBtn.title = "Sao chép tin nhắn";
      copyBtn.addEventListener("click", () => {
        navigator.clipboard?.writeText(text).catch(() => {});
      });
      const mdBtn = document.createElement("button");
      mdBtn.type = "button";
      mdBtn.className = "ptt-mk-msg-btn";
      mdBtn.textContent = "MD";
      mdBtn.title = "Xuất tin nhắn này (.md)";
      mdBtn.addEventListener("click", () => exportMessages([{ role, text }], "md"));
      actions.appendChild(copyBtn);
      actions.appendChild(mdBtn);
      head.appendChild(actions);
    }
    div.appendChild(head);
    const body = document.createElement("div");
    body.className = "ptt-mk-chat-msg__body";
    if (role === "user") {
      body.textContent = text;
    } else {
      renderRichContent(text, body);
    }
    div.appendChild(body);
    if (els.scrollAnchor && els.scrollAnchor.parentNode === els.msgs) {
      els.msgs.insertBefore(div, els.scrollAnchor);
    } else {
      els.msgs.appendChild(div);
    }
    ensureScrollAnchor();
    if (!skipScroll) {
      if (role === "user") {
        stickToBottom = true;
        scrollToBottom({ force: true });
      } else {
        finalizeBotMessage(body);
      }
    }
    return div;
  }

  async function finalizeBotMessage(body) {
    scheduleScrollToBottom(true);
    await renderMermaidIn(body);
    scheduleScrollToBottom(true);
  }

  async function renderHistory() {
    if (!els.msgs) return;
    chartInstances.forEach((c) => c.destroy());
    chartInstances.length = 0;
    els.msgs.innerHTML = "";
    els.scrollAnchor = null;
    const botBodies = [];
    history.forEach((m) => {
      const node = appendMessage(m.role, m.text, { skipScroll: true });
      if (node && m.role !== "user") {
        const body = node.querySelector(".ptt-mk-chat-msg__body");
        if (body) botBodies.push(body);
      }
    });
    await Promise.all(botBodies.map((body) => renderMermaidIn(body)));
    ensureScrollAnchor();
    scheduleScrollToBottom(true);
  }

  function startKpiCampaignFlow() {
    openPanel();
    kpiFlow = "awaiting_brief";
    kpiBriefParts = [];
    const prompt = config?.kpi_brief_prompt || KPI_BRIEF_FALLBACK;
    history.push({ role: "assistant", text: prompt });
    appendMessage("assistant", prompt);
    saveHistory();
    scheduleScrollToBottom(true);
    els.input?.focus();
  }

  function wantsForceGenerate(text) {
    const t = (text || "").toLowerCase();
    return /tao file|tạo file|đủ rồi|du roi|ok tạo|ok tao|tạo ngay|tao ngay|generate|bỏ qua|bo qua/.test(t);
  }

  async function downloadBlobUrl(url, fallbackName) {
    const res = await fetch(url, { credentials: "same-origin" });
    if (res.status === 401) {
      window.location.href = "/admin/login?next=/cms";
      return;
    }
    if (!res.ok) throw new Error("Không tải được file.");
    const blob = await res.blob();
    const disp = res.headers.get("Content-Disposition") || "";
    const m = disp.match(/filename=\"?([^\";]+)/);
    const name = m ? m[1] : fallbackName;
    const a = document.createElement("a");
    a.href = URL.createObjectURL(blob);
    a.download = name;
    a.click();
    URL.revokeObjectURL(a.href);
  }

  function appendDownloadBar(body, kit) {
    const bar = document.createElement("div");
    bar.className = "ptt-mk-campaign-downloads";
    const btnKhmkt = document.createElement("button");
    btnKhmkt.type = "button";
    btnKhmkt.className = "ptt-mk-campaign-dl-btn";
    btnKhmkt.textContent = "KHMKT.xlsx";
    btnKhmkt.title = "Tải kế hoạch marketing 7 bước";
    btnKhmkt.addEventListener("click", () => downloadBlobUrl(kit.khmkt_url, "KHMKT.xlsx"));
    const btnKpi = document.createElement("button");
    btnKpi.type = "button";
    btnKpi.className = "ptt-mk-campaign-dl-btn";
    btnKpi.textContent = "KPI.xlsx";
    btnKpi.title = "Tải dashboard KPI chiến dịch";
    btnKpi.addEventListener("click", () => downloadBlobUrl(kit.kpi_url, "KPI.xlsx"));
    bar.appendChild(btnKhmkt);
    bar.appendChild(btnKpi);
    body.appendChild(bar);
  }

  async function generateCampaignKit(brief, opts = {}) {
    const displayBrief = String(brief || "").trim();
    if (!displayBrief) return;

    sending = true;
    stickToBottom = true;
    history.push({ role: "user", text: displayBrief });
    appendMessage("user", displayBrief);
    saveHistory();

    if (kpiFlow === "awaiting_brief" || !kpiBriefParts.length) {
      kpiBriefParts = [displayBrief];
    } else if (kpiBriefParts[kpiBriefParts.length - 1] !== displayBrief) {
      kpiBriefParts.push(displayBrief);
    }

    const payloadBrief = kpiBriefParts.join("\n\n");
    const force = opts.force || wantsForceGenerate(displayBrief);

    if (els.typing) els.typing.hidden = false;
    scrollToBottom({ force: true });
    if (els.send) els.send.disabled = true;

    try {
      const data = await requestJson(config?.campaign_kit_url || "/api/cms/marketing-chat/campaign-kit", {
        method: "POST",
        body: JSON.stringify({ brief: payloadBrief, force }),
      });
      const reply = String(data.reply || "").trim();
      if (data.status === "needs_info") {
        kpiFlow = "awaiting_clarification";
        if (reply) {
          history.push({ role: "assistant", text: reply });
          appendMessage("assistant", reply);
          saveHistory();
        }
        return;
      }

      kpiFlow = null;
      kpiBriefParts = [];
      if (reply) {
        history.push({
          role: "assistant",
          text: reply,
          kit: { khmkt_url: data.khmkt_url, kpi_url: data.kpi_url },
        });
        const node = appendMessage("assistant", reply);
        const body = node?.querySelector(".ptt-mk-chat-msg__body");
        if (body && data.khmkt_url && data.kpi_url) {
          appendDownloadBar(body, data);
        }
        saveHistory();
        if (data.khmkt_url) {
          await downloadBlobUrl(data.khmkt_url, `KHMKT-${data.slug || "du-an"}.xlsx`);
        }
        if (data.kpi_url) {
          await downloadBlobUrl(data.kpi_url, `KPI-${data.slug || "du-an"}.xlsx`);
        }
      }
    } catch (err) {
      appendMessage("assistant", `Lỗi tạo bộ tài liệu: ${err.message || "Thử lại sau."}`);
    } finally {
      sending = false;
      if (els.typing) els.typing.hidden = true;
      if (els.send) els.send.disabled = false;
      scheduleScrollToBottom(true);
      els.input?.focus();
    }
  }

  function handleQuickReply(text) {
    const t = (text || "").toLowerCase();
    if (t.includes("kpi") && t.includes("excel")) {
      startKpiCampaignFlow();
      return;
    }
    if (t.includes("excel") && (t.includes("12 tuần") || t.includes("12 tuan") || t.includes("xls"))) {
      downloadWeeklyPlan();
      send(text);
      return;
    }
    send(text);
  }

  function renderQuickReplies() {
    if (!els.quick || !config) return;
    els.quick.innerHTML = "";
    (config.quick_replies || []).forEach((text) => {
      const btn = document.createElement("button");
      btn.type = "button";
      btn.textContent = text;
      btn.addEventListener("click", () => handleQuickReply(text));
      els.quick.appendChild(btn);
    });
  }

  function renderModules() {
    const box = $("pttMkChatModules");
    if (!box || !config?.modules?.length) return;
    box.innerHTML = "";
    config.modules.forEach((mod) => {
      const btn = document.createElement("button");
      btn.type = "button";
      btn.className = "ptt-mk-module-btn" + (mod.action === "download_xlsx" || mod.action === "download_mc_xlsx" || mod.action === "prompt_kpi_campaign" ? " ptt-mk-module-btn--xls" : "");
      btn.textContent = mod.label || mod.id;
      btn.title = mod.prompt || "";
      btn.addEventListener("click", () => {
        const payload = `[BUOC:${mod.id}] ${mod.prompt || mod.label}`;
        if (mod.action === "download_xlsx") {
          downloadWeeklyPlan();
          send(payload);
          return;
        }
        if (mod.action === "download_mc_xlsx") {
          downloadMultichannelPlan();
          send(payload);
          return;
        }
        if (mod.action === "prompt_kpi_campaign") {
          startKpiCampaignFlow();
          return;
        }
        send(mod.prompt || mod.label);
      });
      box.appendChild(btn);
    });
  }

  async function requestJson(url, options) {
    const controller = new AbortController();
    const timer = window.setTimeout(() => controller.abort(), 35000);
    try {
      const res = await fetch(url, {
        credentials: "same-origin",
        headers: { "Content-Type": "application/json" },
        signal: controller.signal,
        ...options,
      });
      if (res.status === 401) {
        const body = await res.json().catch(() => ({}));
        if (typeof body.login === "string") window.location.href = body.login;
        throw new Error(body.error || "Unauthorized");
      }
      if (!res.ok) {
        const body = await res.json().catch(() => ({}));
        throw new Error(body.error || "Request failed");
      }
      return res.json();
    } catch (err) {
      if (err.name === "AbortError") {
        throw new Error("Yêu cầu quá thời gian chờ. Thử lại hoặc dùng nút module nhanh.");
      }
      throw err;
    } finally {
      window.clearTimeout(timer);
    }
  }

  async function downloadWeeklyPlan() {
    const url = config?.weekly_plan_xlsx_url || "/api/cms/marketing-chat/weekly-plan.xlsx";
    try {
      const res = await fetch(url, { credentials: "same-origin" });
      if (res.status === 401) {
        window.location.href = "/admin/login?next=/cms";
        return;
      }
      if (!res.ok) throw new Error("Không tải được file Excel.");
      const blob = await res.blob();
      const disp = res.headers.get("Content-Disposition") || "";
      const m = disp.match(/filename=\"?([^\";]+)/);
      const name = m ? m[1] : "ptt-ke-hoach-marketing-tuan.xlsx";
      const a = document.createElement("a");
      a.href = URL.createObjectURL(blob);
      a.download = name;
      a.click();
      URL.revokeObjectURL(a.href);
    } catch (err) {
      alert(err.message || "Không tải được Excel.");
    }
  }

  async function downloadMultichannelPlan() {
    const url = config?.multichannel_plan_xlsx_url || "/api/cms/marketing-chat/multichannel-plan.xlsx";
    try {
      const res = await fetch(url, { credentials: "same-origin" });
      if (res.status === 401) {
        window.location.href = "/admin/login?next=/cms";
        return;
      }
      if (!res.ok) throw new Error("Không tải được file Excel đa kênh.");
      const blob = await res.blob();
      const disp = res.headers.get("Content-Disposition") || "";
      const m = disp.match(/filename=\"?([^\";]+)/);
      const name = m ? m[1] : "ptt-ke-hoach-truyen-thong-da-kenh.xlsx";
      const a = document.createElement("a");
      a.href = URL.createObjectURL(blob);
      a.download = name;
      a.click();
      URL.revokeObjectURL(a.href);
    } catch (err) {
      alert(err.message || "Không tải được Excel đa kênh.");
    }
  }

  async function downloadKpiStrategy() {
    const url = config?.kpi_strategy_xlsx_url || "/api/cms/marketing-chat/kpi-strategy.xlsx";
    try {
      const res = await fetch(url, { credentials: "same-origin" });
      if (res.status === 401) {
        window.location.href = "/admin/login?next=/cms";
        return;
      }
      if (!res.ok) throw new Error("Không tải được file Excel KPI.");
      const blob = await res.blob();
      const disp = res.headers.get("Content-Disposition") || "";
      const m = disp.match(/filename=\"?([^\";]+)/);
      const name = m ? m[1] : "ptt-kpi-chien-luoc-marketing.xlsx";
      const a = document.createElement("a");
      a.href = URL.createObjectURL(blob);
      a.download = name;
      a.click();
      URL.revokeObjectURL(a.href);
    } catch (err) {
      alert(err.message || "Không tải được Excel KPI.");
    }
  }

  async function exportMessages(msgs, format) {
    const messages = msgs || history;
    if (!messages.length) return;
    try {
      const res = await fetch("/api/cms/marketing-chat/export", {
        method: "POST",
        credentials: "same-origin",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ format, messages }),
      });
      if (!res.ok) {
        const err = await res.json().catch(() => ({}));
        throw new Error(err.error || "Export failed");
      }
      const blob = await res.blob();
      const disp = res.headers.get("Content-Disposition") || "";
      const m = disp.match(/filename=\"?([^\";]+)/);
      const name = m ? m[1] : `ptt-marketing-chat.${format === "html" ? "html" : format === "json" ? "json" : "md"}`;
      const a = document.createElement("a");
      a.href = URL.createObjectURL(blob);
      a.download = name;
      a.click();
      URL.revokeObjectURL(a.href);
    } catch (err) {
      alert(err.message || "Không xuất được file.");
    }
  }

  async function send(text) {
    const msg = String(text || els.input?.value || "").trim();
    if (!msg || sending) return;
    if (els.input) els.input.value = "";

    if (kpiFlow === "awaiting_brief" || kpiFlow === "awaiting_clarification") {
      await generateCampaignKit(msg);
      return;
    }

    sending = true;
    stickToBottom = true;
    history.push({ role: "user", text: msg });
    appendMessage("user", msg);
    saveHistory();

    if (els.typing) els.typing.hidden = false;
    scrollToBottom({ force: true });
    if (els.send) els.send.disabled = true;

    try {
      const data = await requestJson("/api/cms/marketing-chat/send", {
        method: "POST",
        body: JSON.stringify({
          text: msg,
          messages: history.slice(0, -1),
        }),
      });
      const reply = String(data.reply || "").trim();
      if (reply) {
        history.push({ role: "assistant", text: reply });
        appendMessage("assistant", reply);
        saveHistory();
      }
    } catch (err) {
      appendMessage("assistant", `Lỗi: ${err.message || "Không gửi được tin nhắn."}`);
    } finally {
      sending = false;
      if (els.typing) els.typing.hidden = true;
      if (els.send) els.send.disabled = false;
      scheduleScrollToBottom(true);
      els.input?.focus();
    }
  }

  function hideTeaser(persist) {
    if (teaserTimer) {
      clearTimeout(teaserTimer);
      teaserTimer = null;
    }
    els.teaser?.classList.remove("is-visible");
    window.setTimeout(() => els.teaser?.setAttribute("hidden", "true"), 280);
    if (persist) {
      try {
        sessionStorage.setItem(TEASER_KEY, "1");
      } catch {
        /* ignore */
      }
    }
  }

  function showTeaser() {
    if (!els.teaser || !els.teaserText || !config?.welcome) return;
    try {
      if (sessionStorage.getItem(TEASER_KEY)) return;
    } catch {
      /* ignore */
    }
    els.teaserText.innerHTML = escapeHtml(config.welcome).replace(/\n/g, "<br>");
    els.teaser.removeAttribute("hidden");
    requestAnimationFrame(() => {
      requestAnimationFrame(() => els.teaser?.classList.add("is-visible"));
    });
  }

  function openPanel() {
    hideTeaser(true);
    els.launcher?.setAttribute("hidden", "true");
    els.panel?.classList.add("is-open");
    els.panel?.removeAttribute("hidden");
    scrollToBottom({ force: true });
    els.input?.focus();
  }

  function closePanel() {
    els.panel?.classList.remove("is-open");
    window.setTimeout(() => els.panel?.setAttribute("hidden", "true"), 260);
    els.launcher?.removeAttribute("hidden");
  }

  function toggleExpand() {
    els.panel?.classList.toggle("is-expanded");
    scrollToBottom({ force: true });
  }

  function ensureWelcome() {
    if (history.length) return;
    const welcome = config?.welcome;
    if (!welcome) return;
    history.push({ role: "assistant", text: welcome });
    saveHistory();
    appendMessage("assistant", welcome);
  }

  async function boot() {
    els.launcher = $("pttMkChatLauncher");
    els.teaser = $("pttMkChatTeaser");
    els.teaserText = $("pttMkChatTeaserText");
    els.fab = $("pttMkChatFab");
    els.panel = $("pttMkChatPanel");
    els.msgs = $("pttMkChatMsgs");
    els.input = $("pttMkChatInput");
    els.quick = $("pttMkChatQuick");
    els.typing = $("pttMkChatTyping");
    els.send = $("pttMkChatSend");

    if (!els.fab || !els.panel) return;

    bindScrollGuard();
    ensureScrollAnchor();
    els.scrollAnchor = els.msgs?.querySelector(".ptt-mk-chat-scroll-anchor") || null;

    try {
      config = await requestJson("/api/cms/marketing-chat/config");
    } catch (err) {
      const note = $("pttMkChatNote");
      if (note) note.textContent = err.message || "Không tải được cấu hình chatbox.";
      return;
    }

    if (!config.enabled) {
      els.launcher.hidden = true;
      return;
    }

    const titleEl = $("pttMkChatTitle");
    if (titleEl) titleEl.textContent = config.title || "Quản trị Marketing";
    const sub = $("pttMkChatSubtitle");
    if (sub) sub.textContent = config.subtitle || "KPI · Rủi ro · Ngân sách · Lợi nhuận";
    const note = $("pttMkChatNote");
    if (note && config.ai_note) note.textContent = config.ai_note + " · Xuất MD/HTML/JSON";
    if (els.input) els.input.placeholder = config.placeholder || "Mô tả bài toán marketing, yêu cầu biểu đồ…";

    loadHistory();
    renderModules();
    renderQuickReplies();
    renderHistory().then(() => {
      if (!history.length) {
        teaserTimer = window.setTimeout(showTeaser, 1500);
      }
    });
    $("pttMkChatTeaserClose")?.addEventListener("click", (e) => {
      e.stopPropagation();
      hideTeaser(true);
    });
    $("pttMkChatClear")?.addEventListener("click", async () => {
      history = [];
      saveHistory();
      await renderHistory();
      ensureWelcome();
    });
    $("pttMkChatExpand")?.addEventListener("click", toggleExpand);
    $("pttMkChatExportMd")?.addEventListener("click", () => exportMessages(null, "md"));
    $("pttMkChatExportHtml")?.addEventListener("click", () => exportMessages(null, "html"));
    $("pttMkChatExportJson")?.addEventListener("click", () => exportMessages(null, "json"));
    $("pttMkChatWeeklyXlsx")?.addEventListener("click", () => downloadWeeklyPlan());
    $("pttMkChatMultichannelXlsx")?.addEventListener("click", () => downloadMultichannelPlan());
    $("pttMkChatKpiXlsx")?.addEventListener("click", () => startKpiCampaignFlow());

    els.teaser?.addEventListener("click", () => {
      openPanel();
      ensureWelcome();
    });
    els.fab.addEventListener("click", () => {
      openPanel();
      ensureWelcome();
    });
    els.send?.addEventListener("click", () => send());
    els.input?.addEventListener("keydown", (e) => {
      if (e.key === "Enter" && !e.shiftKey) {
        e.preventDefault();
        send();
      }
    });

    $("pttMkChatClose")?.addEventListener("click", closePanel);
  }

  document.addEventListener("DOMContentLoaded", boot);
  return { open: openPanel, close: closePanel, send, exportMessages, downloadWeeklyPlan, downloadMultichannelPlan, downloadKpiStrategy, startKpiCampaignFlow, reload: boot };
})();
