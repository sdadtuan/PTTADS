(function () {
  "use strict";

  var metaEl = document.getElementById("intake-page-meta");
  if (!metaEl) return;

  var meta = {};
  try {
    meta = JSON.parse(metaEl.textContent || "{}");
  } catch (e) {
    console.error("intake meta parse", e);
    return;
  }

  var state = {
    session: meta.active_session || null,
    definition: meta.definition || {},
    formFields: meta.form_fields || [],
    lifecycleId: meta.lifecycle_id || null,
    leadId: meta.lead_id || null,
    isCommonForm: !!meta.is_common_form,
    saving: false,
    dirty: false,
    saveTimer: null,
  };

  var quillRegistry = new Map();
  var QUILL_TOOLBAR = [
    ["bold", "italic", "underline"],
    [{ list: "ordered" }, { list: "bullet" }],
    ["link"],
    ["clean"],
  ];
  var QUILL_TOOLBAR_COMPACT = [
    ["bold", "italic"],
    [{ list: "bullet" }],
    ["clean"],
  ];

  var listView = document.getElementById("intake-list-view");
  var formView = document.getElementById("intake-form-view");
  var sessionsList = document.getElementById("intake-sessions-list");
  var saveStatus = document.getElementById("intake-save-status");
  var activeTab = "overview";
  var TAB_IDS = ["overview", "phone", "meet", "qualify", "close"];
  var TAB_LABELS = {
    overview: "Tổng quan",
    phone: "Gọi điện",
    meet: "Gặp KH",
    qualify: "Đánh giá",
    close: "Chốt deal",
  };

  function qs(sel, root) {
    return (root || document).querySelector(sel);
  }
  function qsa(sel, root) {
    return Array.prototype.slice.call((root || document).querySelectorAll(sel));
  }

  function visibleTabs(mode) {
    if (mode === "in_person") return TAB_IDS.slice();
    return TAB_IDS.filter(function (id) {
      return id !== "meet";
    });
  }

  function switchTab(tabId) {
    var mode = (state.session && state.session.mode) || "phone";
    var tabs = visibleTabs(mode);
    if (tabs.indexOf(tabId) < 0) tabId = tabs[0];
    activeTab = tabId;
    qsa(".intake-tab-btn").forEach(function (btn) {
      var id = btn.getAttribute("data-intake-tab");
      var on = id === tabId;
      btn.classList.toggle("is-active", on);
      btn.setAttribute("aria-selected", on ? "true" : "false");
    });
    qsa(".intake-tab-panel").forEach(function (panel) {
      var id = panel.getAttribute("data-intake-panel");
      var show = id === tabId;
      panel.classList.toggle("is-active", show);
      panel.hidden = !show;
    });
    var activeBtn = qs("#intake-tab-btn-" + tabId);
    if (activeBtn && activeBtn.scrollIntoView) {
      activeBtn.scrollIntoView({ behavior: "smooth", block: "nearest", inline: "center" });
    }
    updateTabNav();
  }

  function updateTabsForMode(mode) {
    var meetBtn = qs("#intake-tab-btn-meet");
    if (meetBtn) meetBtn.hidden = mode !== "in_person";
    var tabs = visibleTabs(mode);
    tabs.forEach(function (id, idx) {
      var btn = qs("#intake-tab-btn-" + id);
      if (btn) btn.textContent = idx + 1 + ". " + TAB_LABELS[id];
    });
    if (tabs.indexOf(activeTab) < 0) activeTab = tabs[0];
    switchTab(activeTab);
  }

  function updateTabNav() {
    var mode = (state.session && state.session.mode) || "phone";
    var tabs = visibleTabs(mode);
    var idx = tabs.indexOf(activeTab);
    var hint = qs("#intake-tab-nav-hint");
    var prev = qs("#intake-tab-prev");
    var next = qs("#intake-tab-next");
    if (hint) hint.textContent = "Bước " + (idx + 1) + " / " + tabs.length;
    if (prev) prev.disabled = idx <= 0;
    if (next) {
      next.disabled = idx >= tabs.length - 1;
      next.textContent = idx >= tabs.length - 1 ? "Tab cuối" : "Tab sau →";
    }
  }

  function bindTabControls() {
    qsa(".intake-tab-btn").forEach(function (btn) {
      btn.addEventListener("click", function () {
        switchTab(btn.getAttribute("data-intake-tab"));
      });
    });
    var prev = qs("#intake-tab-prev");
    var next = qs("#intake-tab-next");
    if (prev) {
      prev.addEventListener("click", function () {
        var tabs = visibleTabs(state.session.mode || "phone");
        var idx = tabs.indexOf(activeTab);
        if (idx > 0) switchTab(tabs[idx - 1]);
      });
    }
    if (next) {
      next.addEventListener("click", function () {
        var tabs = visibleTabs(state.session.mode || "phone");
        var idx = tabs.indexOf(activeTab);
        if (idx < tabs.length - 1) switchTab(tabs[idx + 1]);
      });
    }
  }

  function api(path, opts) {
    opts = opts || {};
    return fetch(path, {
      method: opts.method || "GET",
      headers: Object.assign(
        { "Content-Type": "application/json" },
        opts.headers || {}
      ),
      body: opts.body ? JSON.stringify(opts.body) : undefined,
      credentials: "same-origin",
    }).then(function (res) {
      return res.json().then(function (data) {
        if (!res.ok) throw new Error((data && data.error) || "Lỗi API");
        return data;
      });
    });
  }

  function escapeHtml(str) {
    return String(str || "")
      .replace(/&/g, "&amp;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;")
      .replace(/"/g, "&quot;");
  }

  function htmlToPlain(html) {
    var div = document.createElement("div");
    div.innerHTML = html || "";
    return (div.textContent || div.innerText || "").trim();
  }

  function destroyQuills() {
    quillRegistry.clear();
  }

  function mountQuill(wrapEl, html, readonly, compact) {
    if (!wrapEl) return null;
    var editorEl = wrapEl.querySelector(".intake-quill-editor");
    if (!editorEl) return null;

    if (typeof Quill === "undefined") {
      editorEl.innerHTML =
        '<textarea class="intake-fallback-textarea" rows="3" style="width:100%;border:0;padding:.5rem;font:inherit;">' +
        escapeHtml(htmlToPlain(html)) +
        "</textarea>";
      var ta = editorEl.querySelector("textarea");
      if (ta) {
        ta.disabled = !!readonly;
        ta.addEventListener("input", onFieldChange);
        wrapEl.__fallback = ta;
      }
      return null;
    }

    wrapEl.classList.toggle("is-readonly", !!readonly);
    var quill = new Quill(editorEl, {
      theme: "snow",
      modules: { toolbar: compact ? QUILL_TOOLBAR_COMPACT : QUILL_TOOLBAR },
      placeholder: "Nhập ghi chú…",
    });
    if (html) {
      if (html.indexOf("<") >= 0) quill.root.innerHTML = html;
      else quill.setText(html);
    }
    if (readonly) quill.enable(false);
    quill.on("text-change", onFieldChange);
    wrapEl.__quill = quill;
    return quill;
  }

  function readQuillValue(wrapEl) {
    if (!wrapEl) return "";
    if (wrapEl.__quill) {
      var html = wrapEl.__quill.root.innerHTML.trim();
      return html === "<p><br></p>" ? "" : html;
    }
    if (wrapEl.__fallback) return wrapEl.__fallback.value;
    return "";
  }

  function registerQuill(key, wrapEl) {
    if (wrapEl) quillRegistry.set(key, wrapEl);
  }

  function intakeListUrl() {
    if (meta.lifecycle_id) {
      return "/crm/intake?lifecycle_id=" + meta.lifecycle_id;
    }
    if (meta.lead_id) {
      return (
        "/crm/intake?lead_id=" +
        meta.lead_id +
        "&service_slug=" +
        encodeURIComponent(meta.service_slug || "_common")
      );
    }
    return "/crm/intake";
  }

  function showList() {
    stopAiSummaryPoll();
    destroyQuills();
    listView.hidden = false;
    formView.hidden = true;
    history.replaceState(null, "", intakeListUrl());
  }

  function showForm(session) {
    destroyQuills();
    state.session = session;
    activeTab = "overview";
    listView.hidden = true;
    formView.hidden = false;
    renderForm();
    var url =
      "/crm/intake?session_id=" +
      session.id +
      (session.lifecycle_id || meta.lifecycle_id
        ? "&lifecycle_id=" + (session.lifecycle_id || meta.lifecycle_id)
        : session.lead_id || meta.lead_id
          ? "&lead_id=" + (session.lead_id || meta.lead_id) +
            "&service_slug=" + encodeURIComponent(session.service_slug || meta.service_slug || "_common")
          : "");
    history.replaceState(null, "", url);
  }

  function modeLabel(mode) {
    return mode === "in_person" ? "PHẦN B — Gặp trực tiếp" : "PHẦN A — Gọi điện";
  }

  function renderSessionsList(sessions) {
    sessionsList.innerHTML = "";
    if (!sessions || !sessions.length) {
      sessionsList.innerHTML =
        '<p class="intake-hint">Chưa có phiên nào. Tạo buổi gọi hoặc gặp mới.</p>';
      return;
    }
    sessions.forEach(function (s) {
      var row = document.createElement("div");
      row.className = "intake-session-row";
      var badge =
        s.status === "completed"
          ? '<span class="intake-badge intake-badge--done">Hoàn thành</span>'
          : '<span class="intake-badge">Nháp</span>';
      var modeIcon = s.mode === "in_person" ? "🤝" : "📞";
      var decisionTag = s.decision
        ? '<span class="intake-session-row__tag intake-session-row__tag--' +
          escapeHtml(String(s.decision)) +
          '">' +
          escapeHtml(String(s.decision)) +
          "</span>"
        : "";
      row.innerHTML =
        '<div class="intake-session-row__icon" aria-hidden="true">' +
        modeIcon +
        "</div>" +
        '<div class="intake-session-row__body">' +
        "<div class=\"intake-session-row__title\"><strong>#" +
        s.id +
        "</strong> " +
        modeLabel(s.mode) +
        decisionTag +
        "</div>" +
        '<div class="intake-session-row__meta">' +
        "BANT " +
        (s.bant_total || 0) +
        "/30 · " +
        (s.updated_at || s.created_at || "") +
        (s.contact_name ? " · " + escapeHtml(s.contact_name) : "") +
        "</div></div>" +
        badge;
      row.addEventListener("click", function () {
        showForm(s);
      });
      sessionsList.appendChild(row);
    });
  }

  function answers() {
    var a = state.session.answers_json;
    if (!a || typeof a !== "object") {
      a = {};
      state.session.answers_json = a;
    }
    if (!a.phone) a.phone = {};
    if (!a.inperson) a.inperson = {};
    if (!a.red_flags) a.red_flags = [];
    if (!a.urgency) a.urgency = [];
    if (!a.objections) a.objections = {};
    if (!a.demo) a.demo = [];
    if (!a.docs) a.docs = {};
    if (!a.kpi) a.kpi = {};
    if (!a.scope) a.scope = {};
    if (!a.crm_fields) a.crm_fields = {};
    if (!a.meta) a.meta = {};
    return a;
  }

  function suggestDecisionFromBant() {
    var total = state.session.bant_total || 0;
    var redCount = qsa('#intake-red-flags input[type="checkbox"]:checked').length;
    var thresholds = meta.go_thresholds || { go: 24, nurture_min: 18 };
    var suggested = "no_go";
    if (redCount >= 3) suggested = "no_go";
    else if (total >= thresholds.go) suggested = "go";
    else if (total >= thresholds.nurture_min) suggested = "nurture";
    var sel = qs('[data-field="decision"]');
    if (sel && !sel.disabled) sel.value = suggested;
    onFieldChange();
    updateDecisionHint(state.session);
  }

  function updateProgress() {
    var filled = 0;
    var total = 0;
    qsa("[data-field]").forEach(function (el) {
      if (el.classList.contains("intake-quill-wrap")) return;
      total += 1;
      if (String(el.value || "").trim()) filled += 1;
    });
    qsa("[data-bant]:checked").forEach(function () {
      filled += 1;
    });
    total += qsa("[data-bant]").length / 5;
    quillRegistry.forEach(function (wrap) {
      total += 1;
      if (htmlToPlain(readQuillValue(wrap))) filled += 1;
    });
    var pct = total ? Math.min(100, Math.round((filled / total) * 100)) : 0;
    var textEl = qs("#intake-progress-text");
    var fillEl = qs("#intake-progress-fill");
    if (textEl) textEl.textContent = Math.round(filled) + "/" + Math.round(total);
    if (fillEl) fillEl.style.width = pct + "%";
  }

  function showRecapBanners(s, def) {
    var recapEl = qs("#intake-recap-banner");
    var aiEl = qs("#intake-ai-prefill-banner");
    var summaryEl = qs("#intake-ai-summary-banner");
    var ans = answers();
    var meta = ans.meta || {};
    var recapText = (meta.recap && meta.recap.text) || ans.recap || meta.recap || "";
    if (recapEl) {
      if (s.mode === "in_person" && recapText) {
        var when = (meta.recap && meta.recap.phone_completed_at) || meta.phone_completed_at || "";
        recapEl.hidden = false;
        recapEl.innerHTML =
          "<strong>Recap buổi gọi" +
          (when ? " (" + escapeHtml(when.slice(0, 16)) + ")" : "") +
          ":</strong><pre class=\"intake-recap-pre\">" +
          escapeHtml(recapText) +
          "</pre>";
      } else {
        recapEl.hidden = true;
        recapEl.innerHTML = "";
      }
    }
    if (aiEl) {
      var brief = meta.ai_brief || meta.pain_summary || "";
      var qualifyQs = meta.qualify_questions;
      if (brief || (qualifyQs && qualifyQs.length)) {
        aiEl.hidden = false;
        var html = "<strong>Prefill từ lead / AI qualify:</strong> ";
        if (brief) html += escapeHtml(brief.slice(0, 400));
        if (qualifyQs && qualifyQs.length) {
          html +=
            "<ul class=\"intake-qualify-hints\">" +
            qualifyQs
              .slice(0, 5)
              .map(function (q) {
                return "<li>" + escapeHtml(String(q)) + "</li>";
              })
              .join("") +
            "</ul>";
        }
        aiEl.innerHTML = html;
      } else {
        aiEl.hidden = true;
        aiEl.innerHTML = "";
      }
    }
    if (summaryEl) {
      var aiSummary = String(s.ai_summary || "").trim();
      var suggested = s.ai_suggested_questions || [];
      if (aiSummary) {
        summaryEl.hidden = false;
        var sumHtml =
          "<strong>AI tóm tắt buổi intake:</strong><pre class=\"intake-recap-pre\">" +
          escapeHtml(aiSummary) +
          "</pre>";
        if (suggested.length) {
          sumHtml +=
            "<div class=\"intake-ai-questions\"><em>Câu hỏi gợi ý:</em><ul>" +
            suggested
              .slice(0, 6)
              .map(function (q) {
                return "<li>" + escapeHtml(String(q)) + "</li>";
              })
              .join("") +
            "</ul></div>";
        }
        summaryEl.innerHTML = sumHtml;
      } else if (s.status === "completed") {
        summaryEl.hidden = false;
        summaryEl.innerHTML =
          "<span class=\"intake-hint\">⏳ Đang tạo AI tóm tắt… (tự cập nhật sau vài giây)</span>";
      } else {
        summaryEl.hidden = true;
        summaryEl.innerHTML = "";
      }
    }
  }

  var aiPollTimer = null;
  function stopAiSummaryPoll() {
    if (aiPollTimer) {
      clearInterval(aiPollTimer);
      aiPollTimer = null;
    }
  }

  function pollAiSummary() {
    stopAiSummaryPoll();
    if (!state.session || state.session.status !== "completed") return;
    if (String(state.session.ai_summary || "").trim()) return;
    var tries = 0;
    aiPollTimer = setInterval(function () {
      tries += 1;
      if (tries > 12 || !state.session) {
        stopAiSummaryPoll();
        return;
      }
      api("/api/crm/intake/sessions/" + state.session.id)
        .then(function (row) {
          if (row && row.ai_summary) {
            state.session = row;
            showRecapBanners(state.session, state.definition);
            stopAiSummaryPoll();
          }
        })
        .catch(function () {});
    }, 3000);
  }

  function setupPrintLink() {
    var link = qs("#intake-print-link");
    if (!link) return;
    if (meta.print_form_url) {
      link.href = meta.print_form_url;
      link.hidden = false;
    } else {
      link.hidden = true;
    }
  }

  function renderForm() {
    var s = state.session;
    var def = state.definition;
    var readonly = s.status === "completed";
    var badge = qs("#intake-session-badge");
    badge.textContent = readonly ? "Hoàn thành" : "Nháp";
    badge.className =
      "intake-badge" + (readonly ? " intake-badge--done" : "");
    qs("#intake-mode-label").textContent = modeLabel(s.mode);

    updateTabsForMode(s.mode);

    qsa("[data-field]").forEach(function (el) {
      if (el.classList.contains("intake-quill-wrap")) return;
      var key = el.getAttribute("data-field");
      if (el.tagName === "INPUT" || el.tagName === "SELECT" || el.tagName === "TEXTAREA") {
        el.value = s[key] != null ? s[key] : "";
        el.disabled = readonly;
      }
    });

    qs("#intake-call-script").textContent = def.call_script || "";
    renderBant(def.bant_rows || [], s.bant_json || {}, readonly);
    renderQuestions("phone", def.phone_questions || [], answers().phone, readonly);
    renderQuestions("inperson", def.inperson_questions || [], answers().inperson, readonly);
    renderRedFlags(def.red_flags || [], answers().red_flags, readonly);
    renderCheckboxGroup(
      "intake-urgency",
      def.urgency_triggers || [],
      answers().urgency,
      readonly,
      "urgency"
    );
    renderObjections(def.objections || [], answers().objections, readonly);
    renderDemoChecklist(def.demo_checklist || [], answers().demo, readonly);
    renderDocsChecklist(def.docs || [], answers().docs, readonly);
    renderKpiScope(
      def.kpi_questions || [],
      def.scope_questions || [],
      answers().kpi,
      answers().scope,
      readonly
    );
    renderStakeholders(s.stakeholders_json || [], readonly);
    renderCommitments(s.commitments_json || [], readonly);
    renderCrmFields(state.formFields, answers().crm_fields, readonly);
    renderDecisionReason(s.decision_reason || "", readonly);
    showRecapBanners(s, def);
    pollAiSummary();
    setupPrintLink();
    updateBantTotal(s.bant_total || 0);
    updateDecisionHint(s);
    updateProgress();

    var completeBtn = qs("#intake-complete");
    if (completeBtn) {
      completeBtn.textContent =
        meta.is_common_form && !meta.workflow_url
          ? "Hoàn thành intake"
          : "Hoàn thành → Workflow";
      completeBtn.disabled = readonly;
    }
    qs("#intake-reopen").hidden = !readonly;
    setSaveStatus("");
  }

  function renderDecisionReason(value, readonly) {
    var wrap = qs("#intake-decision-reason-editor");
    if (!wrap) return;
    wrap.innerHTML = '<div class="intake-quill-editor"></div>';
    mountQuill(wrap, value, readonly, true);
    registerQuill("field:decision_reason", wrap);
  }

  function renderBant(rows, bant, readonly) {
    var wrap = qs("#intake-bant-rows");
    wrap.innerHTML = "";
    rows.forEach(function (row) {
      var div = document.createElement("div");
      div.className = "intake-bant-row";
      var lbl = document.createElement("div");
      lbl.className = "intake-bant-label";
      lbl.textContent = row.label;
      var hint = document.createElement("div");
      hint.className = "intake-bant-hint";
      hint.textContent = row.hint || "";
      var scores = document.createElement("div");
      scores.className = "intake-bant-scores";
      for (var i = 1; i <= 5; i++) {
        var label = document.createElement("label");
        label.className = "intake-bant-score";
        var radio = document.createElement("input");
        radio.type = "radio";
        radio.name = "bant-" + row.key;
        radio.value = String(i);
        radio.setAttribute("data-bant", row.key);
        if (String(bant[row.key]) === String(i)) radio.checked = true;
        radio.disabled = readonly;
        radio.addEventListener("change", onFieldChange);
        label.appendChild(radio);
        label.appendChild(document.createTextNode(String(i)));
        scores.appendChild(label);
      }
      div.appendChild(lbl);
      div.appendChild(hint);
      div.appendChild(scores);
      wrap.appendChild(div);
    });
  }

  function renderQuestions(prefix, questions, store, readonly) {
    var container =
      prefix === "phone"
        ? qs("#intake-phone-questions")
        : qs("#intake-inperson-questions");
    container.innerHTML = "";
    var table = document.createElement("table");
    table.className = "intake-q-table";
    table.innerHTML =
      "<thead><tr><th>#</th><th>Câu hỏi</th><th>Ghi chú / trả lời</th></tr></thead>";
    var tbody = document.createElement("tbody");
    questions.forEach(function (q, idx) {
      var key = "p" + idx;
      var quillKey = prefix + ":" + key;
      var tr = document.createElement("tr");
      var numTd = document.createElement("td");
      numTd.className = "intake-q-num";
      numTd.textContent = String(idx + 1);
      var qTd = document.createElement("td");
      qTd.className = "intake-q-text";
      qTd.textContent = q;
      var aTd = document.createElement("td");
      var wrap = document.createElement("div");
      wrap.className = "intake-quill-wrap intake-quill-wrap--compact";
      wrap.setAttribute("data-answer", quillKey);
      wrap.innerHTML = '<div class="intake-quill-editor"></div>';
      aTd.appendChild(wrap);
      tr.appendChild(numTd);
      tr.appendChild(qTd);
      tr.appendChild(aTd);
      tbody.appendChild(tr);
      mountQuill(wrap, store[key] || "", readonly, true);
      registerQuill("answer:" + quillKey, wrap);
    });
    table.appendChild(tbody);
    container.appendChild(table);
  }

  function renderRedFlags(flags, selected, readonly) {
    var wrap = qs("#intake-red-flags");
    wrap.innerHTML = "";
    flags.forEach(function (flag, idx) {
      var label = document.createElement("label");
      label.className = "intake-check-item";
      var cb = document.createElement("input");
      cb.type = "checkbox";
      cb.value = flag;
      cb.id = "intake-rf-" + idx;
      cb.checked = selected.indexOf(flag) >= 0;
      cb.disabled = readonly;
      cb.addEventListener("change", onFieldChange);
      var span = document.createElement("span");
      span.textContent = flag;
      label.appendChild(cb);
      label.appendChild(span);
      wrap.appendChild(label);
    });
  }

  function renderCheckboxGroup(wrapId, items, selected, readonly, dataKind) {
    var wrap = qs("#" + wrapId);
    if (!wrap) return;
    wrap.innerHTML = "";
    items.forEach(function (item, idx) {
      var label = document.createElement("label");
      label.className = "intake-check-item";
      var cb = document.createElement("input");
      cb.type = "checkbox";
      cb.value = item;
      cb.setAttribute("data-check-group", dataKind);
      cb.checked = selected.indexOf(item) >= 0;
      cb.disabled = readonly;
      cb.addEventListener("change", onFieldChange);
      var span = document.createElement("span");
      span.textContent = item;
      label.appendChild(cb);
      label.appendChild(span);
      wrap.appendChild(label);
    });
  }

  function renderObjections(items, store, readonly) {
    var wrap = qs("#intake-objections");
    if (!wrap) return;
    wrap.innerHTML = "";
    if (!items.length) {
      wrap.innerHTML = '<p class="intake-hint">Không có objections cho dịch vụ này.</p>';
      return;
    }
    items.forEach(function (item, idx) {
      var title = item.title || item[0] || "";
      var hint = item.hint || item[1] || "";
      var block = document.createElement("div");
      block.className = "intake-objection";
      block.innerHTML =
        '<div class="intake-objection-title">' +
        escapeHtml(title) +
        '</div><div class="intake-hint">' +
        escapeHtml(hint) +
        "</div>";
      var qWrap = document.createElement("div");
      qWrap.className = "intake-quill-wrap intake-quill-wrap--compact";
      qWrap.setAttribute("data-objection", String(idx));
      qWrap.innerHTML = '<div class="intake-quill-editor"></div>';
      block.appendChild(qWrap);
      wrap.appendChild(block);
      mountQuill(qWrap, store[String(idx)] || store[idx] || "", readonly, true);
      registerQuill("objection:" + idx, qWrap);
    });
  }

  function renderDemoChecklist(items, selected, readonly) {
    var wrap = qs("#intake-demo-checklist");
    if (!wrap) return;
    wrap.innerHTML = "";
    if (!items.length) {
      wrap.innerHTML = '<p class="intake-hint">—</p>';
      return;
    }
    items.forEach(function (item) {
      var label = document.createElement("label");
      label.className = "intake-check-item";
      var cb = document.createElement("input");
      cb.type = "checkbox";
      cb.value = item;
      cb.setAttribute("data-check-group", "demo");
      cb.checked = selected.indexOf(item) >= 0;
      cb.disabled = readonly;
      cb.addEventListener("change", onFieldChange);
      var span = document.createElement("span");
      span.textContent = item;
      label.appendChild(cb);
      label.appendChild(span);
      wrap.appendChild(label);
    });
  }

  function renderDocsChecklist(docs, store, readonly) {
    var wrap = qs("#intake-docs-checklist");
    if (!wrap) return;
    wrap.innerHTML = "";
    if (!docs.length) {
      wrap.innerHTML = '<p class="intake-hint">—</p>';
      return;
    }
    var table = document.createElement("table");
    table.className = "intake-q-table intake-docs-table";
    table.innerHTML =
      "<thead><tr><th>Tài liệu</th><th>Lead</th><th>Onboard</th></tr></thead>";
    var tbody = document.createElement("tbody");
    docs.forEach(function (doc, idx) {
      var name = doc.name || doc[0] || "";
      var saved = store[String(idx)] || store[name] || {};
      var tr = document.createElement("tr");
      tr.innerHTML = "<td>" + escapeHtml(name) + "</td>";
      ["lead", "onboard"].forEach(function (col) {
        var td = document.createElement("td");
        var cb = document.createElement("input");
        cb.type = "checkbox";
        cb.setAttribute("data-doc", idx + ":" + col);
        cb.checked = !!(saved && saved[col]);
        cb.disabled = readonly;
        cb.addEventListener("change", onFieldChange);
        td.appendChild(cb);
        tr.appendChild(td);
      });
      tbody.appendChild(tr);
    });
    table.appendChild(tbody);
    wrap.appendChild(table);
  }

  function renderKpiScope(kpiQs, scopeQs, kpiStore, scopeStore, readonly) {
    var wrap = qs("#intake-kpi-scope");
    if (!wrap) return;
    wrap.innerHTML = "";
    function addBlock(title, prefix, questions, store) {
      if (!questions.length) return;
      var h = document.createElement("h5");
      h.className = "intake-subtitle";
      h.textContent = title;
      wrap.appendChild(h);
      questions.forEach(function (q, idx) {
        var key = "p" + idx;
        var block = document.createElement("div");
        block.className = "intake-question";
        block.innerHTML =
          '<div class="intake-question-label">' + escapeHtml(q) + "</div>";
        var qWrap = document.createElement("div");
        qWrap.className = "intake-quill-wrap intake-quill-wrap--compact";
        qWrap.setAttribute("data-" + prefix + "-answer", key);
        qWrap.innerHTML = '<div class="intake-quill-editor"></div>';
        block.appendChild(qWrap);
        wrap.appendChild(block);
        mountQuill(qWrap, store[key] || "", readonly, true);
        registerQuill(prefix + ":" + key, qWrap);
      });
    }
    addBlock("KPI", "kpi", kpiQs, kpiStore);
    addBlock("Phạm vi IN/OUT", "scope", scopeQs, scopeStore);
  }

  function renderStakeholders(rows, readonly) {
    var wrap = qs("#intake-stakeholders");
    var table = document.createElement("table");
    table.innerHTML =
      "<thead><tr><th>Vai trò</th><th>Họ tên</th><th>Chức danh</th><th>Ảnh hưởng</th><th>Ghi chú</th></tr></thead>";
    var tbody = document.createElement("tbody");
    rows.forEach(function (row, idx) {
      var tr = document.createElement("tr");
      tr.innerHTML = "<td>" + escapeHtml(row.role_label || row.role) + "</td>";
      ["name", "title", "influence"].forEach(function (field) {
        var td = document.createElement("td");
        var inp = document.createElement("input");
        inp.setAttribute("data-stake", field + ":" + idx);
        inp.value = row[field] || "";
        inp.disabled = readonly;
        inp.addEventListener("input", onFieldChange);
        td.appendChild(inp);
        tr.appendChild(td);
      });
      var notesTd = document.createElement("td");
      var notesWrap = document.createElement("div");
      notesWrap.className = "intake-quill-wrap intake-quill-wrap--compact";
      notesWrap.setAttribute("data-stake-notes", String(idx));
      notesWrap.innerHTML = '<div class="intake-quill-editor"></div>';
      notesTd.appendChild(notesWrap);
      tr.appendChild(notesTd);
      tbody.appendChild(tr);
      mountQuill(notesWrap, row.notes || "", readonly, true);
      registerQuill("stake:notes:" + idx, notesWrap);
    });
    table.appendChild(tbody);
    wrap.innerHTML = "";
    wrap.appendChild(table);
  }

  function renderCommitments(rows, readonly) {
    var wrap = qs("#intake-commitments");
    var table = document.createElement("table");
    table.innerHTML =
      "<thead><tr><th>Cam kết</th><th>Chi tiết</th><th>Deadline</th></tr></thead>";
    var tbody = document.createElement("tbody");
    rows.forEach(function (row, idx) {
      var tr = document.createElement("tr");
      var labelTd = document.createElement("td");
      labelTd.textContent = row.label || "";
      tr.appendChild(labelTd);
      var detailTd = document.createElement("td");
      var detailWrap = document.createElement("div");
      detailWrap.className = "intake-quill-wrap intake-quill-wrap--compact";
      detailWrap.setAttribute("data-commit-detail", String(idx));
      detailWrap.innerHTML = '<div class="intake-quill-editor"></div>';
      detailTd.appendChild(detailWrap);
      tr.appendChild(detailTd);
      var deadlineTd = document.createElement("td");
      var deadlineInp = document.createElement("input");
      deadlineInp.setAttribute("data-commit", "deadline:" + idx);
      deadlineInp.value = row.deadline || "";
      deadlineInp.disabled = readonly;
      deadlineInp.addEventListener("input", onFieldChange);
      deadlineTd.appendChild(deadlineInp);
      tr.appendChild(deadlineTd);
      tbody.appendChild(tr);
      mountQuill(detailWrap, row.detail || "", readonly, true);
      registerQuill("commit:detail:" + idx, detailWrap);
    });
    table.appendChild(tbody);
    wrap.innerHTML = "";
    wrap.appendChild(table);
  }

  function renderCrmFields(fields, store, readonly) {
    var wrap = qs("#intake-crm-fields");
    wrap.innerHTML = "";
    if (!fields.length) {
      wrap.innerHTML =
        '<p class="intake-hint">Không có trường CRM cho dịch vụ này.</p>';
      return;
    }
    fields.forEach(function (f) {
      var fieldWrap = document.createElement("div");
      fieldWrap.className = "intake-field";
      var title = document.createElement("span");
      title.textContent = f.label;
      fieldWrap.appendChild(title);
      if (f.type === "textarea") {
        var qWrap = document.createElement("div");
        qWrap.className = "intake-quill-wrap";
        qWrap.setAttribute("data-crm", f.key);
        qWrap.innerHTML = '<div class="intake-quill-editor"></div>';
        fieldWrap.appendChild(qWrap);
        mountQuill(qWrap, store[f.key] || "", readonly, false);
        registerQuill("crm:" + f.key, qWrap);
      } else {
        var input = document.createElement("input");
        input.type = f.type === "number" ? "number" : "text";
        input.setAttribute("data-crm", f.key);
        input.value = store[f.key] || "";
        input.disabled = readonly;
        input.addEventListener("input", onFieldChange);
        fieldWrap.appendChild(input);
      }
      wrap.appendChild(fieldWrap);
    });
  }

  function collectPayload() {
    var s = state.session;
    var ans = answers();
    qsa("[data-field]").forEach(function (el) {
      if (el.classList.contains("intake-quill-wrap")) return;
      var key = el.getAttribute("data-field");
      if (el.tagName === "INPUT" || el.tagName === "SELECT" || el.tagName === "TEXTAREA") {
        s[key] = el.value;
      }
    });

    var decisionWrap = qs("#intake-decision-reason-editor");
    s.decision_reason = htmlToPlain(readQuillValue(decisionWrap));

    var bant = {};
    qsa("[data-bant]:checked").forEach(function (el) {
      bant[el.getAttribute("data-bant")] = parseInt(el.value, 10) || 0;
    });

    quillRegistry.forEach(function (wrapEl, key) {
      if (key.indexOf("answer:") === 0) {
        var parts = key.replace("answer:", "").split(":");
        var section = parts[0];
        var akey = parts[1];
        if (!ans[section]) ans[section] = {};
        ans[section][akey] = readQuillValue(wrapEl);
      } else if (key.indexOf("crm:") === 0) {
        ans.crm_fields[key.replace("crm:", "")] = htmlToPlain(readQuillValue(wrapEl));
      } else if (key.indexOf("objection:") === 0) {
        ans.objections[key.replace("objection:", "")] = htmlToPlain(readQuillValue(wrapEl));
      } else if (key.indexOf("kpi:") === 0) {
        ans.kpi[key.replace("kpi:", "")] = htmlToPlain(readQuillValue(wrapEl));
      } else if (key.indexOf("scope:") === 0) {
        ans.scope[key.replace("scope:", "")] = htmlToPlain(readQuillValue(wrapEl));
      }
    });

    ans.red_flags = qsa('#intake-red-flags input[type="checkbox"]:checked').map(
      function (cb) {
        return cb.value;
      }
    );
    ans.urgency = qsa('#intake-urgency input[type="checkbox"]:checked').map(function (cb) {
      return cb.value;
    });
    ans.demo = qsa('[data-check-group="demo"]:checked').map(function (cb) {
      return cb.value;
    });
    var docsStore = {};
    qsa("[data-doc]").forEach(function (cb) {
      var p = cb.getAttribute("data-doc").split(":");
      var idx = p[0];
      var col = p[1];
      if (!docsStore[idx]) docsStore[idx] = {};
      docsStore[idx][col] = cb.checked;
    });
    ans.docs = docsStore;

    qsa("[data-crm]").forEach(function (el) {
      if (el.tagName === "INPUT") {
        ans.crm_fields[el.getAttribute("data-crm")] = el.value;
      }
    });

    var stakeholders = (s.stakeholders_json || []).slice();
    qsa("[data-stake]").forEach(function (el) {
      var p = el.getAttribute("data-stake").split(":");
      var field = p[0];
      var idx = parseInt(p[1], 10);
      if (stakeholders[idx]) stakeholders[idx][field] = el.value;
    });
    stakeholders.forEach(function (_row, idx) {
      var notesWrap = quillRegistry.get("stake:notes:" + idx);
      if (notesWrap && stakeholders[idx]) {
        stakeholders[idx].notes = htmlToPlain(readQuillValue(notesWrap));
      }
    });

    var commitments = (s.commitments_json || []).slice();
    qsa("[data-commit]").forEach(function (el) {
      var p = el.getAttribute("data-commit").split(":");
      var field = p[0];
      var idx = parseInt(p[1], 10);
      if (commitments[idx]) commitments[idx][field] = el.value;
    });
    commitments.forEach(function (_row, idx) {
      var detailWrap = quillRegistry.get("commit:detail:" + idx);
      if (detailWrap && commitments[idx]) {
        commitments[idx].detail = htmlToPlain(readQuillValue(detailWrap));
      }
    });

    return {
      mode: s.mode,
      contact_name: s.contact_name,
      contact_role: s.contact_role,
      company_name: s.company_name,
      source: s.source,
      lead_temperature: s.lead_temperature,
      decision: s.decision,
      decision_reason: s.decision_reason,
      next_meeting_at: s.next_meeting_at,
      next_meeting_note: s.next_meeting_note,
      proposal_date: s.proposal_date,
      bant_json: bant,
      answers_json: ans,
      stakeholders_json: stakeholders,
      commitments_json: commitments,
    };
  }

  function updateBantTotal(total) {
    qs("#intake-bant-total").textContent = (total || 0) + "/30";
  }

  function updateDecisionHint(s) {
    var hint = qs("#intake-decision-hint");
    var total = s.bant_total || 0;
    var text = "Gợi ý: ";
    if (total >= 24) text += "Go (≥24)";
    else if (total >= 18) text += "Nurture (18–23)";
    else if (total > 0) text += "No-Go (<18)";
    else text += "Chấm BANT để có gợi ý";
    hint.textContent = text;
  }

  function setSaveStatus(msg, isError) {
    saveStatus.textContent = msg || "";
    saveStatus.className = "intake-save-status" + (isError ? " is-error" : "");
  }

  function onFieldChange() {
    state.dirty = true;
    clearTimeout(state.saveTimer);
    state.saveTimer = setTimeout(saveNow, 2000);
    setSaveStatus("Đang chờ lưu…");
  }

  function saveNow() {
    if (!state.session || !state.session.id || state.saving) return;
    if (state.session.status === "completed") return;
    state.saving = true;
    var payload = collectPayload();
    api("/api/crm/intake/sessions/" + state.session.id, {
      method: "PATCH",
      body: payload,
    })
      .then(function (updated) {
        state.session = updated;
        state.dirty = false;
        updateBantTotal(updated.bant_total);
        updateDecisionHint(updated);
        updateProgress();
        var now = new Date();
        setSaveStatus(
          "Đã lưu " +
            now.getHours().toString().padStart(2, "0") +
            ":" +
            now.getMinutes().toString().padStart(2, "0")
        );
      })
      .catch(function (err) {
        setSaveStatus(err.message || "Lỗi lưu", true);
      })
      .finally(function () {
        state.saving = false;
      });
  }

  function createSession(mode) {
    if (!meta.lifecycle_id && !meta.lead_id) {
      alert("Thiếu lifecycle hoặc lead");
      return;
    }
    var body = {
      service_slug: meta.service_slug || "_common",
      mode: mode,
      company_name: meta.customer_name || "",
    };
    if (meta.lifecycle_id) body.lifecycle_id = meta.lifecycle_id;
    if (meta.lead_id) body.lead_id = meta.lead_id;
    if (meta.lead_name) body.contact_name = meta.lead_name;
    api("/api/crm/intake/sessions", {
      method: "POST",
      body: body,
    })
      .then(function (session) {
        refreshSessionsList();
        showForm(session);
      })
      .catch(function (err) {
        alert(err.message || "Không tạo được phiên");
      });
  }

  function completeSession() {
    if (state.session.status === "completed") return;
    saveNow();
    setTimeout(function () {
      api("/api/crm/intake/sessions/" + state.session.id + "/complete", {
        method: "POST",
        body: {},
      })
        .then(function (updated) {
          state.session = updated;
          if (meta.workflow_url) {
            window.location.href = meta.workflow_url + "?intake_done=" + updated.id;
            return;
          }
          renderForm();
          refreshSessionsList();
          setSaveStatus(
            meta.is_common_form && !meta.workflow_url
              ? "Đã hoàn thành · ghi lead & AI summary"
              : "Đã hoàn thành & sync CRM"
          );
        })
        .catch(function (err) {
          alert(err.message || "Không hoàn thành được");
        });
    }, 500);
  }

  function reopenSession() {
    api("/api/crm/intake/sessions/" + state.session.id + "/reopen", {
      method: "POST",
      body: {},
    })
      .then(function (updated) {
        state.session = updated;
        renderForm();
        refreshSessionsList();
      })
      .catch(function (err) {
        alert(err.message || "Không mở lại được");
      });
  }

  function refreshSessionsList() {
    var q = meta.lifecycle_id
      ? "lifecycle_id=" + meta.lifecycle_id
      : meta.lead_id
        ? "lead_id=" + meta.lead_id
        : "";
    if (!q) return;
    api("/api/crm/intake/sessions?" + q).then(function (data) {
      renderSessionsList(data.sessions || []);
    });
  }

  qsa("[data-create-mode]").forEach(function (btn) {
    btn.addEventListener("click", function () {
      createSession(btn.getAttribute("data-create-mode"));
    });
  });

  qs("#intake-back-list").addEventListener("click", showList);
  qs("#intake-save-now").addEventListener("click", saveNow);
  qs("#intake-complete").addEventListener("click", completeSession);
  qs("#intake-reopen").addEventListener("click", reopenSession);
  var suggestBtn = qs("#intake-suggest-decision");
  if (suggestBtn) suggestBtn.addEventListener("click", suggestDecisionFromBant);
  bindTabControls();

  qsa("[data-field]").forEach(function (el) {
    if (el.classList.contains("intake-quill-wrap")) return;
    el.addEventListener("input", onFieldChange);
    el.addEventListener("change", onFieldChange);
  });

  renderSessionsList(meta.sessions || []);
  if (state.session) {
    showForm(state.session);
  } else if (meta.auto_create && (meta.lifecycle_id || meta.lead_id)) {
    createSession(meta.auto_create_mode || "phone");
  }
})();
