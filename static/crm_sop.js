(function () {
  "use strict";

  window.addEventListener("pageshow", (ev) => {
    if (ev.persisted) window.location.reload();
  });

  const metaEl = document.getElementById("crm-sop-meta");
  /** @type {Record<string, any>} */
  const meta = metaEl ? JSON.parse(metaEl.textContent) : {};
  const {
    task_statuses = [],
    task_status_labels = {},
    run_statuses = [],
    run_status_labels = {},
    step_roles = [],
    step_role_labels = {},
    campaign_channels = [],
    campaign_channel_labels = {},
  } = meta;

  /** @type {Array<Record<string, any>>} */
  let cachedTemplates = [];
  /** @type {Array<Record<string, any>>} */
  let cachedCampaigns = [];
  /** @type {Array<Record<string, any>>} */
  let cachedStaff = [];
  /** @type {Record<number, Array<Record<string, any>>>} */
  let cachedRunTasks = {};
  /** @type {Set<number>} */
  let expandedRuns = new Set();

  let busyTimer;

  // ── utils ──────────────────────────────────────────────────────────────────

  function esc(s) {
    const d = document.createElement("div");
    d.textContent = s ?? "";
    return d.innerHTML;
  }

  function escAttr(s) {
    return esc(s).replace(/"/g, "&quot;");
  }

  function setBusy(txt) {
    // No-op — we use inline per-section messages
    void txt;
  }

  /** @param {HTMLElement|null} el @param {string} msg @param {boolean} [ok] */
  function showMsg(el, msg, ok) {
    if (!el) return;
    if (!msg) { el.hidden = true; return; }
    el.hidden = false;
    el.textContent = msg;
    el.classList.toggle("is-error", !ok);
    if (ok) el.classList.add("is-success");
    else el.classList.remove("is-success");
  }

  async function reqJson(url, opts = {}) {
    const headers = { Accept: "application/json", ...(opts.headers || {}) };
    const body = opts.body;
    if (body && typeof body === "string") headers["Content-Type"] = "application/json";
    const res = await fetch(url, { credentials: "same-origin", ...opts, headers });
    const ct = res.headers.get("Content-Type") || "";
    let data = {};
    if (ct.includes("application/json")) {
      try { data = await res.json(); } catch { data = {}; }
    }
    if (res.status === 401) {
      if (typeof data.login === "string") window.location.href = data.login;
      throw new Error(String(data.error || "Chưa đăng nhập"));
    }
    if (!res.ok) throw new Error(String(data.error || res.statusText || "Lỗi mạng"));
    return data;
  }

  function todayIso() {
    const d = new Date();
    return `${d.getFullYear()}-${String(d.getMonth()+1).padStart(2,"0")}-${String(d.getDate()).padStart(2,"0")}`;
  }

  function fmtDate(iso) {
    const m = String(iso||"").match(/^(\d{4})-(\d{2})-(\d{2})/);
    if (!m) return iso||"—";
    return `${m[3]}/${m[2]}/${m[1]}`;
  }

  function isOverdue(iso) {
    if (!iso) return false;
    return iso < todayIso();
  }

  function pct(done, total) {
    if (!total) return 0;
    return Math.round((done / total) * 100);
  }

  // ── modal helpers ──────────────────────────────────────────────────────────

  function openModal(root) {
    root.hidden = false;
    root.classList.add("is-open");
    document.body.style.overflow = "hidden";
  }
  function closeModal(root) {
    root.hidden = true;
    root.classList.remove("is-open");
    document.body.style.overflow = "";
  }

  document.querySelectorAll("[data-close-modal]").forEach((el) =>
    el.addEventListener("click", () => {
      const r = el.closest(".crm-modal-root");
      if (r) closeModal(r);
    }),
  );
  document.addEventListener("keydown", (e) => {
    if (e.key !== "Escape") return;
    document.querySelectorAll(".crm-modal-root:not([hidden])").forEach((r) => {
      if (r instanceof HTMLElement) closeModal(r);
    });
  });

  // ── fillSelect ─────────────────────────────────────────────────────────────

  /** @param {HTMLSelectElement|null} sel @param {string[]} ids @param {Record<string,string>} labels */
  function fillSelect(sel, ids, labels) {
    if (!sel) return;
    sel.innerHTML = "";
    ids.forEach((id) => {
      const o = document.createElement("option");
      o.value = id; o.textContent = labels[id] || id;
      sel.appendChild(o);
    });
  }

  // populate static selects once
  fillSelect(document.getElementById("crm-sop-tpl-channel"), campaign_channels, campaign_channel_labels);
  fillSelect(document.getElementById("crm-sop-step-role"), step_roles, step_role_labels);
  fillSelect(document.getElementById("crm-sop-task-role"), step_roles, step_role_labels);
  fillSelect(document.getElementById("crm-sop-task-status"), task_statuses, task_status_labels);
  fillSelect(document.getElementById("crm-sop-launch-status"), run_statuses, run_status_labels);
  fillSelect(document.getElementById("crm-sop-run-status-sel"), run_statuses, run_status_labels);

  // ── tab switch ─────────────────────────────────────────────────────────────

  function switchTab(tab) {
    document.querySelectorAll("[data-sop-tab]").forEach((btn) => {
      if (!(btn instanceof HTMLElement)) return;
      btn.classList.toggle("is-active", btn.getAttribute("data-sop-tab") === tab);
    });
    document.querySelectorAll("[data-sop-pane]").forEach((pane) => {
      if (!(pane instanceof HTMLElement)) return;
      pane.hidden = pane.getAttribute("data-sop-pane") !== tab;
    });
    if (tab === "runs") loadRuns().catch(() => {});
    if (tab === "templates") loadTemplates().catch(() => {});
    if (tab === "overdue") loadOverdue().catch(() => {});
  }

  document.querySelectorAll("[data-sop-tab]").forEach((btn) =>
    btn.addEventListener("click", () => {
      const t = btn.getAttribute("data-sop-tab");
      if (t) switchTab(t);
    }),
  );

  // ── loading helpers ────────────────────────────────────────────────────────

  async function loadStaff() {
    try {
      const d = await reqJson("/api/crm/staff");
      cachedStaff = d.staff || [];
    } catch { cachedStaff = []; }
  }

  async function loadCampaignOptions() {
    try {
      const d = await reqJson("/api/crm/campaigns?include_inactive=1");
      cachedCampaigns = d.campaigns || [];
    } catch { cachedCampaigns = []; }
  }

  function populateCampaignSelect(sel, selectedId) {
    if (!sel) return;
    sel.innerHTML = '<option value="">— Tuỳ chọn —</option>';
    cachedCampaigns.forEach((c) => {
      const o = document.createElement("option");
      o.value = String(c.id);
      const off = Number(c.active) === 0 ? " [tắt]" : "";
      o.textContent = `${c.code ? "["+c.code+"] " : ""}${c.name||""}${off}`;
      sel.appendChild(o);
    });
    if (selectedId) sel.value = String(selectedId);
  }

  function populateTemplateSelect(sel) {
    if (!sel) return;
    sel.innerHTML = '<option value="">— Chọn playbook —</option>';
    cachedTemplates.filter(t => Number(t.active) !== 0).forEach((t) => {
      const o = document.createElement("option");
      o.value = String(t.id);
      const ch = campaign_channel_labels[t.channel] || t.channel || "";
      o.textContent = `${t.code ? "["+t.code+"] " : ""}${t.name} (${ch})`;
      sel.appendChild(o);
    });
  }

  function populateStaffSelect(sel, selectedId) {
    if (!sel) return;
    sel.innerHTML = '<option value="">— Chưa gán —</option>';
    cachedStaff.forEach((s) => {
      const o = document.createElement("option");
      o.value = String(s.id);
      o.textContent = String(s.name || s.id);
      sel.appendChild(o);
    });
    if (selectedId) sel.value = String(selectedId);
  }

  // ── progress ring ─────────────────────────────────────────────────────────

  function progressRingHtml(done, total) {
    const p = pct(done, total);
    const r = 20;
    const circ = 2 * Math.PI * r;
    const offset = circ * (1 - p / 100);
    return `
      <svg class="crm-sop-ring" viewBox="0 0 48 48" width="48" height="48" aria-label="${p}%" role="img">
        <circle cx="24" cy="24" r="${r}" fill="none" stroke="rgba(26,32,44,.1)" stroke-width="4"/>
        <circle cx="24" cy="24" r="${r}" fill="none" stroke="${p === 100 ? "#22c55e" : "#398b43"}"
          stroke-width="4" stroke-dasharray="${circ}" stroke-dashoffset="${offset}"
          stroke-linecap="round" transform="rotate(-90 24 24)"/>
        <text x="24" y="27" text-anchor="middle" font-size="10" font-weight="700" fill="currentColor">${p}%</text>
      </svg>`;
  }

  // ── checklist helpers ──────────────────────────────────────────────────────

  /**
   * @param {HTMLUListElement|null} ul
   * @param {Array<{label: string, done?: boolean}>} items
   */
  function renderChecklist(ul, items) {
    if (!ul) return;
    ul.innerHTML = "";
    (items || []).forEach((item, i) => {
      const li = document.createElement("li");
      li.className = "crm-sop-cl-item";
      li.dataset.idx = String(i);
      li.innerHTML = `
        <input type="checkbox" class="crm-sop-cl-check" ${item.done ? "checked" : ""}
          aria-label="${escAttr(String(item.label||""))}" />
        <input type="text" class="crm-sop-cl-label" value="${escAttr(String(item.label||""))}"
          placeholder="Mục kiểm tra…" maxlength="500" />
        <button type="button" class="crm-sop-cl-del" aria-label="Xoá mục">×</button>`;
      ul.appendChild(li);
    });
  }

  /**
   * @param {HTMLUListElement|null} ul
   * @returns {Array<{label: string, done: boolean}>}
   */
  function collectChecklist(ul) {
    if (!ul) return [];
    /** @type {Array<{label: string, done: boolean}>} */
    const out = [];
    ul.querySelectorAll(".crm-sop-cl-item").forEach((li) => {
      const lbl = /** @type {HTMLInputElement|null} */ (li.querySelector(".crm-sop-cl-label"));
      const chk = /** @type {HTMLInputElement|null} */ (li.querySelector(".crm-sop-cl-check"));
      if (lbl) out.push({ label: lbl.value.trim(), done: !!(chk && chk.checked) });
    });
    return out.filter((i) => i.label);
  }

  function addChecklistItem(ul) {
    if (!ul) return;
    const li = document.createElement("li");
    li.className = "crm-sop-cl-item";
    li.innerHTML = `
      <input type="checkbox" class="crm-sop-cl-check" aria-label="Mục mới" />
      <input type="text" class="crm-sop-cl-label" placeholder="Mục kiểm tra…" maxlength="500" autofocus />
      <button type="button" class="crm-sop-cl-del" aria-label="Xoá mục">×</button>`;
    ul.appendChild(li);
    /** @type {HTMLInputElement|null} */ (li.querySelector(".crm-sop-cl-label"))?.focus();
  }

  document.addEventListener("click", (ev) => {
    const t = /** @type {HTMLElement} */ (ev.target);
    if (t.classList.contains("crm-sop-cl-del")) {
      t.closest(".crm-sop-cl-item")?.remove();
    }
  });

  document.getElementById("crm-sop-step-cl-add")?.addEventListener("click", () =>
    addChecklistItem(document.getElementById("crm-sop-step-checklist")),
  );
  document.getElementById("crm-sop-task-cl-add")?.addEventListener("click", () =>
    addChecklistItem(document.getElementById("crm-sop-task-checklist")),
  );

  // ── TEMPLATE list ─────────────────────────────────────────────────────────

  async function loadTemplates() {
    const incl = document.getElementById("crm-sop-tpl-inactive-toggle");
    const qs = incl instanceof HTMLInputElement && incl.checked ? "?include_inactive=1" : "";
    showMsg(document.getElementById("crm-sop-tpl-msg"), "");
    const container = document.getElementById("crm-sop-tpl-list");
    if (!container) return;
    container.innerHTML = '<p class="muted crm-sop-loading">Đang tải…</p>';
    try {
      const data = await reqJson(`/api/crm/sop/templates${qs}`);
      cachedTemplates = data.templates || [];
      renderTemplateList(container, cachedTemplates);
      document.getElementById("crm-sop-count-tpl").textContent = String(cachedTemplates.filter(t => t.active).length);
    } catch (e) {
      showMsg(document.getElementById("crm-sop-tpl-msg"), e instanceof Error ? e.message : "Lỗi", false);
      container.innerHTML = "";
    }
  }

  /** @param {HTMLElement} container @param {Array<Record<string,any>>} templates */
  function renderTemplateList(container, templates) {
    if (!templates.length) {
      container.innerHTML = '<p class="muted" style="padding:1rem">Chưa có playbook nào. Nhấn <strong>Tạo playbook mới</strong> để bắt đầu.</p>';
      return;
    }
    container.innerHTML = templates.map((t) => {
      const inactive = Number(t.active) === 0;
      const ch = campaign_channel_labels[t.channel] || t.channel || "";
      return `
        <div class="crm-sop-tpl-row ${inactive ? "crm-sop-tpl-row--off" : ""}" data-tpl-id="${escAttr(String(t.id))}">
          <div class="crm-sop-tpl-header">
            <button type="button" class="crm-sop-tpl-expand" aria-expanded="false" data-tpl-expand="${escAttr(String(t.id))}"
              aria-controls="crm-sop-tpl-body-${escAttr(String(t.id))}">
              <span class="crm-sop-tpl-expand-icon" aria-hidden="true">▶</span>
              <span class="crm-sop-tpl-name">${esc(t.name)}${inactive ? ' <span class="crm-staff-pill is-off">Tắt</span>' : ""}</span>
            </button>
            <span class="crm-chip-mini">${esc(ch)}</span>
            ${t.code ? `<code class="crm-sop-code">${esc(t.code)}</code>` : ""}
            <div class="crm-sop-tpl-actions">
              <button type="button" class="btn-secondary crm-hub-action-btn crm-sop-tpl-edit" data-id="${escAttr(String(t.id))}">Sửa</button>
              <button type="button" class="btn-secondary crm-hub-action-btn crm-sop-tpl-add-step" data-id="${escAttr(String(t.id))}">+ Bước</button>
              <button type="button" class="btn crm-hub-action-btn crm-sop-tpl-launch" data-id="${escAttr(String(t.id))}" data-name="${escAttr(String(t.name))}">Khởi chạy</button>
            </div>
          </div>
          ${t.description ? `<p class="crm-sop-tpl-desc muted">${esc(t.description)}</p>` : ""}
          <div class="crm-sop-tpl-body" id="crm-sop-tpl-body-${escAttr(String(t.id))}" hidden>
            <p class="muted crm-sop-loading" style="padding:.5rem 0">Đang tải bước…</p>
          </div>
        </div>`;
    }).join("");
  }

  document.getElementById("crm-sop-tpl-list")?.addEventListener("click", async (ev) => {
    const t = /** @type {HTMLElement} */ (ev.target);

    const expandBtn = t.closest("[data-tpl-expand]");
    if (expandBtn instanceof HTMLElement) {
      const tid = expandBtn.getAttribute("data-tpl-expand");
      if (tid) await toggleTemplateExpand(parseInt(tid));
      return;
    }

    const editBtn = t.closest(".crm-sop-tpl-edit");
    if (editBtn instanceof HTMLElement) {
      const id = editBtn.getAttribute("data-id");
      if (id) openEditTemplate(parseInt(id));
      return;
    }

    const addStepBtn = t.closest(".crm-sop-tpl-add-step");
    if (addStepBtn instanceof HTMLElement) {
      const id = addStepBtn.getAttribute("data-id");
      if (id) openAddStep(parseInt(id));
      return;
    }

    const launchBtn = t.closest(".crm-sop-tpl-launch");
    if (launchBtn instanceof HTMLElement) {
      const id = launchBtn.getAttribute("data-id");
      if (id) openLaunch(parseInt(id));
      return;
    }

    const editStepBtn = t.closest(".crm-sop-step-edit");
    if (editStepBtn instanceof HTMLElement) {
      const id = editStepBtn.getAttribute("data-step-id");
      const tid = editStepBtn.getAttribute("data-tpl-id");
      if (id && tid) openEditStep(parseInt(id), parseInt(tid));
      return;
    }

    const delStepBtn = t.closest(".crm-sop-step-del");
    if (delStepBtn instanceof HTMLElement) {
      const id = delStepBtn.getAttribute("data-step-id");
      const tid = delStepBtn.getAttribute("data-tpl-id");
      if (id && tid && window.confirm("Xoá bước này?")) {
        try {
          await reqJson(`/api/crm/sop/steps/${encodeURIComponent(id)}`, { method: "DELETE" });
          await loadStepBody(parseInt(tid));
        } catch (e) {
          alert(e instanceof Error ? e.message : "Lỗi");
        }
      }
    }

    const moveBtn = t.closest(".crm-sop-step-move");
    if (moveBtn instanceof HTMLElement) {
      const dir = moveBtn.getAttribute("data-dir");
      const tid = parseInt(moveBtn.getAttribute("data-tpl-id") || "0");
      const sid = parseInt(moveBtn.getAttribute("data-step-id") || "0");
      if (dir && tid && sid) await moveStep(tid, sid, dir);
    }
  });

  async function toggleTemplateExpand(tid) {
    const body = document.getElementById(`crm-sop-tpl-body-${tid}`);
    const btn = document.querySelector(`[data-tpl-expand="${tid}"]`);
    if (!body) return;
    const isOpen = !body.hidden;
    if (isOpen) {
      body.hidden = true;
      if (btn) { btn.setAttribute("aria-expanded", "false"); btn.querySelector(".crm-sop-tpl-expand-icon").textContent = "▶"; }
      return;
    }
    body.hidden = false;
    if (btn) { btn.setAttribute("aria-expanded", "true"); btn.querySelector(".crm-sop-tpl-expand-icon").textContent = "▼"; }
    await loadStepBody(tid);
  }

  async function loadStepBody(tid) {
    const body = document.getElementById(`crm-sop-tpl-body-${tid}`);
    if (!body || body.hidden) return;
    body.innerHTML = '<p class="muted crm-sop-loading" style="padding:.5rem 0">Đang tải bước…</p>';
    try {
      const d = await reqJson(`/api/crm/sop/templates/${tid}`);
      const steps = d.steps || [];
      if (!steps.length) {
        body.innerHTML = '<p class="muted" style="padding:.5rem 0">Chưa có bước nào — nhấn <strong>+ Bước</strong> để thêm.</p>';
        return;
      }
      body.innerHTML = `
        <ol class="crm-sop-step-list">
          ${steps.map((s, i) => stepRowHtml(s, tid, i, steps.length)).join("")}
        </ol>`;
    } catch (e) {
      body.innerHTML = `<p class="muted is-error" style="padding:.5rem 0">${esc(e instanceof Error ? e.message : "Lỗi")}</p>`;
    }
  }

  /** @param {Record<string,any>} s @param {number} tid @param {number} i @param {number} total */
  function stepRowHtml(s, tid, i, total) {
    const role = step_role_labels[s.role] || s.role || "";
    const req = s.required ? '<span class="crm-sop-step-req" title="Bắt buộc">*</span>' : "";
    const cl = s.checklist_json ? (() => { try { return JSON.parse(s.checklist_json); } catch { return []; } })() : [];
    const clHint = cl.length ? `<span class="crm-sop-cl-badge">${cl.length} checklist</span>` : "";
    return `
      <li class="crm-sop-step-item" data-step-id="${escAttr(String(s.id))}">
        <div class="crm-sop-step-num">${i + 1}</div>
        <div class="crm-sop-step-content">
          <p class="crm-sop-step-title">${req}${esc(s.title)}</p>
          <p class="crm-sop-step-meta muted">
            <span title="Từ ngày bắt đầu + ${s.offset_days} ngày">D+${s.offset_days}d</span>
            · <span>${s.duration_days}d</span>
            · <span>${esc(role)}</span>
            ${clHint}
          </p>
          ${s.description ? `<p class="crm-sop-step-desc muted">${esc(s.description)}</p>` : ""}
        </div>
        <div class="crm-sop-step-actions">
          <button type="button" class="crm-sop-step-move crm-hub-action-btn btn-secondary"
            data-dir="up" data-tpl-id="${tid}" data-step-id="${s.id}" ${i === 0 ? "disabled" : ""} aria-label="Lên">↑</button>
          <button type="button" class="crm-sop-step-move crm-hub-action-btn btn-secondary"
            data-dir="down" data-tpl-id="${tid}" data-step-id="${s.id}" ${i === total - 1 ? "disabled" : ""} aria-label="Xuống">↓</button>
          <button type="button" class="crm-sop-step-edit crm-hub-action-btn btn-secondary"
            data-step-id="${s.id}" data-tpl-id="${tid}">Sửa</button>
          <button type="button" class="crm-sop-step-del crm-hub-action-btn btn-secondary"
            data-step-id="${s.id}" data-tpl-id="${tid}">Xoá</button>
        </div>
      </li>`;
  }

  async function moveStep(tid, sid, dir) {
    try {
      const d = await reqJson(`/api/crm/sop/templates/${tid}`);
      const steps = d.steps || [];
      const idx = steps.findIndex((s) => s.id === sid);
      if (idx < 0) return;
      const swapIdx = dir === "up" ? idx - 1 : idx + 1;
      if (swapIdx < 0 || swapIdx >= steps.length) return;
      [steps[idx], steps[swapIdx]] = [steps[swapIdx], steps[idx]];
      await reqJson(`/api/crm/sop/templates/${tid}/steps/reorder`, {
        method: "POST",
        body: JSON.stringify({ order: steps.map((s) => s.id) }),
      });
      await loadStepBody(tid);
    } catch (e) {
      alert(e instanceof Error ? e.message : "Lỗi");
    }
  }

  // ── TEMPLATE MODAL ─────────────────────────────────────────────────────────

  const modalTpl = document.getElementById("crm-sop-modal-tpl");
  const formTpl = /** @type {HTMLFormElement|null} */ (document.getElementById("crm-sop-form-tpl"));

  document.getElementById("crm-sop-tpl-add-btn")?.addEventListener("click", () => {
    if (!modalTpl || !formTpl) return;
    showMsg(document.getElementById("crm-sop-tpl-err"), "");
    formTpl.reset();
    /** @type {HTMLInputElement|null} */ (formTpl.querySelector("input[name='id']")).value = "";
    /** @type {HTMLInputElement|null} */ (formTpl.querySelector("input[name='active']")).checked = true;
    openModal(modalTpl);
    formTpl.querySelector("input[name='name']")?.focus();
  });

  function openEditTemplate(id) {
    const tpl = cachedTemplates.find((t) => t.id === id);
    if (!tpl || !modalTpl || !formTpl) return;
    showMsg(document.getElementById("crm-sop-tpl-err"), "");
    /** @type {HTMLInputElement|null} */ (formTpl.querySelector("input[name='id']")).value = String(id);
    /** @type {HTMLInputElement|null} */ (formTpl.querySelector("input[name='name']")).value = String(tpl.name || "");
    /** @type {HTMLInputElement|null} */ (formTpl.querySelector("input[name='code']")).value = String(tpl.code || "");
    /** @type {HTMLSelectElement|null} */ (formTpl.querySelector("select[name='channel']")).value = String(tpl.channel || "other");
    /** @type {HTMLTextAreaElement|null} */ (formTpl.querySelector("textarea[name='description']")).value = String(tpl.description || "");
    /** @type {HTMLTextAreaElement|null} */ (formTpl.querySelector("textarea[name='notes']")).value = String(tpl.notes || "");
    /** @type {HTMLInputElement|null} */ (formTpl.querySelector("input[name='active']")).checked = Number(tpl.active) !== 0;
    openModal(modalTpl);
  }

  formTpl?.addEventListener("submit", async (ev) => {
    ev.preventDefault();
    showMsg(document.getElementById("crm-sop-tpl-err"), "");
    const fd = new FormData(formTpl);
    const idStr = fd.get("id") ? String(fd.get("id")).trim() : "";
    const payload = {
      name: fd.get("name") || "",
      code: fd.get("code") || "",
      channel: fd.get("channel") || "other",
      description: fd.get("description") || "",
      notes: fd.get("notes") || "",
      active: !!(formTpl.querySelector("input[name='active']")) &&
        /** @type {HTMLInputElement} */ (formTpl.querySelector("input[name='active']")).checked,
    };
    try {
      if (idStr) {
        await reqJson(`/api/crm/sop/templates/${encodeURIComponent(idStr)}`, {
          method: "PATCH", body: JSON.stringify(payload),
        });
      } else {
        await reqJson("/api/crm/sop/templates", { method: "POST", body: JSON.stringify(payload) });
      }
      if (modalTpl) closeModal(modalTpl);
      await loadTemplates();
    } catch (e) {
      showMsg(document.getElementById("crm-sop-tpl-err"), e instanceof Error ? e.message : "Lỗi", false);
    }
  });

  document.getElementById("crm-sop-tpl-inactive-toggle")?.addEventListener("change", () => loadTemplates().catch(() => {}));

  // ── STEP MODAL ─────────────────────────────────────────────────────────────

  const modalStep = document.getElementById("crm-sop-modal-step");
  const formStep = /** @type {HTMLFormElement|null} */ (document.getElementById("crm-sop-form-step"));
  const stepChecklist = /** @type {HTMLUListElement|null} */ (document.getElementById("crm-sop-step-checklist"));

  function openAddStep(tplId) {
    if (!modalStep || !formStep) return;
    showMsg(document.getElementById("crm-sop-step-err"), "");
    formStep.reset();
    /** @type {HTMLInputElement|null} */ (formStep.querySelector("input[name='id']")).value = "";
    /** @type {HTMLInputElement|null} */ (formStep.querySelector("input[name='template_id']")).value = String(tplId);
    /** @type {HTMLInputElement|null} */ (formStep.querySelector("input[name='required']")).checked = true;
    document.getElementById("crm-sop-step-kicker").textContent = `Template #${tplId}`;
    renderChecklist(stepChecklist, []);
    openModal(modalStep);
    formStep.querySelector("input[name='title']")?.focus();
  }

  async function openEditStep(sid, tid) {
    if (!modalStep || !formStep) return;
    showMsg(document.getElementById("crm-sop-step-err"), "");
    try {
      const d = await reqJson(`/api/crm/sop/templates/${tid}`);
      const step = (d.steps || []).find((s) => s.id === sid);
      if (!step) throw new Error("Không tìm thấy bước");
      /** @type {HTMLInputElement|null} */ (formStep.querySelector("input[name='id']")).value = String(sid);
      /** @type {HTMLInputElement|null} */ (formStep.querySelector("input[name='template_id']")).value = String(tid);
      /** @type {HTMLInputElement|null} */ (formStep.querySelector("input[name='title']")).value = String(step.title || "");
      /** @type {HTMLTextAreaElement|null} */ (formStep.querySelector("textarea[name='description']")).value = String(step.description || "");
      /** @type {HTMLInputElement|null} */ (formStep.querySelector("input[name='offset_days']")).value = String(step.offset_days ?? 0);
      /** @type {HTMLInputElement|null} */ (formStep.querySelector("input[name='duration_days']")).value = String(step.duration_days ?? 1);
      /** @type {HTMLSelectElement|null} */ (formStep.querySelector("select[name='role']")).value = String(step.role || "any");
      /** @type {HTMLInputElement|null} */ (formStep.querySelector("input[name='required']")).checked = step.required !== 0;
      let cl = [];
      try { cl = JSON.parse(step.checklist_json || "[]"); } catch { cl = []; }
      renderChecklist(stepChecklist, cl);
      document.getElementById("crm-sop-step-kicker").textContent = `Bước trong Template #${tid}`;
      openModal(modalStep);
    } catch (e) {
      alert(e instanceof Error ? e.message : "Lỗi");
    }
  }

  formStep?.addEventListener("submit", async (ev) => {
    ev.preventDefault();
    showMsg(document.getElementById("crm-sop-step-err"), "");
    const fd = new FormData(formStep);
    const sid = fd.get("id") ? String(fd.get("id")).trim() : "";
    const tid = String(fd.get("template_id") || "").trim();
    const checklist = collectChecklist(stepChecklist);
    const payload = {
      title: fd.get("title") || "",
      description: fd.get("description") || "",
      offset_days: parseInt(String(fd.get("offset_days") || "0"), 10) || 0,
      duration_days: Math.max(1, parseInt(String(fd.get("duration_days") || "1"), 10) || 1),
      role: fd.get("role") || "any",
      required: !!(formStep.querySelector("input[name='required']")) &&
        /** @type {HTMLInputElement} */ (formStep.querySelector("input[name='required']")).checked,
      checklist_json: checklist,
    };
    try {
      if (sid) {
        await reqJson(`/api/crm/sop/steps/${encodeURIComponent(sid)}`, { method: "PATCH", body: JSON.stringify(payload) });
      } else if (tid) {
        await reqJson(`/api/crm/sop/templates/${encodeURIComponent(tid)}/steps`, { method: "POST", body: JSON.stringify(payload) });
      } else throw new Error("Thiếu template_id");
      if (modalStep) closeModal(modalStep);
      if (tid) await loadStepBody(parseInt(tid));
    } catch (e) {
      showMsg(document.getElementById("crm-sop-step-err"), e instanceof Error ? e.message : "Lỗi", false);
    }
  });

  // ── LAUNCH MODAL ──────────────────────────────────────────────────────────

  const modalLaunch = document.getElementById("crm-sop-modal-launch");
  const formLaunch = /** @type {HTMLFormElement|null} */ (document.getElementById("crm-sop-form-launch"));

  document.getElementById("crm-sop-launch-btn")?.addEventListener("click", () => openLaunch());
  document.getElementById("crm-sop-run-list")?.addEventListener("click", async (ev) => {
    const t = /** @type {HTMLElement} */ (ev.target);
    const lb = t.closest(".crm-sop-run-launch-btn");
    if (lb instanceof HTMLElement) {
      const tid = parseInt(lb.getAttribute("data-tpl-id") || "0");
      openLaunch(tid || undefined);
    }
  });

  async function openLaunch(presetTplId) {
    if (!modalLaunch || !formLaunch) return;
    showMsg(document.getElementById("crm-sop-launch-err"), "");
    formLaunch.reset();
    /** @type {HTMLInputElement|null} */ (formLaunch.querySelector("input[name='id']")).value = "";
    /** @type {HTMLInputElement|null} */ (formLaunch.querySelector("input[name='start_date']")).value = todayIso();
    /** @type {HTMLSelectElement|null} */ (formLaunch.querySelector("select[name='status']")).value = "active";

    await Promise.all([loadCampaignOptions(), loadTemplates().catch(() => {})]);
    populateCampaignSelect(document.getElementById("crm-sop-launch-campaign"));
    populateTemplateSelect(document.getElementById("crm-sop-launch-template"));

    if (presetTplId) {
      const sel = /** @type {HTMLSelectElement|null} */ (document.getElementById("crm-sop-launch-template"));
      if (sel) sel.value = String(presetTplId);
      await updateLaunchPreview(presetTplId);
    } else {
      const prev = document.getElementById("crm-sop-launch-preview");
      if (prev) prev.hidden = true;
    }

    openModal(modalLaunch);
    formLaunch.querySelector("input[name='name']")?.focus();
  }

  document.getElementById("crm-sop-launch-template")?.addEventListener("change", async (ev) => {
    const tid = parseInt(/** @type {HTMLSelectElement} */ (ev.target).value || "0");
    if (tid) await updateLaunchPreview(tid);
    else {
      const prev = document.getElementById("crm-sop-launch-preview");
      if (prev) prev.hidden = true;
    }
  });

  async function updateLaunchPreview(tid) {
    const prevEl = document.getElementById("crm-sop-launch-preview");
    const listEl = document.getElementById("crm-sop-launch-preview-list");
    if (!prevEl || !listEl) return;
    try {
      const d = await reqJson(`/api/crm/sop/templates/${tid}`);
      const steps = d.steps || [];
      const startRaw = /** @type {HTMLInputElement|null} */ (formLaunch?.querySelector("input[name='start_date']"))?.value || todayIso();
      if (!steps.length) {
        prevEl.hidden = true;
        return;
      }
      listEl.innerHTML = steps.map((s) => {
        const role = step_role_labels[s.role] || s.role || "";
        return `<li class="crm-sop-preview-item">
          <span class="crm-sop-preview-pos">D+${s.offset_days}d</span>
          <span class="crm-sop-preview-title">${esc(s.title)}</span>
          <span class="crm-sop-preview-meta muted">${esc(role)} · ${s.duration_days}d</span>
        </li>`;
      }).join("");
      prevEl.hidden = false;
    } catch { prevEl.hidden = true; }
  }

  formLaunch?.querySelector("input[name='start_date']")?.addEventListener("change", () => {
    const tid = parseInt(/** @type {HTMLSelectElement|null} */ (document.getElementById("crm-sop-launch-template"))?.value || "0");
    if (tid) updateLaunchPreview(tid).catch(() => {});
  });

  formLaunch?.addEventListener("submit", async (ev) => {
    ev.preventDefault();
    showMsg(document.getElementById("crm-sop-launch-err"), "");
    const fd = new FormData(formLaunch);
    const idStr = fd.get("id") ? String(fd.get("id")).trim() : "";

    /** @type {Record<string, any>} */
    const payload = {
      name: fd.get("name") || "",
      start_date: fd.get("start_date") || todayIso(),
      status: fd.get("status") || "active",
      notes: fd.get("notes") || "",
      generate_tasks: true,
    };
    const tplRaw = fd.get("template_id");
    const tplNum = tplRaw ? parseInt(String(tplRaw)) : 0;
    if (tplNum > 0) payload.template_id = tplNum;
    const campRaw = fd.get("campaign_id");
    const campNum = campRaw ? parseInt(String(campRaw)) : 0;
    if (campNum > 0) payload.campaign_id = campNum;

    try {
      if (idStr) {
        await reqJson(`/api/crm/sop/runs/${encodeURIComponent(idStr)}`, { method: "PATCH", body: JSON.stringify(payload) });
      } else {
        await reqJson("/api/crm/sop/runs", { method: "POST", body: JSON.stringify(payload) });
      }
      if (modalLaunch) closeModal(modalLaunch);
      await loadRuns();
      await updateSummary();
    } catch (e) {
      showMsg(document.getElementById("crm-sop-launch-err"), e instanceof Error ? e.message : "Lỗi", false);
    }
  });

  // ── RUNS list ─────────────────────────────────────────────────────────────

  async function loadRuns() {
    const filterSel = /** @type {HTMLSelectElement|null} */ (document.getElementById("crm-sop-run-filter"));
    const st = filterSel ? filterSel.value : "active";
    showMsg(document.getElementById("crm-sop-run-msg"), "");
    const container = document.getElementById("crm-sop-run-list");
    if (!container) return;
    container.innerHTML = '<p class="muted crm-sop-loading">Đang tải SOP Runs…</p>';
    try {
      const d = await reqJson(`/api/crm/sop/runs?status=${encodeURIComponent(st)}`);
      const runs = d.runs || [];
      renderRunList(container, runs);
      const activeCount = runs.filter(r => r.status === "active").length;
      const ov = document.getElementById("crm-sop-count-active");
      if (ov) ov.textContent = String(activeCount);
    } catch (e) {
      showMsg(document.getElementById("crm-sop-run-msg"), e instanceof Error ? e.message : "Lỗi", false);
      container.innerHTML = "";
    }
  }

  document.getElementById("crm-sop-run-filter")?.addEventListener("change", () => loadRuns().catch(() => {}));

  /** @param {HTMLElement} container @param {Array<Record<string,any>>} runs */
  function renderRunList(container, runs) {
    if (!runs.length) {
      container.innerHTML = '<div class="panel muted" style="padding:1.2rem">Không có SOP Run nào trong trạng thái này.</div>';
      return;
    }
    container.innerHTML = runs.map((r) => runCardHtml(r)).join("");
    runs.forEach((r) => {
      if (expandedRuns.has(r.id)) {
        const tasks = cachedRunTasks[r.id];
        if (tasks) renderTaskList(r.id, tasks);
        else loadRunTasks(r.id).catch(() => {});
      }
    });
  }

  /** @param {Record<string,any>} r */
  function runCardHtml(r) {
    const stats = r.stats || {};
    const done = stats.done || 0;
    const total = stats.total || 0;
    const overdue = stats.overdue || 0;
    const inProg = stats.in_progress || 0;
    const ring = progressRingHtml(done, total);
    const statusLabel = run_status_labels[r.status] || r.status || "";
    const runDate = r.start_date ? fmtDate(r.start_date) : "—";
    const expanded = expandedRuns.has(r.id);
    return `
      <div class="crm-sop-run-card panel" data-run-id="${escAttr(String(r.id))}">
        <div class="crm-sop-run-card-top">
          ${ring}
          <div class="crm-sop-run-card-info">
            <p class="crm-sop-run-name">
              <button type="button" class="crm-sop-run-expand crm-sop-run-toggle" data-run-id="${escAttr(String(r.id))}">
                ${esc(r.name)}
              </button>
            </p>
            <p class="crm-sop-run-meta muted">
              <span class="crm-staff-pill is-on">${esc(statusLabel)}</span>
              ${r.template_name ? `· ${esc(r.template_name)}` : ""}
              ${r.campaign_name ? `· <span title="Chiến dịch">${esc(r.campaign_name)}</span>` : ""}
              · Bắt đầu: ${esc(runDate)}
            </p>
            <p class="crm-sop-run-progress-text muted">
              ${done}/${total} hoàn thành
              ${overdue ? `· <strong class="is-overdue-text">${overdue} quá hạn</strong>` : ""}
              ${inProg ? `· ${inProg} đang thực hiện` : ""}
            </p>
          </div>
          <div class="crm-sop-run-card-actions">
            <button type="button" class="btn-secondary crm-hub-action-btn crm-sop-run-edit-btn" data-id="${escAttr(String(r.id))}">Sửa</button>
            <button type="button" class="btn-secondary crm-hub-action-btn crm-sop-run-add-task-btn" data-id="${escAttr(String(r.id))}">+ Task</button>
            <button type="button" class="btn-secondary crm-hub-action-btn crm-sop-run-toggle" data-run-id="${escAttr(String(r.id))}">
              ${expanded ? "Thu gọn ▲" : "Xem task ▼"}
            </button>
          </div>
        </div>
        <div class="crm-sop-run-tasks-wrap" id="crm-sop-run-tasks-${escAttr(String(r.id))}" ${expanded ? "" : "hidden"}></div>
      </div>`;
  }

  document.getElementById("crm-sop-run-list")?.addEventListener("click", async (ev) => {
    const t = /** @type {HTMLElement} */ (ev.target);
    const toggleBtn = t.closest(".crm-sop-run-toggle");
    if (toggleBtn instanceof HTMLElement) {
      const rid = parseInt(toggleBtn.getAttribute("data-run-id") || "0");
      if (rid) await toggleRunExpand(rid);
      return;
    }
    const editBtn = t.closest(".crm-sop-run-edit-btn");
    if (editBtn instanceof HTMLElement) {
      const id = editBtn.getAttribute("data-id");
      if (id) openEditRun(parseInt(id));
      return;
    }
    const addTaskBtn = t.closest(".crm-sop-run-add-task-btn");
    if (addTaskBtn instanceof HTMLElement) {
      const id = addTaskBtn.getAttribute("data-id");
      if (id) openAddTask(parseInt(id));
      return;
    }
    const taskBtn = t.closest(".crm-sop-task-item-btn");
    if (taskBtn instanceof HTMLElement) {
      const tid = taskBtn.getAttribute("data-task-id");
      const rid = taskBtn.getAttribute("data-run-id");
      if (tid && rid) openEditTask(parseInt(tid), parseInt(rid));
      return;
    }
    const statusBtn = t.closest(".crm-sop-task-quick-status");
    if (statusBtn instanceof HTMLElement) {
      const tid = parseInt(statusBtn.getAttribute("data-task-id") || "0");
      const st = statusBtn.getAttribute("data-status") || "done";
      if (tid) await quickUpdateTaskStatus(tid, st);
    }
  });

  async function toggleRunExpand(rid) {
    const wrap = document.getElementById(`crm-sop-run-tasks-${rid}`);
    if (!wrap) return;
    const isOpen = !wrap.hidden;
    if (isOpen) {
      wrap.hidden = true;
      expandedRuns.delete(rid);
      const btn = document.querySelector(`.crm-sop-run-toggle[data-run-id="${rid}"]`);
      if (btn) btn.textContent = "Xem task ▼";
      return;
    }
    wrap.hidden = false;
    expandedRuns.add(rid);
    const btn = document.querySelector(`.crm-sop-run-toggle[data-run-id="${rid}"]`);
    if (btn) btn.textContent = "Thu gọn ▲";
    await loadRunTasks(rid);
  }

  async function loadRunTasks(rid) {
    const wrap = document.getElementById(`crm-sop-run-tasks-${rid}`);
    if (!wrap || wrap.hidden) return;
    wrap.innerHTML = '<p class="muted crm-sop-loading">Đang tải task…</p>';
    try {
      const d = await reqJson(`/api/crm/sop/runs/${rid}/tasks`);
      cachedRunTasks[rid] = d.tasks || [];
      renderTaskList(rid, cachedRunTasks[rid]);
    } catch (e) {
      wrap.innerHTML = `<p class="muted is-error">${esc(e instanceof Error ? e.message : "Lỗi")}</p>`;
    }
  }

  /** @param {number} rid @param {Array<Record<string,any>>} tasks */
  function renderTaskList(rid, tasks) {
    const wrap = document.getElementById(`crm-sop-run-tasks-${rid}`);
    if (!wrap) return;
    const today = todayIso();
    if (!tasks.length) {
      wrap.innerHTML = '<p class="muted crm-sop-loading">Chưa có task nào — nhấn <strong>+ Task</strong> để thêm thủ công.</p>';
      return;
    }
    const grouped = {};
    task_statuses.forEach((s) => { grouped[s] = []; });
    tasks.forEach((t) => { (grouped[t.status] || (grouped["todo"] = grouped["todo"] || [])).push(t); });
    wrap.innerHTML = `
      <div class="crm-sop-kanban">
        ${task_statuses.map((st) => {
          const col = grouped[st] || [];
          return `
            <div class="crm-sop-kcol" data-st="${escAttr(st)}">
              <header class="crm-sop-kcol-head">
                <span>${esc(task_status_labels[st] || st)}</span>
                <span class="crm-col-count">${col.length}</span>
              </header>
              <div class="crm-sop-kcol-body">
                ${col.map((t) => taskCardHtml(t, today, rid)).join("") || '<p class="muted crm-sop-kcol-empty">Trống</p>'}
              </div>
            </div>`;
        }).join("")}
      </div>`;
  }

  /** @param {Record<string,any>} t @param {string} today @param {number} rid */
  function taskCardHtml(t, today, rid) {
    const overdue = t.status !== "done" && t.status !== "skipped" && t.due_date && t.due_date < today;
    const dueText = t.due_date ? fmtDate(t.due_date) : "—";
    const role = step_role_labels[t.role] || t.role || "";
    const staff = t.assigned_staff_name ? `<span class="crm-chip-mini crm-chip-mini--assign">${esc(t.assigned_staff_name)}</span>` : "";
    let cl = [];
    try { cl = JSON.parse(t.checklist_json || "[]"); } catch {}
    const clDone = cl.filter((i) => i.done).length;
    const clTotal = cl.length;
    const clBadge = clTotal ? `<span class="crm-sop-cl-badge">${clDone}/${clTotal}</span>` : "";
    const nextStatus = t.status === "todo" ? "in_progress" : t.status === "in_progress" ? "done" : null;
    return `
      <article class="crm-sop-task-card ${overdue ? "is-overdue" : ""}" data-task-id="${escAttr(String(t.id))}">
        <p class="crm-sop-task-title">
          <button type="button" class="crm-sop-task-item-btn" data-task-id="${escAttr(String(t.id))}" data-run-id="${escAttr(String(rid))}">${esc(t.title)}</button>
        </p>
        <div class="crm-sop-task-meta muted">
          <span>${esc(role)}</span>
          · <span ${overdue ? 'class="is-overdue-text"' : ""}>${dueText}</span>
          ${staff}
          ${clBadge}
        </div>
        ${nextStatus ? `
          <button type="button" class="crm-sop-task-quick-status btn-secondary crm-hub-action-btn"
            data-task-id="${escAttr(String(t.id))}" data-status="${escAttr(nextStatus)}">
            ${nextStatus === "in_progress" ? "→ Đang làm" : "✓ Xong"}
          </button>` : ""}
      </article>`;
  }

  async function quickUpdateTaskStatus(tid, status) {
    try {
      const d = await reqJson(`/api/crm/sop/run_tasks/${tid}`, {
        method: "PATCH", body: JSON.stringify({ status }),
      });
      const rid = d.run_id;
      if (rid) {
        await loadRunTasks(rid);
        await updateSummary();
        await reloadRunCard(rid);
      }
    } catch (e) {
      alert(e instanceof Error ? e.message : "Lỗi");
    }
  }

  async function reloadRunCard(rid) {
    try {
      const d = await reqJson(`/api/crm/sop/runs?status=all`);
      const run = (d.runs || []).find((r) => r.id === rid);
      if (!run) return;
      const card = document.querySelector(`.crm-sop-run-card[data-run-id="${rid}"]`);
      if (!card) return;
      const newHtml = document.createElement("div");
      newHtml.innerHTML = runCardHtml(run);
      const newCard = newHtml.firstElementChild;
      if (!newCard) return;
      card.replaceWith(newCard);
      if (expandedRuns.has(rid)) {
        const wrap = document.getElementById(`crm-sop-run-tasks-${rid}`);
        if (wrap) { wrap.hidden = false; await loadRunTasks(rid); }
      }
    } catch {}
  }

  // ── RUN EDIT MODAL ─────────────────────────────────────────────────────────

  const modalRun = document.getElementById("crm-sop-modal-run");
  const formRun = /** @type {HTMLFormElement|null} */ (document.getElementById("crm-sop-form-run"));

  function openEditRun(rid) {
    if (!modalRun || !formRun) return;
    showMsg(document.getElementById("crm-sop-run-err"), "");
    reqJson(`/api/crm/sop/runs?status=all`).then((d) => {
      const run = (d.runs || []).find((r) => r.id === rid);
      if (!run) return;
      /** @type {HTMLInputElement|null} */ (formRun.querySelector("input[name='id']")).value = String(rid);
      /** @type {HTMLInputElement|null} */ (formRun.querySelector("input[name='name']")).value = String(run.name || "");
      /** @type {HTMLInputElement|null} */ (formRun.querySelector("input[name='start_date']")).value = String((run.start_date || "").slice(0, 10));
      /** @type {HTMLSelectElement|null} */ (formRun.querySelector("select[name='status']")).value = String(run.status || "active");
      /** @type {HTMLTextAreaElement|null} */ (formRun.querySelector("textarea[name='notes']")).value = String(run.notes || "");
      openModal(modalRun);
    }).catch(() => {});
  }

  formRun?.addEventListener("submit", async (ev) => {
    ev.preventDefault();
    showMsg(document.getElementById("crm-sop-run-err"), "");
    const fd = new FormData(formRun);
    const id = fd.get("id") ? String(fd.get("id")).trim() : "";
    if (!id) return;
    try {
      await reqJson(`/api/crm/sop/runs/${encodeURIComponent(id)}`, {
        method: "PATCH",
        body: JSON.stringify({
          name: fd.get("name") || "",
          start_date: fd.get("start_date") || "",
          status: fd.get("status") || "active",
          notes: fd.get("notes") || "",
        }),
      });
      if (modalRun) closeModal(modalRun);
      await loadRuns();
      await updateSummary();
    } catch (e) {
      showMsg(document.getElementById("crm-sop-run-err"), e instanceof Error ? e.message : "Lỗi", false);
    }
  });

  // ── TASK MODAL ─────────────────────────────────────────────────────────────

  const modalTask = document.getElementById("crm-sop-modal-task");
  const formTask = /** @type {HTMLFormElement|null} */ (document.getElementById("crm-sop-form-task"));
  const taskChecklist = /** @type {HTMLUListElement|null} */ (document.getElementById("crm-sop-task-checklist"));

  function openAddTask(rid) {
    if (!modalTask || !formTask) return;
    showMsg(document.getElementById("crm-sop-task-err"), "");
    formTask.reset();
    /** @type {HTMLInputElement|null} */ (formTask.querySelector("input[name='id']")).value = "";
    /** @type {HTMLInputElement|null} */ (formTask.querySelector("input[name='run_id']")).value = String(rid);
    /** @type {HTMLSelectElement|null} */ (formTask.querySelector("select[name='status']")).value = "todo";
    renderChecklist(taskChecklist, []);
    populateStaffSelect(document.getElementById("crm-sop-task-staff"));
    document.getElementById("crm-sop-task-del").hidden = true;
    openModal(modalTask);
    formTask.querySelector("input[name='title']")?.focus();
  }

  async function openEditTask(tid, rid) {
    if (!modalTask || !formTask) return;
    showMsg(document.getElementById("crm-sop-task-err"), "");
    try {
      const d = await reqJson(`/api/crm/sop/runs/${rid}/tasks`);
      const task = (d.tasks || []).find((t) => t.id === tid);
      if (!task) throw new Error("Không tìm thấy task");
      /** @type {HTMLInputElement|null} */ (formTask.querySelector("input[name='id']")).value = String(tid);
      /** @type {HTMLInputElement|null} */ (formTask.querySelector("input[name='run_id']")).value = String(rid);
      /** @type {HTMLInputElement|null} */ (formTask.querySelector("input[name='title']")).value = String(task.title || "");
      /** @type {HTMLTextAreaElement|null} */ (formTask.querySelector("textarea[name='description']")).value = String(task.description || "");
      /** @type {HTMLInputElement|null} */ (formTask.querySelector("input[name='due_date']")).value = String((task.due_date || "").slice(0, 10));
      /** @type {HTMLSelectElement|null} */ (formTask.querySelector("select[name='role']")).value = String(task.role || "any");
      /** @type {HTMLSelectElement|null} */ (formTask.querySelector("select[name='status']")).value = String(task.status || "todo");
      /** @type {HTMLTextAreaElement|null} */ (formTask.querySelector("textarea[name='notes']")).value = String(task.notes || "");
      populateStaffSelect(document.getElementById("crm-sop-task-staff"), task.assigned_staff_id);
      let cl = [];
      try { cl = JSON.parse(task.checklist_json || "[]"); } catch {}
      renderChecklist(taskChecklist, cl);
      const delBtn = document.getElementById("crm-sop-task-del");
      if (delBtn) { delBtn.hidden = false; delBtn.setAttribute("data-task-id", String(tid)); delBtn.setAttribute("data-run-id", String(rid)); }
      openModal(modalTask);
    } catch (e) {
      alert(e instanceof Error ? e.message : "Lỗi");
    }
  }

  document.getElementById("crm-sop-task-del")?.addEventListener("click", async (ev) => {
    const btn = /** @type {HTMLElement} */ (ev.currentTarget);
    const tid = btn.getAttribute("data-task-id");
    const rid = btn.getAttribute("data-run-id");
    if (!tid || !window.confirm("Xoá task này?")) return;
    try {
      await reqJson(`/api/crm/sop/run_tasks/${encodeURIComponent(tid)}`, { method: "DELETE" });
      if (modalTask) closeModal(modalTask);
      if (rid) { await loadRunTasks(parseInt(rid)); await reloadRunCard(parseInt(rid)); }
      await updateSummary();
    } catch (e) {
      showMsg(document.getElementById("crm-sop-task-err"), e instanceof Error ? e.message : "Lỗi", false);
    }
  });

  formTask?.addEventListener("submit", async (ev) => {
    ev.preventDefault();
    showMsg(document.getElementById("crm-sop-task-err"), "");
    const fd = new FormData(formTask);
    const tid = fd.get("id") ? String(fd.get("id")).trim() : "";
    const rid = fd.get("run_id") ? String(fd.get("run_id")).trim() : "";
    const checklist = collectChecklist(taskChecklist);
    /** @type {Record<string, any>} */
    const payload = {
      title: fd.get("title") || "",
      description: fd.get("description") || "",
      due_date: fd.get("due_date") || "",
      role: fd.get("role") || "any",
      status: fd.get("status") || "todo",
      notes: fd.get("notes") || "",
      checklist_json: checklist,
    };
    const staffRaw = fd.get("assigned_staff_id");
    const sn = staffRaw ? parseInt(String(staffRaw)) : 0;
    if (sn > 0) payload.assigned_staff_id = sn;
    else payload.assigned_staff_id = null;
    try {
      if (tid) {
        await reqJson(`/api/crm/sop/run_tasks/${encodeURIComponent(tid)}`, { method: "PATCH", body: JSON.stringify(payload) });
      } else if (rid) {
        await reqJson(`/api/crm/sop/runs/${encodeURIComponent(rid)}/tasks`, { method: "POST", body: JSON.stringify(payload) });
      } else throw new Error("Thiếu run_id");
      if (modalTask) closeModal(modalTask);
      if (rid) { await loadRunTasks(parseInt(rid)); await reloadRunCard(parseInt(rid)); }
      await updateSummary();
    } catch (e) {
      showMsg(document.getElementById("crm-sop-task-err"), e instanceof Error ? e.message : "Lỗi", false);
    }
  });

  // ── OVERDUE ────────────────────────────────────────────────────────────────

  async function loadOverdue() {
    showMsg(document.getElementById("crm-sop-overdue-msg"), "");
    const tbody = document.getElementById("crm-sop-overdue-tbody");
    if (!tbody) return;
    tbody.innerHTML = '<tr><td colspan="5" class="muted">Đang tải…</td></tr>';
    try {
      const d = await reqJson("/api/crm/sop/overdue_tasks");
      const list = d.overdue || [];
      document.getElementById("crm-sop-count-overdue").textContent = String(list.length);
      tbody.innerHTML = list.length
        ? list.map((t) => `
          <tr>
            <td class="is-overdue-text">${esc(fmtDate(t.due_date))}</td>
            <td>${esc(t.title)}</td>
            <td>${esc(t.run_name || "—")}</td>
            <td>${esc(t.assigned_staff_name || "—")}</td>
            <td>
              <button type="button" class="btn-secondary crm-hub-action-btn crm-sop-overdue-done"
                data-task-id="${escAttr(String(t.id))}" data-run-id="${escAttr(String(t.run_id))}">Đánh dấu xong</button>
            </td>
          </tr>`).join("")
        : '<tr><td colspan="5" class="muted">Không có task quá hạn.</td></tr>';
    } catch (e) {
      showMsg(document.getElementById("crm-sop-overdue-msg"), e instanceof Error ? e.message : "Lỗi", false);
      tbody.innerHTML = "";
    }
  }

  document.getElementById("crm-sop-overdue-tbody")?.addEventListener("click", async (ev) => {
    const btn = /** @type {HTMLElement} */ (ev.target).closest(".crm-sop-overdue-done");
    if (!btn) return;
    const tid = btn.getAttribute("data-task-id");
    if (!tid) return;
    try {
      await reqJson(`/api/crm/sop/run_tasks/${encodeURIComponent(tid)}`, {
        method: "PATCH", body: JSON.stringify({ status: "done" }),
      });
      await loadOverdue();
      await updateSummary();
    } catch (e) {
      alert(e instanceof Error ? e.message : "Lỗi");
    }
  });

  document.getElementById("crm-sop-overdue-refresh")?.addEventListener("click", () => loadOverdue().catch(() => {}));

  // ── SUMMARY ────────────────────────────────────────────────────────────────

  async function updateSummary() {
    try {
      const [od, runs, tpls] = await Promise.all([
        reqJson("/api/crm/sop/overdue_tasks"),
        reqJson("/api/crm/sop/runs?status=active"),
        reqJson("/api/crm/sop/templates"),
      ]);
      const odCount = (od.overdue || []).length;
      const activeRuns = (runs.runs || []).length;
      const tplCount = (tpls.templates || []).length;
      document.getElementById("crm-sop-count-overdue").textContent = String(odCount);
      document.getElementById("crm-sop-count-active").textContent = String(activeRuns);
      document.getElementById("crm-sop-count-tpl").textContent = String(tplCount);
    } catch {}
  }

  // ── BOOT ───────────────────────────────────────────────────────────────────

  loadStaff().catch(() => {});
  updateSummary().catch(() => {});
  switchTab("runs");
})();
