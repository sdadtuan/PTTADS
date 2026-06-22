(function () {
  "use strict";

  window.addEventListener("pageshow", (ev) => {
    if (ev.persisted) window.location.reload();
  });

  const metaEl = document.getElementById("crm-mp-meta");
  /** @type {Record<string, any>} */
  const meta = metaEl ? JSON.parse(metaEl.textContent) : {};
  const plan_status_labels = meta.plan_status_labels || {};
  const plan_priorities = meta.plan_priorities || [];
  const plan_priority_labels = meta.plan_priority_labels || {};
  const ms_statuses = meta.ms_statuses || [];
  const ms_status_labels = meta.ms_status_labels || {};
  const campaign_channels = meta.campaign_channels || [];
  const campaign_channel_labels = meta.campaign_channel_labels || {};
  const strategy_framework_keys = meta.strategy_framework_keys || [];
  const target_market_prof_keys = meta.target_market_prof_keys || [];
  const target_market_steps4_keys = meta.target_market_steps4_keys || [];

  /** @type {Array<Record<string, any>>} */
  let staffCache = [];
  /** @type {Array<Record<string, any>>} */
  let campaignsCache = [];
  /** @type {number | null} */
  let modalPlanId = null;
  /** @type {Array<{ localKey?: string; id?: number; title: string; due_date: string; status: string; notes: string }>} */
  let pendingMilestones = [];
  let milestoneLocalInc = 0;

  /** @param {HTMLElement|null} box @param {string} msg @param {boolean} [ok] */
  function boxMsg(box, msg, ok) {
    if (!box) return;
    if (!msg) {
      box.hidden = true;
      return;
    }
    box.hidden = false;
    box.textContent = msg;
    box.classList.toggle("is-error", !ok);
    box.classList.toggle("is-success", !!ok);
  }

  /** @param {HTMLElement|null} el @param {string} msg */
  function showFormErr(el, msg) {
    if (!el) return;
    if (!msg) {
      el.hidden = true;
      return;
    }
    el.hidden = false;
    el.textContent = msg;
  }

  function esc(s) {
    const d = document.createElement("div");
    d.textContent = s ?? "";
    return d.innerHTML;
  }

  async function reqJson(url, opts = {}) {
    const headers = { Accept: "application/json", ...(opts.headers || {}) };
    const body = opts.body;
    if (body && typeof body === "string") headers["Content-Type"] = "application/json";
    const res = await fetch(url, { credentials: "same-origin", ...opts, headers });
    const ct = res.headers.get("Content-Type") || "";
    let data = {};
    if (ct.includes("application/json")) {
      try {
        data = await res.json();
      } catch {
        data = {};
      }
    }
    if (res.status === 401) {
      if (typeof data.login === "string") window.location.href = data.login;
      throw new Error(String(data.error || "Chưa đăng nhập"));
    }
    if (!res.ok) throw new Error(String(data.error || res.statusText || "Lỗi"));
    return data;
  }

  /** @returns {number[]} */
  function selectedCampaignIds() {
    const box = document.getElementById("crm-mp-campaign-box");
    if (!box) return [];
    const ids = [];
    box.querySelectorAll("input.crm-mp-camp-cb:checked").forEach((el) => {
      const x = Number((/** @type {HTMLInputElement} */ (el)).value);
      if (Number.isFinite(x)) ids.push(x);
    });
    return ids;
  }

  function syncCampaignChecks(linkedIds) {
    const set = new Set((linkedIds || []).map(Number));
    document.querySelectorAll("#crm-mp-campaign-box input.crm-mp-camp-cb").forEach((el) => {
      const inp = /** @type {HTMLInputElement} */ (el);
      inp.checked = set.has(Number(inp.value));
    });
  }

  function renderCampaignChoices() {
    const box = document.getElementById("crm-mp-campaign-box");
    if (!box) return;
    const frag = document.createDocumentFragment();
    campaignsCache.forEach((c) => {
      const id = Number(c.id);
      const lbl = document.createElement("label");
      lbl.className = "crm-mp-camp-option";
      const ch = document.createElement("input");
      ch.type = "checkbox";
      ch.className = "crm-mp-camp-cb";
      ch.value = String(id);
      const code = String(c.code || "").trim();
      const name = String(c.name || "").trim() || `#${id}`;
      const tail = [];
      if (code) tail.push(code);
      if (String(c.channel || "")) tail.push(String(c.channel));
      lbl.appendChild(ch);
      const span = document.createElement("span");
      span.textContent = name + (tail.length ? ` — ${tail.join(" · ")}` : "");
      lbl.appendChild(span);
      lbl.dataset.search = `${name} ${code}`.toLowerCase();
      frag.appendChild(lbl);
    });
    box.innerHTML = "";
    box.appendChild(frag);
  }

  function wireCampaignFilter() {
    const inp = document.getElementById("crm-mp-camp-filter");
    if (!inp) return;
    inp.addEventListener("input", () => {
      const q = String(inp.value || "").trim().toLowerCase();
      document.querySelectorAll("#crm-mp-campaign-box .crm-mp-camp-option").forEach((el) => {
        const opt = /** @type {HTMLElement} */ (el);
        const hay = opt.dataset.search || "";
        opt.hidden = q && !hay.includes(q);
      });
    });
  }

  /** @returns {HTMLElement|null} */
  function modalRoot() {
    return document.getElementById("crm-mp-modal");
  }

  function closeStrategyFwModal() {
    const r = document.getElementById("crm-mp-modal-strategy-fw");
    if (!r) return;
    r.hidden = true;
    r.classList.remove("is-open");
    updateStrategyFwSummary();
  }

  /** @returns {number} */
  function strategyFwFilledCount() {
    let n = 0;
    strategy_framework_keys.forEach((k) => {
      const el = document.getElementById(`crm-mp-sf-${k}`);
      if (el && "value" in el && String(/** @type {HTMLTextAreaElement} */ (el).value).trim())
        n += 1;
    });
    return n;
  }

  /** @returns {number} */
  function tmProfFilledCount() {
    let n = 0;
    target_market_prof_keys.forEach((k) => {
      const el = document.getElementById(`crm-mp-tm-${k}`);
      if (el && "value" in el && String(/** @type {HTMLTextAreaElement} */ (el).value).trim())
        n += 1;
    });
    return n;
  }

  /** @returns {number} */
  function tmSteps4FilledCount() {
    let n = 0;
    target_market_steps4_keys.forEach((k) => {
      const el = document.getElementById(`crm-mp-s4-${k}`);
      if (el && "value" in el && String(/** @type {HTMLTextAreaElement} */ (el).value).trim())
        n += 1;
    });
    return n;
  }

  function updateStrategyFwSummary() {
    const el = document.getElementById("crm-mp-fw-summary");
    if (!el) return;
    const fw = strategyFwFilledCount();
    const tm = tmProfFilledCount();
    const s4 = tmSteps4FilledCount();
    if (!fw && !tm && !s4) {
      el.textContent = "Chưa nhập chi tiết nghiệp vụ.";
      return;
    }
    el.textContent = `Khung 9 trụ: ${fw}/9 · TMMT chi tiết: ${tm}/12 · Quy trình 4 bước: ${s4}/14.`;
  }

  function openStrategyFwModal() {
    const r = document.getElementById("crm-mp-modal-strategy-fw");
    if (!r) return;
    r.hidden = false;
    r.classList.add("is-open");
    updateStrategyFwSummary();
    const sum = document.getElementById("crm-mp-sf-target_market");
    if (sum instanceof HTMLTextAreaElement) window.setTimeout(() => sum.focus(), 80);
  }

  function openModal() {
    const r = modalRoot();
    if (!r) return;
    r.hidden = false;
    r.classList.add("is-open");
    document.body.style.overflow = "hidden";
  }

  function closeModalFn() {
    closeStrategyFwModal();
    const r = modalRoot();
    if (!r) return;
    r.hidden = true;
    r.classList.remove("is-open");
    document.body.style.overflow = "";
  }

  /** @returns {Promise<void>} */
  async function putCampaignLinks(planId) {
    const ids = selectedCampaignIds();
    await reqJson(`/api/crm/marketing-plans/${planId}/campaigns`, {
      method: "PUT",
      body: JSON.stringify({ campaign_ids: ids }),
    });
  }

  /** @returns {string[]} */
  function selectedChannels() {
    /** @type {string[]} */
    const out = [];
    document.querySelectorAll("#crm-mp-channel-checks input:checked").forEach((el) => {
      const v = String((/** @type {HTMLInputElement} */ (el)).value || "");
      if (v && !out.includes(v)) out.push(v);
    });
    return out;
  }

  function renderChannelChecks() {
    const box = document.getElementById("crm-mp-channel-checks");
    if (!box) return;
    const frag = document.createDocumentFragment();
    campaign_channels.forEach((ch) => {
      const id = String(ch);
      const lbl = document.createElement("label");
      lbl.className = "crm-hub-inline-check";
      const inp = document.createElement("input");
      inp.type = "checkbox";
      inp.value = id;
      const lab = campaign_channel_labels[id] || id;
      lbl.appendChild(inp);
      lbl.appendChild(document.createTextNode(lab));
      frag.appendChild(lbl);
    });
    box.innerHTML = "";
    box.appendChild(frag);
  }

  function syncChannelsFromPlan(jsonStr) {
    /** @type {string[]} */
    let arr = [];
    try {
      const p = typeof jsonStr === "string" ? JSON.parse(jsonStr || "[]") : jsonStr;
      if (Array.isArray(p)) arr = p.map((x) => String(x));
    } catch {
      arr = [];
    }
    document.querySelectorAll("#crm-mp-channel-checks input[type=checkbox]").forEach((el) => {
      const inp = /** @type {HTMLInputElement} */ (el);
      inp.checked = arr.includes(inp.value);
    });
  }

  function fmtNumVnd(n) {
    try {
      return new Intl.NumberFormat("vi-VN").format(Number(n) || 0);
    } catch {
      return String(n ?? 0);
    }
  }

  /** @param {string} raw */
  function parseDigits(raw) {
    const s = String(raw || "").replace(/\D+/g, "");
    if (!s) return 0;
    try {
      return Math.min(9_999_999_999_999, Number(s));
    } catch {
      return 0;
    }
  }

  /** @returns {HTMLElement|null} */
  function kpiTbody() {
    return document.getElementById("crm-mp-kpi-tbody");
  }

  /** @returns {Record<string,string>[]} */
  function kpiCollect() {
    const tb = kpiTbody();
    /** @type {Record<string,string>[]} */
    const rows = [];
    if (!tb) return rows;
    tb.querySelectorAll("tr[data-kpi]").forEach((tr) => {
      const metric = String(
        (/** @type {HTMLInputElement} */ (tr.querySelector('[name="metric"]')))?.value || "",
      ).trim();
      const target = String(
        (/** @type {HTMLInputElement} */ (tr.querySelector('[name="target"]')))?.value || "",
      ).trim();
      if (!metric && !target) return;
      rows.push({ metric, target });
    });
    return rows;
  }

  function kpiAddRow(metric = "", target = "") {
    const tb = kpiTbody();
    if (!tb) return;
    const tr = document.createElement("tr");
    tr.dataset.kpi = "1";
    tr.innerHTML =
      `<td><input type="text" name="metric" maxlength="240" placeholder="VD: CPL, SQL, CTR" /></td>` +
      `<td><input type="text" name="target" maxlength="480" placeholder="VD: ≤ 500k, +20%" /></td>` +
      `<td><button type="button" class="crm-mp-icon-btn crm-mp-kpi-del" aria-label="Xoá dòng">×</button></td>`;
    tr.querySelector('[name="metric"]').value = metric;
    tr.querySelector('[name="target"]').value = target;
    tr.querySelector(".crm-mp-kpi-del").addEventListener("click", () => tr.remove());
    tb.appendChild(tr);
  }

  function kpiFromJson(js) {
    const tb = kpiTbody();
    if (!tb) return;
    tb.innerHTML = "";
    /** @type {any[]} */
    let arr = [];
    try {
      const p = typeof js === "string" ? JSON.parse(js || "[]") : js;
      if (Array.isArray(p)) arr = p;
    } catch {
      arr = [];
    }
    arr.forEach((item) => {
      if (!item || typeof item !== "object") return;
      kpiAddRow(String(item.metric || item.name || "").trim(), String(item.target || item.goal || "").trim());
    });
    if (!tb.children.length) kpiAddRow();
  }

  /** @returns {Record<string,string>} */
  function collectStrategyFramework() {
    /** @type {Record<string,string>} */
    const o = {};
    strategy_framework_keys.forEach((k) => {
      const el = document.getElementById(`crm-mp-sf-${k}`);
      o[k] = el && "value" in el ? String(/** @type {HTMLInputElement} */ (el).value || "").trim() : "";
    });
    return o;
  }

  /** @param {string|Record<string,string>|undefined} raw */
  function fillStrategyFramework(raw) {
    /** @type {Record<string, string>} */
    let o = {};
    try {
      const p =
        typeof raw === "string" ? JSON.parse(raw || "{}") : raw && typeof raw === "object" ? raw : {};
      if (p && typeof p === "object") o = /** @type {Record<string, string>} */ (p);
    } catch {
      o = {};
    }
    strategy_framework_keys.forEach((k) => {
      const el = document.getElementById(`crm-mp-sf-${k}`);
      if (el && "value" in el) /** @type {HTMLInputElement} */ (el).value = String(o[k] || "");
    });
  }

  function clearStrategyFramework() {
    strategy_framework_keys.forEach((k) => {
      const el = document.getElementById(`crm-mp-sf-${k}`);
      if (el && "value" in el) /** @type {HTMLInputElement} */ (el).value = "";
    });
  }

  /** @returns {Record<string,string>} */
  function collectTargetMarketProf() {
    /** @type {Record<string,string>} */
    const o = {};
    target_market_prof_keys.forEach((k) => {
      const el = document.getElementById(`crm-mp-tm-${k}`);
      o[k] = el && "value" in el ? String(/** @type {HTMLInputElement} */ (el).value || "").trim() : "";
    });
    return o;
  }

  /** @param {string|Record<string,string>|undefined} raw */
  function fillTargetMarketProf(raw) {
    /** @type {Record<string, string>} */
    let ob = {};
    try {
      const p =
        typeof raw === "string" ? JSON.parse(raw || "{}") : raw && typeof raw === "object" ? raw : {};
      if (p && typeof p === "object") ob = /** @type {Record<string, string>} */ (p);
    } catch {
      ob = {};
    }
    target_market_prof_keys.forEach((k) => {
      const el = document.getElementById(`crm-mp-tm-${k}`);
      if (el && "value" in el) /** @type {HTMLInputElement} */ (el).value = String(ob[k] || "");
    });
  }

  function clearTargetMarketProf() {
    target_market_prof_keys.forEach((k) => {
      const el = document.getElementById(`crm-mp-tm-${k}`);
      if (el && "value" in el) /** @type {HTMLInputElement} */ (el).value = "";
    });
  }

  /** @returns {Record<string,string>} */
  function collectTargetMarketSteps4() {
    /** @type {Record<string,string>} */
    const o = {};
    target_market_steps4_keys.forEach((k) => {
      const el = document.getElementById(`crm-mp-s4-${k}`);
      o[k] = el && "value" in el ? String(/** @type {HTMLInputElement} */ (el).value || "").trim() : "";
    });
    return o;
  }

  /** @param {string|Record<string,string>|undefined} raw */
  function fillTargetMarketSteps4(raw) {
    /** @type {Record<string, string>} */
    let ob = {};
    try {
      const p =
        typeof raw === "string" ? JSON.parse(raw || "{}") : raw && typeof raw === "object" ? raw : {};
      if (p && typeof p === "object") ob = /** @type {Record<string, string>} */ (p);
    } catch {
      ob = {};
    }
    target_market_steps4_keys.forEach((k) => {
      const el = document.getElementById(`crm-mp-s4-${k}`);
      if (el && "value" in el) /** @type {HTMLInputElement} */ (el).value = String(ob[k] || "");
    });
  }

  function clearTargetMarketSteps4() {
    target_market_steps4_keys.forEach((k) => {
      const el = document.getElementById(`crm-mp-s4-${k}`);
      if (el && "value" in el) /** @type {HTMLInputElement} */ (el).value = "";
    });
  }

  /** @returns {string} */
  function pillarsToText(js) {
    try {
      const a = typeof js === "string" ? JSON.parse(js || "[]") : js || [];
      if (!Array.isArray(a)) return "";
      return a
        .map((x) =>
          typeof x === "string" ? x : (x && typeof x === "object" && (x.title || x.name || x.slug)) ? String(x.title || x.name || x.slug) : JSON.stringify(x),
        )
        .filter(Boolean)
        .join("\n");
    } catch {
      return "";
    }
  }

  /** @param {HTMLSelectElement|null} sel @param {{value:string;text:string}[]} opts */
  function fillSelect(sel, opts) {
    if (!sel) return;
    const cur = sel.value;
    sel.innerHTML = "";
    opts.forEach((o) => {
      const opt = document.createElement("option");
      opt.value = o.value;
      opt.textContent = o.text;
      sel.appendChild(opt);
    });
    try {
      if (opts.some((o) => o.value === cur)) sel.value = cur;
    } catch {
      /* ignore */
    }
  }

  /** @returns {Promise<void>} */
  async function loadStaff() {
    const data = await reqJson("/api/crm/staff");
    staffCache = data.staff || [];
    /** @type {HTMLSelectElement|null} */
    const ownerSel = document.querySelector("#crm-mp-f-owner");
    fillSelect(ownerSel, [
      { value: "", text: "— Chưa gán —" },
      ...staffCache.map((s) => ({ value: String(s.id), text: `${s.name || ""} (#${s.id})` })),
    ]);
  }

  /** @returns {Promise<void>} */
  async function loadCampaigns() {
    const data = await reqJson("/api/crm/campaigns");
    campaignsCache = data.campaigns || [];
    renderCampaignChoices();
    wireCampaignFilter();
  }

  function fillFilters() {
    /** @type {HTMLSelectElement|null} */
    const st = document.querySelector("#crm-mp-filter-status");
    /** @type {HTMLInputElement|null} */
    const fyEl = document.querySelector("#crm-mp-filter-fy");
    if (!st) return;

    /** @type {{value:string;text:string}[]} */
    const opts = [{ value: "all", text: "Tất cả trạng thái" }];
    Object.entries(plan_status_labels).forEach(([k, lv]) =>
      opts.push({ value: k, text: String(lv || k) }),
    );
    fillSelect(st, opts);
    if (!st.value || st.options.length === 1) st.value = "all";
    const y = new Date().getFullYear();
    if (fyEl && !fyEl.value) fyEl.value = String(y);
  }

  function fillFormSelects() {
    /** @type {HTMLSelectElement|null} */
    const st = document.querySelector("#crm-mp-form-status");
    /** @type {HTMLSelectElement|null} */
    const prio = document.querySelector("#crm-mp-form-priority");
    const stOpts = Object.entries(plan_status_labels).map(([k, lv]) => ({ value: k, text: String(lv || k) }));
    fillSelect(st, stOpts);
    /** @type {{value:string;text:string}[]} */
    const pOpts = plan_priorities.map((k) => ({
      value: String(k),
      text: String(plan_priority_labels[k] || k),
    }));
    fillSelect(prio, pOpts);
    /** @type {HTMLSelectElement|null} */
    const msNew = document.querySelector("#crm-mp-ms-new-status");
    const msOpts = ms_statuses.map((k) => ({ value: k, text: String(ms_status_labels[k] || k) }));
    fillSelect(msNew, msOpts);
  }

  /** @returns {Promise<void>} */
  async function loadPlans() {
    const msg = document.getElementById("crm-mp-list-msg");
    /** @type {HTMLInputElement|null} */
    const fyEl = document.querySelector("#crm-mp-filter-fy");
    /** @type {HTMLSelectElement|null} */
    const st = document.querySelector("#crm-mp-filter-status");
    /** @type {HTMLInputElement|null} */
    const qEl = document.querySelector("#crm-mp-f-q");

    /** @type {URLSearchParams} */
    const p = new URLSearchParams();
    const fyRaw = String(fyEl?.value ?? "").trim();
    if (fyRaw) {
      try {
        p.set("fiscal_year", String(Number(fyRaw)));
      } catch {
        /* noop */
      }
    }
    if (st && st.value && st.value !== "all") p.set("status", st.value);
    if (qEl && qEl.value.trim()) p.set("q", qEl.value.trim());
    boxMsg(msg || null, "");

    /** @type {HTMLElement|null} */
    const wrap = document.getElementById("crm-mp-table-wrap");
    if (wrap) wrap.setAttribute("aria-busy", "true");

    try {
      const data = await reqJson(`/api/crm/marketing-plans?${p.toString()}`);
      renderPlanTable(data.plans || []);
      boxMsg(msg || null, "", true);
    } catch (e) {
      console.error(e);
      boxMsg(msg || null, String(e.message || e), false);
      const tbody = document.getElementById("crm-mp-tbody");
      if (tbody) tbody.innerHTML = `<tr><td colspan="12" class="muted">Không tải được danh sách.</td></tr>`;
    } finally {
      if (wrap) wrap.removeAttribute("aria-busy");
    }
  }

  /** @param {Record<string, any>[]} plans */
  function renderPlanTable(plans) {
    const tbody = document.getElementById("crm-mp-tbody");
    if (!tbody) return;
    if (!plans.length) {
      tbody.innerHTML = `<tr><td colspan="12" class="muted">Chưa có kế hoạch khớp bộ lọc.</td></tr>`;
      return;
    }
    const rows = [];
    plans.forEach((p) => {
      const pid = Number(p.id);
      const sd = fmtDateDisp(p.updated_at || p.updatedAt);
      const stKey = String(p.status || "").toLowerCase();
      const stLab = esc(plan_status_labels[stKey] || p.status || "—");
      const prKey = String(p.priority || "").toLowerCase();
      const prLab = esc(plan_priority_labels[prKey] || p.priority || "—");
      const mtDone = Number(p.milestone_done) || 0;
      const mtTot = Number(p.milestone_total) || 0;
      const mcc = Number(p.linked_campaign_count) || 0;
      const owner = esc(p.owner_name || "—");

      const stSlug = escAttr(
        String(stKey)
          .toLowerCase()
          .replace(/[^a-z0-9_-]+/g, "-")
          .replace(/^-+|-+$/g, "") || "x",
      );
      rows.push(
        `<tr data-plan-id="${pid}">` +
          `<td class="muted">${esc(p.code || "—")}</td>` +
          `<td><strong>${esc(p.name || "")}</strong></td>` +
          `<td>${esc(String(p.fiscal_year ?? "—"))}</td>` +
          `<td>${esc(p.period_label || "—")}</td>` +
          `<td><span class="crm-mp-badge crm-mp-st-${stSlug}">${stLab}</span></td>` +
          `<td>${prLab}</td>` +
          `<td>${owner}</td>` +
          `<td class="crm-mp-num">${esc(fmtNumVnd(p.budget_planned_vnd))}</td>` +
          `<td>${mtTot ? `${mtDone}/${mtTot}` : "—"}</td>` +
          `<td>${mcc}</td>` +
          `<td class="muted">${sd}</td>` +
          `<td class="crm-mp-actions-cell">` +
          `<button type="button" class="btn-secondary crm-mp-btn-edit" data-id="${pid}">Sửa</button>` +
          `</td>` +
          `</tr>`,
      );
    });
    tbody.innerHTML = rows.join("");
    tbody.querySelectorAll(".crm-mp-btn-edit").forEach((btn) =>
      btn.addEventListener("click", () =>
        openEditModal(Number(btn.getAttribute("data-id"))),
      ),
    );
  }

  function escAttr(s) {
    return esc(s).replace(/"/g, "&quot;");
  }

  /** @returns {string} */
  function fmtDateDisp(ts) {
    if (!ts) return "—";
    const str = String(ts);
    const m = str.match(/^(\d{4}-\d{2}-\d{2})/);
    return m ? m[1] : str.slice(0, 16);
  }

  function resetModalFormNew() {
    modalPlanId = null;
    pendingMilestones = [];
    milestoneLocalInc = 0;
    /** @type {HTMLFormElement|null} */
    const form = document.getElementById("crm-mp-form");
    if (!form) return;
    form.reset();
    const hid = /** @type {HTMLInputElement} */ (document.getElementById("crm-mp-f-id"));
    hid.value = "";
    const fy = /** @type {HTMLInputElement} */ (document.getElementById("crm-mp-form-fiscal"));
    if (fy && !fy.value) fy.value = String(new Date().getFullYear());
    kpiFromJson([]);
    syncChannelsFromPlan("[]");
    syncCampaignChecks([]);
    renderMilestones([]);
    clearStrategyFramework();
    clearTargetMarketProf();
    clearTargetMarketSteps4();
    const delBtn = document.getElementById("crm-mp-delete-plan");
    if (delBtn) delBtn.hidden = true;
    /** @type {HTMLElement|null} */
    const mh = document.getElementById("crm-mp-modal-hint-sub");
    if (mh) mh.remove();
    const hint = document.getElementById("crm-mp-ms-hint");
    if (hint) hint.hidden = false;

    /** @type {HTMLElement|null} */
    const ttl = document.getElementById("crm-mp-modal-title");
    /** @type {HTMLElement|null} */
    const kk = document.getElementById("crm-mp-modal-kicker");
    if (ttl) ttl.textContent = "Kế hoạch mới";
    if (kk) kk.textContent = "Tạo mới";

    /** @type {HTMLInputElement|null} */
    const cf = document.getElementById("crm-mp-camp-filter");
    if (cf) cf.value = "";
    document.querySelectorAll("#crm-mp-campaign-box .crm-mp-camp-option").forEach((el) =>
      el.removeAttribute("hidden"),
    );

    /** @type {HTMLSelectElement|null} */
    const st = document.querySelector("#crm-mp-form-status");
    const prio = document.querySelector("#crm-mp-form-priority");
    fillFormSelects();
    if (st) st.value = "draft";
    if (prio) prio.value = "normal";
    showFormErr(document.getElementById("crm-mp-form-err"), "");
    updateStrategyFwSummary();
  }

  /** @returns {Promise<void>} */
  async function openEditModal(planId) {
    try {
      await loadStaff();
    } catch (e) {
      console.error(e);
    }
    showFormErr(document.getElementById("crm-mp-form-err"), "");
    pendingMilestones = [];
    const hint = document.getElementById("crm-mp-ms-hint");
    if (hint) hint.hidden = true;
    modalPlanId = planId;

    /** @type {HTMLElement|null} */
    const ttl = document.getElementById("crm-mp-modal-title");
    /** @type {HTMLElement|null} */
    const kk = document.getElementById("crm-mp-modal-kicker");
    if (ttl) ttl.textContent = "Chỉnh sửa kế hoạch";
    if (kk) kk.textContent = `#${planId}`;

    const delBtn = document.getElementById("crm-mp-delete-plan");
    if (delBtn) delBtn.hidden = false;

    try {
      const p = await reqJson(`/api/crm/marketing-plans/${planId}`);
      /** @type {HTMLInputElement} */
      document.getElementById("crm-mp-f-id").value = String(planId);

      /** @param {string} fid @returns {HTMLElement|null} */
      const gi = (fid) => document.getElementById(fid);
      gi("crm-mp-f-code").value = p.code || "";
      gi("crm-mp-f-name").value = p.name || "";
      gi("crm-mp-form-fiscal").value = String(p.fiscal_year || new Date().getFullYear());
      gi("crm-mp-f-period").value = p.period_label || "";
      fillFormSelects();
      gi("crm-mp-form-status").value = String(p.status || "draft");
      gi("crm-mp-form-priority").value = String(p.priority || "normal");
      gi("crm-mp-f-north").value = p.north_star || "";
      gi("crm-mp-f-obj").value = p.objectives || "";
      gi("crm-mp-f-pillars").value = pillarsToText(p.pillars_json);
      gi("crm-mp-f-aud").value = p.audiences || "";
      syncChannelsFromPlan(p.channels_focus_json);
      gi("crm-mp-f-budget-p").value = fmtNumVnd(p.budget_planned_vnd);
      gi("crm-mp-f-budget-a").value = fmtNumVnd(p.budget_actual_vnd);
      kpiFromJson(p.success_metrics_json);
      gi("crm-mp-f-risks").value = p.risks_notes || "";
      gi("crm-mp-f-notes").value = p.notes || "";
      gi("crm-mp-f-start").value = String(p.start_date || "").slice(0, 10);
      gi("crm-mp-f-end").value = String(p.end_date || "").slice(0, 10);
      gi("crm-mp-f-owner").value =
        p.owner_staff_id !== null && p.owner_staff_id !== undefined && p.owner_staff_id !== ""
          ? String(p.owner_staff_id)
          : "";
      syncCampaignChecks((p.campaigns || []).map((/** @type {any} */ c) => c.id));
      renderMilestones(p.milestones || []);
      fillStrategyFramework(p.strategy_framework_json);
      fillTargetMarketProf(p.target_market_prof_json);
      fillTargetMarketSteps4(p.target_market_steps4_json);
      updateStrategyFwSummary();
      openModal();
    } catch (e) {
      alert(String(e.message || e));
    }
  }

  /** @returns {HTMLTableSectionElement|null} */
  function msTbodyEl() {
    return document.getElementById("crm-mp-ms-tbody");
  }

  /** @returns {HTMLElement|null} */
  function msHint() {
    return document.getElementById("crm-mp-ms-hint");
  }

  /** @param {number} planIdInner */
  async function refreshPlanMilestones(planIdInner) {
    const p = await reqJson(`/api/crm/marketing-plans/${planIdInner}`);
    renderMilestones(p.milestones || []);
  }

  /**
   * @param {Record<string, any>[]} persisted
   * @returns {void}
   */
  function renderMilestones(persisted) {
    const tb = msTbodyEl();
    if (!tb) return;

    tb.innerHTML = "";
    persisted.forEach((m) =>
      tb.appendChild(
        milestoneRow(Number(m.id), {
          title: String(m.title || ""),
          due_date: String(m.due_date || "").slice(0, 10),
          status: String(m.status || "pending"),
          notes: String(m.notes || ""),
        }),
      ),
    );
    pendingMilestones.forEach((q) =>
      tb.appendChild(
        milestoneRow(null, {
          title: q.title,
          due_date: q.due_date,
          status: q.status,
          notes: q.notes,
          localKey: q.localKey,
        }),
      ),
    );

    /** @type {HTMLSelectElement|null} */
    const msNewStat = document.querySelector("#crm-mp-ms-new-status");
    if (msNewStat && !pendingMilestones.length && persisted.length === 0) msNewStat.value = "pending";

    const h = msHint();
    if (!h) return;
    if (!modalPlanId) h.hidden = pendingMilestones.length === 0;
    else h.hidden = true;
  }

  /**
   * @param {number | null} id
   * @param {{ title:string;due_date:string;status:string;notes:string;localKey?:string }} d
   * @returns {HTMLTableRowElement}
   */
  function milestoneRow(id, d) {
    const tr = document.createElement("tr");
    if (id) tr.dataset.mid = String(id);
    else if (d.localKey) tr.dataset.localMs = String(d.localKey);
    /** @type {Record<string,string>} */
    const stMap = {};
    ms_statuses.forEach((k) => {
      stMap[k] = String(ms_status_labels[k] || k);
    });

    const inpTitle = /** @type {HTMLInputElement} */ (document.createElement("input"));
    inpTitle.type = "text";
    inpTitle.value = d.title;
    inpTitle.maxLength = 500;

    const inpDue = /** @type {HTMLInputElement} */ (document.createElement("input"));
    inpDue.type = "date";
    inpDue.value = d.due_date;

    const selSt = /** @type {HTMLSelectElement} */ (document.createElement("select"));
    ms_statuses.forEach((k) => {
      const o = document.createElement("option");
      o.value = k;
      o.textContent = stMap[k] || k;
      selSt.appendChild(o);
    });
    selSt.value = d.status || "pending";

    const inpNotes = /** @type {HTMLInputElement} */ (document.createElement("input"));
    inpNotes.type = "text";
    inpNotes.value = d.notes;
    inpNotes.placeholder = "Ghi chú";
    inpNotes.style.width = "100%";

    /** @returns {Promise<void>} */
    async function saveRow() {
      const ttl = inpTitle.value.trim();
      if (!ttl) {
        alert("Nhập tiêu đề mốc");
        return;
      }
      if (!modalPlanId) {
        pendingMilestones = pendingMilestones.map((it) =>
          it.localKey === d.localKey
            ? {
                ...it,
                title: ttl,
                due_date: inpDue.value,
                status: selSt.value,
                notes: inpNotes.value,
              }
            : it,
        );
        renderMilestones([]);
        return;
      }

      try {
        if (id) {
          await reqJson(`/api/crm/marketing-plan-milestones/${id}`, {
            method: "PATCH",
            body: JSON.stringify({
              title: ttl,
              due_date: inpDue.value,
              status: selSt.value,
              notes: inpNotes.value.trim(),
            }),
          });
        } else {
          await reqJson(`/api/crm/marketing-plans/${modalPlanId}/milestones`, {
            method: "POST",
            body: JSON.stringify({
              title: ttl,
              due_date: inpDue.value,
              status: selSt.value,
              notes: inpNotes.value.trim(),
            }),
          });
        }
        if (modalPlanId != null) await refreshPlanMilestones(modalPlanId);
      } catch (e) {
        alert(String(e.message || e));
      }
    }

    /** @returns {Promise<void>} */
    async function delRow() {
      if (d.localKey) {
        pendingMilestones = pendingMilestones.filter((x) => x.localKey !== d.localKey);
        renderMilestones([]);
        return;
      }
      if (!id) return;
      if (!confirm("Xoá mốc này?")) return;
      try {
        await reqJson(`/api/crm/marketing-plan-milestones/${id}`, { method: "DELETE" });
        if (modalPlanId != null) await refreshPlanMilestones(modalPlanId);
      } catch (e) {
        alert(String(e.message || e));
      }
    }

    const tdA = document.createElement("td");
    tdA.appendChild(inpTitle);
    const tdB = document.createElement("td");
    tdB.appendChild(inpDue);
    const tdC = document.createElement("td");
    tdC.appendChild(selSt);
    const tdD = document.createElement("td");
    tdD.appendChild(inpNotes);
    const tdE = document.createElement("td");
    tdE.className = "crm-mp-ms-act";

    const btnSave = document.createElement("button");
    btnSave.type = "button";
    btnSave.className = "btn-secondary";
    btnSave.textContent = "Lưu";
    btnSave.addEventListener("click", () => void saveRow());

    const btnDel = document.createElement("button");
    btnDel.type = "button";
    btnDel.className = "crm-mp-icon-btn";
    btnDel.setAttribute("aria-label", "Xoá");
    btnDel.textContent = "×";
    btnDel.addEventListener("click", () => void delRow());

    tdE.append(btnSave, btnDel);
    tr.append(tdA, tdB, tdC, tdD, tdE);
    return tr;
  }

  function addMilestoneDraft() {
    const titleEl = /** @type {HTMLInputElement} */ (document.getElementById("crm-mp-ms-new-title"));
    const dueEl = /** @type {HTMLInputElement} */ (document.getElementById("crm-mp-ms-new-due"));
    const statEl = /** @type {HTMLSelectElement} */ (document.getElementById("crm-mp-ms-new-status"));
    const title = String(titleEl?.value ?? "").trim();
    if (!title) {
      alert("Nhập tiêu đề mốc");
      return;
    }
    const due = dueEl?.value ?? "";
    const status = statEl?.value || "pending";
    milestoneLocalInc += 1;
    const localKey = `L_${milestoneLocalInc}`;
    pendingMilestones.push({ localKey, title, due_date: due, status, notes: "" });
    if (titleEl) titleEl.value = "";
    if (dueEl) dueEl.value = "";
    msHint()?.removeAttribute("hidden");

    /** @returns {Promise<void>} */
    async function pushServer() {
      if (!modalPlanId) return;
      try {
        await reqJson(`/api/crm/marketing-plans/${modalPlanId}/milestones`, {
          method: "POST",
          body: JSON.stringify({ title, due_date: due || "", status, notes: "" }),
        });
        pendingMilestones = pendingMilestones.filter((x) => x.localKey !== localKey);
        await refreshPlanMilestones(modalPlanId);
      } catch (e) {
        alert(String(e.message || e));
      }
    }

    if (modalPlanId) {
      pendingMilestones = pendingMilestones.filter((x) => x.localKey !== localKey);
      void pushServer();
      return;
    }
    renderMilestones([]);
  }

  /** @returns {Promise<void>} */
  async function flushPendingMiles(planIdInner) {
    const copy = pendingMilestones.slice();
    for (let i = 0; i < copy.length; i += 1) {
      const m = copy[i];
      if (!m.title.trim()) continue;
      await reqJson(`/api/crm/marketing-plans/${planIdInner}/milestones`, {
        method: "POST",
        body: JSON.stringify({
          title: m.title.trim(),
          due_date: m.due_date || "",
          status: m.status,
          notes: m.notes || "",
        }),
      });
    }
    pendingMilestones = [];
  }

  /** @returns {Promise<void>} */
  async function onSubmitForm(ev) {
    ev.preventDefault();
    const errEl = document.getElementById("crm-mp-form-err");
    showFormErr(errEl, "");
    const gv = (id) => document.getElementById(id);

    const name = /** @type {HTMLInputElement} */ (gv("crm-mp-f-name")).value.trim();
    if (!name) {
      showFormErr(errEl, "Cần tên kế hoạch.");
      return;
    }

    const pillarsRaw = /** @type {HTMLTextAreaElement} */ (gv("crm-mp-f-pillars")).value.trim();
    const pillarsArr = pillarsRaw
      .split("\n")
      .map((s) => s.trim())
      .filter(Boolean);

    const body = {
      code: /** @type {HTMLInputElement} */ (gv("crm-mp-f-code")).value.trim(),
      name,
      fiscal_year: Number(/** @type {HTMLInputElement} */ (gv("crm-mp-form-fiscal")).value),
      period_label: /** @type {HTMLInputElement} */ (gv("crm-mp-f-period")).value.trim(),
      status: /** @type {HTMLSelectElement} */ (gv("crm-mp-form-status")).value,
      priority: /** @type {HTMLSelectElement} */ (gv("crm-mp-form-priority")).value,
      north_star: /** @type {HTMLTextAreaElement} */ (gv("crm-mp-f-north")).value.trim(),
      objectives: /** @type {HTMLTextAreaElement} */ (gv("crm-mp-f-obj")).value.trim(),
      pillars_json: pillarsArr,
      audiences: /** @type {HTMLTextAreaElement} */ (gv("crm-mp-f-aud")).value.trim(),
      channels_focus: selectedChannels(),
      budget_planned_vnd: parseDigits(/** @type {HTMLInputElement} */ (gv("crm-mp-f-budget-p")).value),
      budget_actual_vnd: parseDigits(/** @type {HTMLInputElement} */ (gv("crm-mp-f-budget-a")).value),
      success_metrics_json: kpiCollect(),
      risks_notes: /** @type {HTMLTextAreaElement} */ (gv("crm-mp-f-risks")).value.trim(),
      notes: /** @type {HTMLTextAreaElement} */ (gv("crm-mp-f-notes")).value.trim(),
      start_date: /** @type {HTMLInputElement} */ (gv("crm-mp-f-start")).value,
      end_date: /** @type {HTMLInputElement} */ (gv("crm-mp-f-end")).value,
      strategy_framework_json: collectStrategyFramework(),
      target_market_prof_json: collectTargetMarketProf(),
      target_market_steps4_json: collectTargetMarketSteps4(),
    };

    const ownerSel = gv("crm-mp-f-owner");
    const ooVal = ownerSel instanceof HTMLSelectElement ? ownerSel.value : "";
    if (ooVal) body.owner_staff_id = Number(ooVal);
    else body.owner_staff_id = null;

    try {
      if (modalPlanId) {
        await reqJson(`/api/crm/marketing-plans/${modalPlanId}`, {
          method: "PATCH",
          body: JSON.stringify(body),
        });
        await putCampaignLinks(modalPlanId);
      } else {
        const cidArr = selectedCampaignIds();
        const created = await reqJson(`/api/crm/marketing-plans`, {
          method: "POST",
          body: JSON.stringify({ ...body, campaign_ids: cidArr }),
        });
        modalPlanId = Number(created.id);
        const hid = gv("crm-mp-f-id");
        if (hid instanceof HTMLInputElement) hid.value = String(modalPlanId);

        const dk = gv("crm-mp-delete-plan");
        if (dk) dk.hidden = false;
        msHint()?.setAttribute("hidden", "hidden");

        try {
          await flushPendingMiles(modalPlanId);
        } catch (e2) {
          showFormErr(errEl, String(e2.message || e2));
          await loadPlans();
          return;
        }
        await putCampaignLinks(modalPlanId);

        const ttl = gv("crm-mp-modal-title");
        const kk = gv("crm-mp-modal-kicker");
        if (ttl) ttl.textContent = "Chỉnh sửa kế hoạch";
        if (kk) kk.textContent = `#${modalPlanId}`;

        await refreshPlanMilestones(modalPlanId);
      }
      await loadPlans();
      boxMsg(document.getElementById("crm-mp-list-msg"), "Đã lưu.", true);
    } catch (e) {
      showFormErr(errEl, String(e.message || e));
    }
  }

  /** @returns {Promise<void>} */
  async function deleteWholePlan() {
    if (!modalPlanId || !confirm("Xoá toàn bộ kế hoạch (mốc, liên kết campaign)?")) return;
    try {
      await reqJson(`/api/crm/marketing-plans/${modalPlanId}`, { method: "DELETE" });
      closeModalFn();
      await loadPlans();
      boxMsg(document.getElementById("crm-mp-list-msg"), "Đã xoá kế hoạch.", true);
    } catch (e) {
      alert(String(e.message || e));
    }
  }

  function wireBudgetFormat() {
    ["crm-mp-f-budget-p", "crm-mp-f-budget-a"].forEach((fid) => {
      const inp = /** @type {HTMLInputElement|null} */ (document.getElementById(fid));
      if (!inp) return;
      inp.addEventListener("blur", () => {
        const n = parseDigits(inp.value);
        inp.value = n ? fmtNumVnd(n) : "";
      });
    });
  }

  function wireStrategyFwPopup() {
    document.querySelectorAll("[data-strategy-fw-close]").forEach((btn) =>
      btn.addEventListener("click", () => closeStrategyFwModal()),
    );
    document.getElementById("crm-mp-open-strategy-fw")?.addEventListener("click", () => openStrategyFwModal());
    const popup = document.getElementById("crm-mp-modal-strategy-fw");
    if (popup)
      popup.addEventListener("input", (ev) => {
        const t = ev.target;
        if (
          t instanceof HTMLTextAreaElement &&
          t.id &&
          (t.id.startsWith("crm-mp-sf-") ||
            t.id.startsWith("crm-mp-tm-") ||
            t.id.startsWith("crm-mp-s4-"))
        )
          updateStrategyFwSummary();
      });
  }

  function wireModalClose() {
    document.querySelectorAll("#crm-mp-modal [data-close-modal]").forEach((el) =>
      el.addEventListener("click", () => closeModalFn()),
    );
  }

  function init() {
    renderChannelChecks();
    fillFilters();
    fillFormSelects();
    wireBudgetFormat();
    wireModalClose();
    wireStrategyFwPopup();

    Promise.all([loadStaff(), loadCampaigns()])
      .then(() => loadPlans())
      .catch((e) => console.error(e));

    ["#crm-mp-filter-fy", "#crm-mp-filter-status"].forEach((sel) => {
      const el = document.querySelector(sel);
      if (!el) return;
      el.addEventListener("change", () => void loadPlans());
    });
    const qEl = document.querySelector("#crm-mp-f-q");
    if (qEl) {
      /** @type {number|undefined} */
      let tid;
      qEl.addEventListener("input", () => {
        if (tid) window.clearTimeout(tid);
        tid = window.setTimeout(() => void loadPlans(), 360);
      });
    }

    document.querySelector("#crm-mp-open-create")?.addEventListener("click", () => {
      resetModalFormNew();
      openModal();
      loadStaff().catch(console.error);
    });

    document.getElementById("crm-mp-form")?.addEventListener("submit", (e) => void onSubmitForm(e));
    document.getElementById("crm-mp-ms-add")?.addEventListener("click", () => addMilestoneDraft());
    document.getElementById("crm-mp-delete-plan")?.addEventListener("click", () => void deleteWholePlan());

    document.getElementById("crm-mp-kpi-add")?.addEventListener("click", () => kpiAddRow());
    updateStrategyFwSummary();
  }

  init();
})();
