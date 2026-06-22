(function () {
  /* Tránh bfcache: sau đăng xuất ở tab khác, quay lại tab CRM vẫn thấy trang cũ nếu không reload. */
  window.addEventListener("pageshow", (ev) => {
    if (ev.persisted) window.location.reload();
  });

  const metaEl = document.getElementById("crm-meta");
  const meta = metaEl ? JSON.parse(metaEl.textContent) : {};
  const { statuses, status_labels, channels, channel_labels, priorities, priority_labels } = meta;
  const pipeline_stages = meta.pipeline_stages || statuses;
  const pipeline_labels = meta.pipeline_labels || status_labels;
  const care_contact_types = meta.care_contact_types || [];
  const care_contact_labels = meta.care_contact_labels || {};
  const care_status_types = meta.care_status_types || [];
  const care_status_labels = meta.care_status_labels || {};

  const STAFF_STORAGE_KEY = "ptt_crm_my_staff_id";
  const staffPortal = Boolean(meta.staff_portal);
  const portalStaffId = meta.staff_id != null ? Number(meta.staff_id) : null;
  const portalStaffName = String(meta.staff_name || "");

  /** @type {Record<string, string>} */
  let dynamicChannelLabels = { ...(channel_labels || {}) };
  /** @type {string[]} */
  let dynamicChannelIds = [...(channels || [])];

  const boardEl = document.getElementById("crm-board");
  const searchEl = document.getElementById("crm-search");
  const modalCreate = document.getElementById("crm-modal-create");
  const modalDetail = document.getElementById("crm-modal-detail");
  const formCreate = document.getElementById("crm-form-create");
  const formDetail = document.getElementById("crm-form-detail");
  const formNote = document.getElementById("crm-form-note");
  const formCareReport = document.getElementById("crm-form-care-report");
  const myStaffSelect = document.getElementById("crm-my-staff-select");
  const staffStatsEl = document.getElementById("crm-staff-stats");
  const staffHintEl = document.getElementById("crm-staff-workspace-hint");
  const createErr = document.getElementById("crm-create-msg-error");
  const detailErr = document.getElementById("crm-detail-msg-error");
  const detailOk = document.getElementById("crm-detail-msg-ok");
  const detailLoading = document.getElementById("crm-detail-loading");
  const detailBody = document.getElementById("crm-detail-body");
  const filterSummaryEl = document.getElementById("crm-filter-summary");
  const customersTbody = document.getElementById("crm-customers-tbody");
  const customersEmptyEl = document.getElementById("crm-customers-empty");
  const customersSummaryEl = document.getElementById("crm-customers-summary");

  const TERMINAL_STAGES = new Set(["chot", "mat", "da_giai_quyet", "dong"]);
  /** @type {"active"|"all"|"done"} */
  let careTableFilter = staffPortal ? "active" : "active";

  const DETAIL_SKELETON_HTML = `
    <span class="crm-skeleton crm-skeleton-line"></span>
    <span class="crm-skeleton crm-skeleton-line crm-skeleton-line--short"></span>
    <p class="crm-detail-loading-text">Đang tải hồ sơ…</p>
  `;

  /** @type {Array<Record<string, unknown>>} */
  let cachedCases = [];
  /** @type {Array<Record<string, unknown>>} */
  let cachedStaff = [];
  /** @type {Array<Record<string, unknown>>} */
  let cachedCampaigns = [];
  /** @type {string} */
  let searchDebounceTimer;
  /** @type {"all"|"mine"} */
  let viewMode = staffPortal ? "mine" : "mine";
  /** @type {number|null} */
  let myStaffId = staffPortal && portalStaffId ? portalStaffId : null;
  /** @type {"all"|"thap"|"binh_thuong"|"cao"} */
  let priorityFilter = "all";

  async function reqJson(url, opts = {}) {
    const headers = {
      Accept: "application/json",
      ...(opts.headers || {}),
    };
    const body = opts.body;
    if (body && typeof body === "string") headers["Content-Type"] = "application/json";

    const res = await fetch(url, {
      credentials: "same-origin",
      ...opts,
      headers,
    });
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
      if (typeof data.login === "string") {
        window.location.href = data.login;
      }
      throw new Error(data.error || "Chưa đăng nhập");
    }

    if (!res.ok) {
      const msg = data.error || res.statusText || "Lỗi mạng";
      throw new Error(msg);
    }
    return data;
  }

  function esc(s) {
    const d = document.createElement("div");
    d.textContent = s ?? "";
    return d.innerHTML;
  }

  function truncate(str, n) {
    const t = String(str ?? "").trim().replace(/\s+/g, " ");
    if (t.length <= n) return t;
    return `${t.slice(0, n)}…`;
  }

  /** @param {string} isoLike */
  function formatViDateTime(isoLike) {
    const raw = String(isoLike || "");
    const m = raw.match(/^(\d{4})-(\d{2})-(\d{2})[ T](\d{2}):(\d{2})/);
    if (!m) return raw || "—";
    const [, y, mo, d, h, mi] = m;
    return `${d}/${mo}/${y} · ${h}:${mi}`;
  }

  /** @param {string} name */
  function customerInitials(name) {
    const s = String(name || "").trim();
    if (!s) return "?";
    const parts = s.split(/\s+/).filter(Boolean);
    if (parts.length >= 2) {
      const a = parts[0][0] || "";
      const b = parts[parts.length - 1][0] || "";
      return (a + b).toUpperCase();
    }
    return s.slice(0, 2).toUpperCase();
  }

  function fillSelect(sel, ids, labelsMap) {
    sel.innerHTML = "";
    ids.forEach((id) => {
      const opt = document.createElement("option");
      opt.value = id;
      opt.textContent = labelsMap[id] || id;
      sel.appendChild(opt);
    });
  }

  async function loadChannelsForSelects(detailChannelCode) {
    try {
      const data = await reqJson("/api/crm/channels");
      const list = data.channels || [];
      dynamicChannelIds = list.map((c) => String(c.code));
      dynamicChannelLabels = { ...(channel_labels || {}) };
      list.forEach((c) => {
        dynamicChannelLabels[String(c.code)] = String(c.name);
      });
      if (!dynamicChannelIds.length) {
        dynamicChannelIds = [...channels];
      }
    } catch {
      dynamicChannelIds = [...channels];
      dynamicChannelLabels = { ...(channel_labels || {}) };
    }
    const createSel = document.getElementById("crm-create-channel");
    const detailSel = formDetail?.elements?.channel;
    if (createSel instanceof HTMLSelectElement) {
      fillSelect(createSel, dynamicChannelIds, dynamicChannelLabels);
    }
    if (detailSel instanceof HTMLSelectElement) {
      fillSelect(detailSel, dynamicChannelIds, dynamicChannelLabels);
      const want =
        detailChannelCode != null && detailChannelCode !== ""
          ? String(detailChannelCode)
          : "";
      if (want && [...detailSel.options].some((o) => o.value === want)) {
        detailSel.value = want;
      }
    }
  }

  function populateCreateFormSelects() {
    fillSelect(document.getElementById("crm-create-priority"), priorities, priority_labels);
  }

  /**
   * Đổ danh sách nhân viên vào ô Phụ trách (sau khi đã `loadStaffForSelects`).
   * @param {string|number|null|undefined} detailAssignId — `assigned_staff_id` khi mở chi tiết
   */
  function fillAssignSelects(detailAssignId) {
    const createSel = document.getElementById("crm-create-assigned");
    const detailSel = document.getElementById("crm-detail-assigned");
    const base =
      '<option value="">— Chưa phân công —</option>' +
      cachedStaff
        .map(
          (s) =>
            `<option value="${escapeAttr(String(s.id))}">${esc(s.name)}</option>`,
        )
        .join("");
    if (createSel) createSel.innerHTML = base;
    if (detailSel) {
      detailSel.innerHTML = base;
      const v =
        detailAssignId != null && detailAssignId !== ""
          ? String(detailAssignId)
          : "";
      detailSel.value = v;
    }
  }

  async function loadStaffForSelects() {
    try {
      if (!staffPortal) {
        const data = await reqJson("/api/crm/staff");
        cachedStaff = (data.staff || []).filter((s) => s.active !== 0);
      }
      fillAssignSelects();
      if (staffPortal) {
        const ws = document.getElementById("crm-staff-workspace");
        const ctrls = document.getElementById("crm-staff-workspace-controls");
        if (ctrls) ctrls.hidden = true;
        if (ws) {
          const title = ws.querySelector(".crm-staff-workspace-title");
          if (title) title.textContent = `Khách hàng của ${portalStaffName || "bạn"}`;
        }
      } else if (myStaffSelect instanceof HTMLSelectElement) {
        const saved = localStorage.getItem(STAFF_STORAGE_KEY) || "";
        myStaffSelect.innerHTML =
          '<option value="">— Chọn nhân viên —</option>' +
          cachedStaff
            .map(
              (s) =>
                `<option value="${escapeAttr(String(s.id))}">${esc(s.name)}</option>`,
            )
            .join("");
        if (saved && cachedStaff.some((s) => String(s.id) === saved)) {
          myStaffSelect.value = saved;
          myStaffId = Number(saved);
        } else if (cachedStaff.length === 1) {
          myStaffSelect.value = String(cachedStaff[0].id);
          myStaffId = Number(cachedStaff[0].id);
        }
      }
      populateCareFormSelects();
      await loadStaffWorkspace();
    } catch {
      cachedStaff = [];
    }
  }

  function populateCareFormSelects() {
    const contactSel = document.getElementById("crm-care-contact");
    const statusSel = document.getElementById("crm-care-status");
    if (contactSel instanceof HTMLSelectElement) {
      fillSelect(contactSel, care_contact_types, care_contact_labels);
    }
    if (statusSel instanceof HTMLSelectElement) {
      fillSelect(statusSel, care_status_types, care_status_labels);
    }
  }

  async function loadStaffWorkspace() {
    if (!myStaffId || viewMode !== "mine") {
      if (staffStatsEl) staffStatsEl.hidden = true;
      if (staffHintEl) {
        staffHintEl.textContent =
          viewMode === "mine" && !myStaffId
            ? "Chọn nhân viên để xem khách được gán và báo cáo chăm sóc."
            : "Đang xem toàn bộ hồ sơ (chế độ quản lý).";
      }
      return;
    }
    try {
      const data = await reqJson(`/api/crm/staff/${myStaffId}/workspace`);
      const st = data.stats || {};
      setText("crm-staff-stat-open", st.open ?? 0);
      setText("crm-staff-stat-high", st.high_priority ?? 0);
      setText("crm-staff-stat-sla", st.sla_overdue ?? 0);
      setText("crm-staff-stat-noreport", st.no_care_report ?? 0);
      setText("crm-staff-stat-new", st.new_today ?? 0);
      if (staffStatsEl) staffStatsEl.hidden = false;
      if (staffHintEl && data.staff?.name) {
        staffHintEl.textContent = `Đang chăm sóc ${st.open ?? 0} khách — ${data.staff.name}.`;
      }
    } catch {
      if (staffStatsEl) staffStatsEl.hidden = true;
    }
  }

  /**
   * Tải danh sách chiến dịch (kể cả đã tắt) cho form tạo / chi tiết.
   * @param {string|number|null|undefined} [detailCampaignId]
   */
  async function loadCampaignDropdowns(detailCampaignId) {
    try {
      const data = await reqJson("/api/crm/campaigns?include_inactive=1");
      cachedCampaigns = data.campaigns || [];
    } catch {
      cachedCampaigns = [];
    }

    /** @returns {string} */
    const optsHtml = () =>
      `<option value="">— Tuỳ chọn —</option>${cachedCampaigns
        .map((camp) => {
          const off = Number(camp.active) === 0 ? " [tắt]" : "";
          const cx = camp.code ? `[${escapeAttr(String(camp.code))}] ` : "";
          return `<option value="${escapeAttr(String(camp.id))}">${cx}${escapeAttr(String(camp.name || ""))}${escapeAttr(off)}</option>`;
        })
        .join("")}`;
    const cre = document.getElementById("crm-create-campaign");
    const det = document.getElementById("crm-detail-campaign");
    if (cre instanceof HTMLSelectElement) cre.innerHTML = optsHtml();
    if (det instanceof HTMLSelectElement) {
      det.innerHTML = optsHtml();
      const want =
        detailCampaignId != null && detailCampaignId !== ""
          ? String(detailCampaignId)
          : "";
      det.value =
        want &&
        [...det.options].some((opt) => opt.value === want)
          ? want
          : "";
    }
  }

  async function loadReminderStrip() {
    const strip = document.getElementById("crm-remind-strip");
    const txtEl = document.getElementById("crm-remind-summary-text");
    if (!strip || !txtEl) return;
    try {
      const sum = await reqJson("/api/crm/reminders/summary");
      const cts = /** @type {Record<string, number>} */ ((sum.counts && typeof sum.counts === "object" && sum.counts) || {});
      const o = Number(cts.overdue || 0);
      const today = Number(cts.today || 0);
      if (o + today === 0) {
        strip.hidden = true;
        return;
      }
      strip.hidden = false;
      const chunks = [];
      if (o) chunks.push(`${o} nhắc việc quá hạn`);
      if (today) chunks.push(`${today} cần xử lý hôm nay`);
      txtEl.textContent = chunks.join(" · ");
    } catch {
      strip.hidden = true;
    }
  }

  populateCreateFormSelects();

  fillSelect(formDetail.elements.status, statuses, status_labels);
  fillSelect(document.getElementById("crm-detail-pipeline"), pipeline_stages, pipeline_labels);
  fillSelect(formDetail.elements.priority, priorities, priority_labels);

  function escapeAttr(s) {
    return esc(s).replace(/"/g, "&quot;");
  }

  /** @param {Record<string, unknown>} c */
  function casePipelineStage(c) {
    return String(c.pipeline_stage || c.status || pipeline_stages[0] || "moi");
  }

  /** @param {Record<string, unknown>} c */
  function cardHtml(c) {
    const prioClass =
      c.priority === "cao" ? "is-high" : c.priority === "thap" ? "is-low" : "";
    const desc = truncate(c.description, 72);
    const pLabel = priority_labels[c.priority] || c.priority;
    const chLabel = dynamicChannelLabels[c.channel] || channel_labels[c.channel] || c.channel;
    const stage = casePipelineStage(c);
    const stLabel = pipeline_labels[stage] || c.pipeline_stage_label || stage;
    const slaBadge = c.sla_overdue
      ? '<span class="crm-pill crm-pill--sla" title="Quá SLA giai đoạn">SLA</span>'
      : "";
    const lastCare = c.last_care_report;
    const careBadge =
      lastCare && lastCare.care_status_label
        ? `<span class="crm-pill crm-pill--care" title="Báo cáo CSKH gần nhất">${esc(lastCare.care_status_label)}</span>`
        : viewMode === "mine"
          ? '<span class="crm-pill crm-pill--care-warn" title="Chưa có báo cáo CSKH">Chưa BC</span>'
          : "";
    return `
      <article
        class="crm-card ${prioClass}${c.sla_overdue ? " is-sla-overdue" : ""}"
        draggable="true"
        data-case-id="${c.id}"
        data-pipeline-stage="${escapeAttr(stage)}"
        role="button"
        tabindex="0"
        aria-label="${esc(c.title)} — ${esc(stLabel)}"
      >
        <div class="crm-card-top">
          <span class="crm-card-id">#${c.id}</span>
          <span class="crm-pill crm-pill--priority crm-pill--p-${escapeAttr(String(c.priority))}">${esc(pLabel)}</span>
          ${slaBadge}
          ${careBadge}
        </div>
        <p class="crm-card-title">${esc(c.title)}</p>
        <p class="crm-card-cust">
          <span class="crm-card-cust-name">${esc(c.customer_name)}</span>
        </p>
        ${
          desc
            ? `<p class="crm-card-desc">${esc(desc)}</p>`
            : '<p class="crm-card-desc crm-card-desc--empty">Chưa có mô tả</p>'
        }
        <div class="crm-card-footer">
          <span class="crm-chip-mini" title="Kênh">${esc(chLabel)}</span>
          ${
            c.assigned_to
              ? `<span class="crm-chip-mini crm-chip-mini--assign" title="Phụ trách">${esc(c.assigned_to)}</span>`
              : '<span class="crm-chip-mini crm-chip-mini--warn" title="Chưa gán">Chưa gán</span>'
          }
        </div>
      </article>
    `;
  }

  function applyClientFilters(cases) {
    let list = cases.slice();
    const q = (searchEl?.value || "").trim().toLowerCase();
    if (q) {
      const hayFn = (c) =>
        [
          "title",
          "description",
          "assigned_to",
          "customer_name",
          "customer_phone",
          "customer_email",
          "customer_address",
          "customer_company",
        ]
          .map((k) => String(c[k] ?? "").toLowerCase())
          .join(" ");
      list = list.filter((c) => hayFn(c).includes(q));
    }
    if (priorityFilter !== "all") {
      list = list.filter((c) => c.priority === priorityFilter);
    }
    if (staffPortal && portalStaffId) {
      list = list.filter((c) => Number(c.assigned_staff_id) === portalStaffId);
    } else if (viewMode === "mine" && myStaffId) {
      list = list.filter((c) => Number(c.assigned_staff_id) === myStaffId);
    }
    return list;
  }

  /** @param {Record<string, unknown>} c */
  function isTerminalCase(c) {
    return TERMINAL_STAGES.has(casePipelineStage(c));
  }

  /** @param {Record<string, unknown>[]} list */
  function applyCareTableFilter(list) {
    if (staffPortal || careTableFilter === "active") {
      return list.filter((c) => !isTerminalCase(c));
    }
    if (careTableFilter === "done") {
      return list.filter((c) => isTerminalCase(c));
    }
    return list;
  }

  /** @param {string} code */
  function careStatusClass(code) {
    const map = {
      da_lien_he_thanh_cong: "is-ok",
      da_tu_van_xong: "is-ok",
      hoan_tat: "is-done",
      khach_hen_goi_lai: "is-pending",
      cho_phan_hoi_khach: "is-pending",
      khong_lien_lac_duoc: "is-bad",
      chuyen_cap_truong: "is-escalate",
    };
    return map[code] || "is-neutral";
  }

  /** @param {Record<string, unknown>} c */
  function careStatusCell(c) {
    const lastCare = c.last_care_report;
    if (lastCare && lastCare.care_status_label) {
      const code = String(lastCare.care_status || "");
      const contact = lastCare.contact_type_label
        ? `<span class="crm-customers-care-meta">${esc(lastCare.contact_type_label)}</span>`
        : "";
      const when = lastCare.created_at
        ? `<span class="crm-customers-care-meta">${esc(formatViDateTime(String(lastCare.created_at)))}</span>`
        : "";
      return `
        <div class="crm-customers-care-cell">
          <span class="crm-care-status-pill ${careStatusClass(code)}">${esc(String(lastCare.care_status_label))}</span>
          ${contact}${when}
        </div>
      `;
    }
    return '<span class="crm-care-status-pill is-none">Chưa báo cáo</span>';
  }

  /** @param {Record<string, unknown>} c */
  function customerTableRow(c) {
    const stage = casePipelineStage(c);
    const stLabel = pipeline_labels[stage] || c.pipeline_stage_label || stage;
    const prioLabel = priority_labels[c.priority] || c.priority;
    const phone = String(c.customer_phone || "").trim();
    const email = String(c.customer_email || "").trim();
    const address = String(c.customer_address || "").trim();
    const company = String(c.customer_company || "").trim();
    const phoneCell = phone
      ? `<a href="tel:${escapeAttr(phone.replace(/\s/g, ""))}" class="crm-cu-link">${esc(phone)}</a>`
      : '<span class="muted">—</span>';
    const emailCell = email
      ? `<a href="mailto:${escapeAttr(email)}" class="crm-cu-link">${esc(email)}</a>`
      : '<span class="muted">—</span>';
    const addressCell = address
      ? `<span class="crm-cu-address">${esc(address)}</span>`
      : '<span class="muted">—</span>';
    const slaMark = c.sla_overdue
      ? ' <span class="crm-pill crm-pill--sla" title="Quá SLA">SLA</span>'
      : "";
    return `
      <tr class="crm-customers-row${c.sla_overdue ? " is-sla-overdue" : ""}" data-case-id="${c.id}" tabindex="0" role="button" aria-label="Mở hồ sơ ${esc(String(c.customer_name || c.title))}">
        <td class="crm-customers-col-id">#${c.id}</td>
        <td class="crm-customers-col-name">
          <strong class="crm-customers-name">${esc(String(c.customer_name || "—"))}</strong>
          ${company ? `<span class="crm-customers-company muted">${esc(company)}</span>` : ""}
        </td>
        <td class="crm-customers-col-phone">${phoneCell}</td>
        <td class="crm-customers-col-email">${emailCell}</td>
        <td class="crm-customers-col-address">${addressCell}</td>
        <td class="crm-customers-col-title">
          <span class="crm-customers-title">${esc(String(c.title || "—"))}</span>
          <span class="crm-pill crm-pill--priority crm-pill--p-${escapeAttr(String(c.priority))}">${esc(String(prioLabel))}</span>${slaMark}
        </td>
        <td><span class="crm-customers-stage crm-customers-stage--${escapeAttr(stage)}">${esc(String(stLabel))}</span></td>
        <td>${careStatusCell(c)}</td>
        <td class="crm-customers-col-assign">${c.assigned_to ? esc(String(c.assigned_to)) : '<span class="muted">Chưa gán</span>'}</td>
        <td class="crm-customers-col-updated">${esc(formatViDateTime(String(c.updated_at || "")))}</td>
        <td class="crm-staff-actions">
          <button type="button" class="btn-secondary crm-staff-row-action-btn crm-customers-open" data-case-id="${c.id}">Chi tiết</button>
        </td>
      </tr>
    `;
  }

  function renderCustomerTable() {
    if (!customersTbody) return;
    const base = applyClientFilters(cachedCases);
    const list = applyCareTableFilter(base);
    list.sort((a, b) => {
      const ta = String(a.updated_at || "");
      const tb = String(b.updated_at || "");
      return tb.localeCompare(ta);
    });

    if (customersSummaryEl) {
      if (staffPortal) {
        const noReport = list.filter((c) => !c.last_care_report).length;
        customersSummaryEl.textContent =
          list.length === 0
            ? "Bạn chưa có khách nào đang được gán chăm sóc."
            : `${list.length} khách đang chăm sóc${noReport ? ` · ${noReport} chưa báo cáo CSKH` : ""}.`;
      } else {
        const activeN = base.filter((c) => !isTerminalCase(c)).length;
        const noReport = base.filter(
          (c) => !isTerminalCase(c) && !c.last_care_report,
        ).length;
        customersSummaryEl.textContent = `${list.length} khách hiển thị · ${activeN} đang chăm sóc · ${noReport} chưa báo cáo CSKH.`;
      }
    }

    if (!list.length) {
      customersTbody.innerHTML = "";
      if (customersEmptyEl) customersEmptyEl.hidden = false;
      return;
    }
    if (customersEmptyEl) customersEmptyEl.hidden = true;
    customersTbody.innerHTML = list.map(customerTableRow).join("");

    customersTbody.querySelectorAll(".crm-customers-row").forEach((row) => {
      row.addEventListener("click", (ev) => {
        if (!(row instanceof HTMLElement) || !row.dataset.caseId) return;
        ev.preventDefault();
        openDetail(Number(row.dataset.caseId));
      });
      row.addEventListener("keydown", (ev) => {
        if (ev.key !== "Enter" && ev.key !== " ") return;
        if (!(row instanceof HTMLElement) || !row.dataset.caseId) return;
        ev.preventDefault();
        openDetail(Number(row.dataset.caseId));
      });
    });
  }

  function renderStats(filteredLen, totalLen) {
    const all = cachedCases;
    const terminal = new Set(["chot", "mat", "da_giai_quyet", "dong"]);
    setText("crm-stat-total", all.length);
    setText(
      "crm-stat-pipeline",
      all.filter((c) => !terminal.has(casePipelineStage(c))).length,
    );
    setText(
      "crm-stat-high",
      all.filter(
        (c) => c.priority === "cao" && !terminal.has(casePipelineStage(c)),
      ).length,
    );
    setText(
      "crm-stat-sla",
      all.filter((c) => c.sla_overdue && !terminal.has(casePipelineStage(c))).length,
    );
    setText(
      "crm-stat-unassigned",
      all.filter((c) => !c.assigned_staff_id && !terminal.has(casePipelineStage(c))).length,
    );

    if (filterSummaryEl) {
      const q = (searchEl?.value || "").trim();
      const staffNote =
        viewMode === "mine" && myStaffId
          ? " · khách của tôi"
          : viewMode === "mine"
            ? " · chọn nhân viên"
            : "";
      if (filteredLen === totalLen && !q && priorityFilter === "all" && viewMode === "all") {
        filterSummaryEl.textContent = "";
      } else {
        filterSummaryEl.textContent = `Hiển thị ${filteredLen} / ${totalLen} hồ sơ${staffNote}`;
      }
    }
  }

  function colEmptyHtml() {
    const hasFilter =
      (searchEl?.value || "").trim() !== "" || priorityFilter !== "all";
    return `<p class="crm-col-empty muted">${
      hasFilter ? "Không có hồ sơ khớp bộ lọc." : "Chưa có hồ sơ — kéo thẻ vào đây hoặc tạo yêu cầu mới."
    }</p>`;
  }

  function renderBoard() {
    if (!boardEl) return;
    const totalLen = cachedCases.length;
    const list = applyClientFilters(cachedCases);
    renderStats(list.length, totalLen);

    boardEl.innerHTML = pipeline_stages
      .map((st) => {
        const inCol = list.filter((c) => casePipelineStage(c) === st);
        const cardsHtml = inCol.length ? inCol.map(cardHtml).join("") : colEmptyHtml();
        return `
          <div class="crm-col crm-col--pipe-${escapeAttr(st)}" data-pipeline-stage="${escapeAttr(st)}">
            <header class="crm-col-head">
              <span class="crm-col-title">${esc(pipeline_labels[st] || st)}</span>
              <span class="crm-col-count">${inCol.length}</span>
            </header>
            <div class="crm-col-body" data-drop-pipeline="${escapeAttr(st)}" tabindex="-1">
              ${cardsHtml}
            </div>
          </div>
        `;
      })
      .join("");

    boardEl.querySelectorAll(".crm-card").forEach((el) => {
      el.addEventListener("click", (ev) => {
        if (!(ev.target instanceof HTMLElement)) return;
        const card = ev.target.closest(".crm-card");
        if (!card || !card.dataset.caseId) return;
        ev.preventDefault();
        openDetail(Number(card.dataset.caseId));
      });

      el.addEventListener("keydown", (ev) => {
        if (ev.key === "Enter" || ev.key === " ") {
          ev.preventDefault();
          const id = Number(el.getAttribute("data-case-id"));
          if (id) openDetail(id);
        }
      });

      el.addEventListener("dragstart", (ev) => {
        if (!(ev.target instanceof HTMLElement)) return;
        const cardEl = ev.target.closest(".crm-card");
        if (!cardEl?.dataset.caseId) return;
        ev.dataTransfer?.setData("text/plain", cardEl.dataset.caseId);
        ev.dataTransfer.effectAllowed = "move";
      });
    });

    boardEl.querySelectorAll(".crm-col-body").forEach((colBody) => {
      colBody.addEventListener("dragover", (ev) => {
        ev.preventDefault();
        ev.dataTransfer.dropEffect = "move";
        colBody.classList.add("is-drag-over");
      });
      colBody.addEventListener("dragleave", () => colBody.classList.remove("is-drag-over"));
      colBody.addEventListener("drop", async (ev) => {
        ev.preventDefault();
        colBody.classList.remove("is-drag-over");
        const id = Number(ev.dataTransfer?.getData("text/plain"));
        const dest = colBody.getAttribute("data-drop-pipeline");
        if (!id || !dest) return;
        const current = cachedCases.find((c) => c.id === id);
        if (!current || casePipelineStage(current) === dest) return;
        try {
          await reqJson(`/api/crm/cases/${id}`, {
            method: "PATCH",
            body: JSON.stringify({ pipeline_stage: dest }),
          });
          await reload();
          loadFunnel().catch(() => {});
        } catch (err) {
          alert(err instanceof Error ? err.message : "Không đổi được giai đoạn");
        }
      });
    });
    renderCustomerTable();
  }

  async function loadFunnel() {
    const updatedEl = document.getElementById("crm-funnel-updated");
    const kpisEl = document.getElementById("crm-funnel-kpis");
    const barsEl = document.getElementById("crm-funnel-bars");
    const bnEl = document.getElementById("crm-funnel-bottlenecks");
    if (!barsEl) return;
    try {
      const data = await reqJson("/api/crm/funnel/live");
      const totals = data.totals || {};
      const stages = Array.isArray(data.stages) ? data.stages : [];
      const maxCount = Math.max(1, ...stages.map((s) => Number(s.count || 0)));

      if (updatedEl) {
        updatedEl.textContent = data.generated_at
          ? `Cập nhật ${formatViDateTime(data.generated_at)} · tự làm mới 30s`
          : "—";
      }
      if (kpisEl) {
        const wr =
          totals.win_rate_pct != null ? `${totals.win_rate_pct}%` : "—";
        setText("crm-stat-winrate", wr);
        kpisEl.innerHTML = `
          <span class="crm-funnel-kpi"><strong>${totals.open_pipeline ?? 0}</strong> đang mở</span>
          <span class="crm-funnel-kpi crm-funnel-kpi--warn"><strong>${totals.sla_overdue ?? 0}</strong> quá SLA</span>
          <span class="crm-funnel-kpi"><strong>${totals.unassigned ?? 0}</strong> chưa gán</span>
        `;
      }

      barsEl.innerHTML = stages
        .map((s) => {
          const cnt = Number(s.count || 0);
          const pct = Math.round((cnt / maxCount) * 100);
          const conv =
            s.conversion_from_prev_pct != null
              ? `<span class="crm-funnel-conv">${s.conversion_from_prev_pct}%</span>`
              : "";
          const avg =
            s.avg_hours > 0
              ? `<span class="crm-funnel-avg">${s.avg_hours}h TB</span>`
              : "";
          return `
            <div class="crm-funnel-row" data-stage="${escapeAttr(String(s.stage))}">
              <span class="crm-funnel-label">${esc(s.label || s.stage)}</span>
              <div class="crm-funnel-bar-wrap" title="${cnt} lead · SLA ${s.sla_hours || 0}h">
                <div class="crm-funnel-bar" style="width:${pct}%"></div>
              </div>
              <span class="crm-funnel-count">${cnt}</span>
              ${conv}${avg}
            </div>
          `;
        })
        .join("");

      if (bnEl) {
        const bn = Array.isArray(data.bottlenecks) ? data.bottlenecks : [];
        if (!bn.length) {
          bnEl.hidden = true;
          bnEl.innerHTML = "";
        } else {
          bnEl.hidden = false;
          bnEl.innerHTML = `
            <p class="crm-funnel-bn-title">Điểm nghẽn phễu</p>
            <ul class="crm-funnel-bn-list">${bn
              .map(
                (b) =>
                  `<li><strong>${esc(b.label)}</strong> — ${b.count} lead, TB ${b.avg_hours}h (SLA ${b.sla_hours}h)</li>`,
              )
              .join("")}</ul>
          `;
        }
      }
    } catch {
      if (updatedEl) updatedEl.textContent = "Không tải được phễu.";
    }
  }

  /** @param {string} id @param {string|number} v */
  function setText(id, v) {
    const el = document.getElementById(id);
    if (el) el.textContent = String(v);
  }

  async function reload() {
    let url = "/api/crm/cases";
    if (viewMode === "mine" && myStaffId) {
      url += `?staff_id=${encodeURIComponent(String(myStaffId))}`;
    }
    const data = await reqJson(url);
    cachedCases = data.cases || [];
    renderBoard();
    if (!staffPortal) loadReminderStrip().catch(() => {});
    if (!staffPortal) loadFunnel().catch(() => {});
    loadStaffWorkspace().catch(() => {});
  }

  function openModal(root) {
    if (!(root instanceof HTMLElement)) return;
    root.removeAttribute("hidden");
    root.classList.add("is-open");
    root.setAttribute("aria-hidden", "false");
    document.body.style.overflow = "hidden";
  }

  function closeModal(root) {
    if (!(root instanceof HTMLElement)) return;
    root.classList.remove("is-open");
    root.setAttribute("aria-hidden", "true");
    document.body.style.overflow = "";
    window.setTimeout(() => {
      if (!root.classList.contains("is-open")) {
        root.setAttribute("hidden", "");
      }
    }, 220);
  }

  document.addEventListener("keydown", (e) => {
    if (e.key !== "Escape") return;
    if (modalCreate && modalCreate.classList.contains("is-open")) {
      closeModal(modalCreate);
    } else if (modalDetail && modalDetail.classList.contains("is-open")) {
      closeModal(modalDetail);
    }
  });

  document.querySelectorAll("[data-close-modal]").forEach((el) =>
    el.addEventListener("click", () => {
      if (!el.closest(".crm-modal-root")) return;
      closeModal(el.closest(".crm-modal-root"));
    }),
  );

  document.querySelectorAll(".crm-chip[data-priority-filter]").forEach((btn) => {
    btn.addEventListener("click", () => {
      priorityFilter = /** @type {typeof priorityFilter} */ (
        btn.getAttribute("data-priority-filter") || "all"
      );
      document.querySelectorAll(".crm-chip[data-priority-filter]").forEach((b) => {
        b.classList.toggle("is-active", b === btn);
      });
      renderBoard();
    });
  });

  document.querySelectorAll(".crm-chip[data-crm-care-filter]").forEach((btn) => {
    btn.addEventListener("click", () => {
      careTableFilter = /** @type {typeof careTableFilter} */ (
        btn.getAttribute("data-crm-care-filter") || "active"
      );
      document.querySelectorAll(".crm-chip[data-crm-care-filter]").forEach((b) => {
        b.classList.toggle("is-active", b === btn);
      });
      renderBoard();
    });
  });

  function openCreateCaseModal() {
    if (!modalCreate || !formCreate) return;
    if (createErr) createErr.hidden = true;
    formCreate.reset();
    try {
      populateCreateFormSelects();
      fillAssignSelects();
    } catch (_err) {
      /* vẫn mở modal nếu dropdown phụ thuộc meta chưa sẵn */
    }
    loadChannelsForSelects().catch(() => {});
    loadCampaignDropdowns().catch(() => {});
    const csel = document.getElementById("crm-create-assigned");
    if (csel) csel.value = "";
    openModal(modalCreate);
    formCreate.querySelector("input[name='customer_name']")?.focus();
  }

  document.getElementById("crm-open-create")?.addEventListener("click", openCreateCaseModal);
  document.querySelectorAll(".crm-add-open").forEach((btn) => {
    if (btn.id === "crm-open-create") return;
    btn.addEventListener("click", openCreateCaseModal);
  });

  formCreate?.addEventListener("submit", async (ev) => {
    ev.preventDefault();
    createErr.hidden = true;
    const fd = new FormData(formCreate);

    const phone = (fd.get("customer_phone") || "").toString().trim();
    const emailVal = (fd.get("customer_email") || "").toString().trim();
    if (!phone && !emailVal) {
      createErr.textContent = "Cần ít nhất số điện thoại hoặc email.";
      createErr.hidden = false;
      return;
    }

    try {
      const rawStaff = fd.get("assigned_staff_id");
      let assigned_staff_id = null;
      if (rawStaff != null && String(rawStaff).trim() !== "") {
        const n = Number(rawStaff);
        if (!Number.isNaN(n) && n > 0) assigned_staff_id = n;
      }
      const payload = /** @type {Record<string, unknown>} */ ({
        title: fd.get("title"),
        description: fd.get("description") || "",
        channel: fd.get("channel"),
        priority: fd.get("priority"),
        assigned_staff_id,
        customer: {
          name: fd.get("customer_name"),
          phone,
          email: emailVal,
          address: (fd.get("customer_address") || "").toString().trim(),
          company: fd.get("customer_company") || "",
        },
      });
      const rawCamp = fd.get("campaign_id");
      if (rawCamp != null && String(rawCamp).trim() !== "") {
        const nc = Number(rawCamp);
        if (!Number.isNaN(nc) && nc > 0) payload.campaign_id = nc;
      }
      await reqJson("/api/crm/cases", {
        method: "POST",
        body: JSON.stringify(payload),
      });
      closeModal(modalCreate);
      await reload();
    } catch (err) {
      createErr.textContent = err instanceof Error ? err.message : "Lỗi";
      createErr.hidden = false;
    }
  });

  async function openDetail(caseId) {
    detailLoading.innerHTML = DETAIL_SKELETON_HTML;
    detailLoading.hidden = false;
    detailBody.hidden = true;
    detailErr.hidden = true;
    detailOk.hidden = true;
    openModal(modalDetail);
    detailOk.textContent = "Đã lưu.";
    detailOk.hidden = true;

    const badgesEl = document.getElementById("crm-detail-badges");
    const kickerEl = document.getElementById("crm-detail-kicker");
    const avatarEl = document.getElementById("crm-detail-avatar");

    try {
      const c = await reqJson(`/api/crm/cases/${caseId}`);

      if (badgesEl) {
        badgesEl.innerHTML = `
          <span class="crm-badge crm-badge--muted">#${c.id}</span>
          <span class="crm-badge crm-badge--status">${esc(pipeline_labels[casePipelineStage(c)] || c.pipeline_stage_label || c.status)}</span>
          <span class="crm-badge crm-badge--priority crm-badge--p-${escapeAttr(String(c.priority))}">${esc(
          priority_labels[c.priority] || c.priority,
        )}</span>
          <span class="crm-badge crm-badge--channel">${esc(channel_labels[c.channel] || c.channel)}</span>
          ${
            c.campaign_id && (c.campaign_name || c.campaign_code)
              ? (() => {
                  const code = String(c.campaign_code || "").trim();
                  const nm = String(c.campaign_name || "").trim();
                  const label = [code, nm].filter(Boolean).join(" — ");
                  return `<span class="crm-badge crm-badge--muted" title="Chiến dịch">${esc(label)}</span>`;
                })()
              : ""
          }
        `;
        badgesEl.hidden = false;
      }
      if (kickerEl) {
        const upd = formatViDateTime(c.updated_at);
        const asg = (c.assigned_at && String(c.assigned_at).trim()) || "";
        kickerEl.textContent = asg
          ? `Phân công ${formatViDateTime(asg)} · Cập nhật ${upd}`
          : `Cập nhật ${upd}`;
      }
      if (avatarEl) {
        avatarEl.textContent = customerInitials(c.customer_name);
      }

      await loadCampaignDropdowns(c.campaign_id);
      await loadChannelsForSelects(c.channel);

      const custEl = document.getElementById("crm-detail-customer");
      custEl.innerHTML = [
        ["Họ tên", c.customer_name],
        ["SĐT", c.customer_phone || "—"],
        ["Email", c.customer_email || "—"],
        ["Địa chỉ", c.customer_address || "—"],
        ["Công ty", c.customer_company || "—"],
      ]
        .map(
          ([k, v]) =>
            `<li><span class="crm-k">${esc(k)}</span><span class="crm-v">${esc(v)}</span></li>`,
        )
        .join("");

      formDetail.elements.case_id.value = String(c.id);
      const pipeSel = document.getElementById("crm-detail-pipeline");
      if (pipeSel instanceof HTMLSelectElement) {
        pipeSel.value = casePipelineStage(c);
      }
      formDetail.elements.status.value = String(c.status);
      formDetail.elements.priority.value = String(c.priority);
      formDetail.elements.channel.value = String(c.channel);
      fillAssignSelects(c.assigned_staff_id);
      formDetail.elements.title.value = String(c.title || "");
      formDetail.elements.description.value = String(c.description || "");
      const dealEl = document.getElementById("crm-detail-deal");
      if (dealEl instanceof HTMLInputElement) {
        dealEl.value =
          c.deal_value_vnd != null && c.deal_value_vnd !== ""
            ? String(c.deal_value_vnd)
            : "";
      }

      formNote.elements.case_id.value = String(c.id);
      if (formCareReport) {
        formCareReport.elements.case_id.value = String(c.id);
        const careStaffEl = document.getElementById("crm-care-staff-id");
        if (careStaffEl instanceof HTMLInputElement) {
          careStaffEl.value =
            myStaffId != null
              ? String(myStaffId)
              : c.assigned_staff_id != null
                ? String(c.assigned_staff_id)
                : "";
        }
      }

      const evEl = document.getElementById("crm-detail-events");
      const events = Array.isArray(c.events) ? c.events : [];
      const careReports = Array.isArray(c.care_reports) ? c.care_reports : [];
      const timelineItems = [
        ...events.map((e) => ({ type: "event", data: e })),
        ...careReports.map((r) => ({ type: "care", data: r })),
      ].sort((a, b) => {
        const ta = String(a.data.created_at || "");
        const tb = String(b.data.created_at || "");
        return ta.localeCompare(tb);
      });
      evEl.innerHTML = timelineItems.length
        ? timelineItems
            .map((item) => {
              if (item.type === "care") {
                const r = item.data;
                return `
            <li class="crm-ev crm-ev-care">
              <div class="crm-ev-dot" aria-hidden="true"></div>
              <div class="crm-ev-body">
                <time datetime="${esc(r.created_at)}">${esc(formatViDateTime(r.created_at))}</time>
                <p><strong>${esc(r.care_status_label || r.care_status)}</strong> · ${esc(r.contact_type_label || r.contact_type)}${r.staff_name ? ` · ${esc(r.staff_name)}` : ""}</p>
                <p>${esc(r.summary)}</p>
                ${r.next_action ? `<p class="crm-ev-next muted">Bước tiếp: ${esc(r.next_action)}</p>` : ""}
              </div>
            </li>`;
              }
              const e = item.data;
              const k = String(e.kind);
              const evExtra =
                k === "trang_thai" || k === "pipeline"
                  ? "crm-ev-status"
                  : k === "phan_cong"
                    ? "crm-ev-assignment"
                    : k === "bao_cao_cskh"
                      ? "crm-ev-care"
                      : "";
              return `
            <li class="crm-ev ${evExtra}">
              <div class="crm-ev-dot" aria-hidden="true"></div>
              <div class="crm-ev-body">
                <time datetime="${esc(e.created_at)}">${esc(formatViDateTime(e.created_at))}</time>
                <p>${esc(e.body)}</p>
              </div>
            </li>`;
            })
            .join("")
        : '<li class="crm-ev-muted crm-ev-empty">Chưa có báo cáo hay ghi chú.</li>';

      document.getElementById("crm-detail-title").textContent =
        String(c.title || "Chi tiết yêu cầu");
      detailLoading.hidden = true;
      detailBody.hidden = false;
    } catch {
      detailLoading.innerHTML = `<p class="crm-detail-load-msg">Không tải được dữ liệu. Thử lại sau.</p>`;
      detailLoading.hidden = false;
      detailBody.hidden = true;
      if (badgesEl) badgesEl.hidden = true;
    }
  }

  formDetail?.addEventListener("submit", async (ev) => {
    ev.preventDefault();
    detailErr.hidden = true;
    detailOk.hidden = true;
    const fd = new FormData(formDetail);
    const id = fd.get("case_id");
    if (!id) return;
    const rawStaff = fd.get("assigned_staff_id");
    let assigned_staff_id = null;
    if (rawStaff != null && String(rawStaff).trim() !== "") {
      const n = Number(rawStaff);
      if (!Number.isNaN(n) && n > 0) assigned_staff_id = n;
    }
    const rawCamp = fd.get("campaign_id");
    let campaign_id = 0;
    if (rawCamp != null && String(rawCamp).trim() !== "") {
      const n = Number(rawCamp);
      if (!Number.isNaN(n) && n > 0) campaign_id = n;
    }
    const rawDeal = fd.get("deal_value_vnd");
    let deal_value_vnd = null;
    if (rawDeal != null && String(rawDeal).trim() !== "") {
      const n = Number(rawDeal);
      if (!Number.isNaN(n) && n >= 0) deal_value_vnd = n;
    }
    const pipeStage = fd.get("pipeline_stage");
    try {
      await reqJson(`/api/crm/cases/${id}`, {
        method: "PATCH",
        body: JSON.stringify({
          pipeline_stage: pipeStage,
          status: fd.get("status"),
          priority: fd.get("priority"),
          channel: fd.get("channel"),
          assigned_staff_id,
          title: fd.get("title"),
          description: fd.get("description") || "",
          campaign_id: campaign_id || 0,
          deal_value_vnd,
        }),
      });
      detailOk.hidden = false;
      await reload();
      await openDetail(Number(id));
    } catch (err) {
      detailErr.textContent = err instanceof Error ? err.message : "Không lưu được.";
      detailErr.hidden = false;
    }
  });

  formNote?.addEventListener("submit", async (ev) => {
    ev.preventDefault();
    detailErr.hidden = true;
    const fd = new FormData(formNote);
    const id = fd.get("case_id");
    const bodyTxt = fd.get("body");
    if (!id || !(bodyTxt && String(bodyTxt).trim())) return;
    try {
      await reqJson(`/api/crm/cases/${id}/events`, {
        method: "POST",
        body: JSON.stringify({ body: String(bodyTxt).trim() }),
      });
      formNote.reset();
      formNote.elements.case_id.value = String(id);
      await reload();
      await openDetail(Number(id));
    } catch (err) {
      detailErr.textContent = err instanceof Error ? err.message : "Không thêm được ghi chú.";
      detailErr.hidden = false;
    }
  });

  formCareReport?.addEventListener("submit", async (ev) => {
    ev.preventDefault();
    detailErr.hidden = true;
    detailOk.hidden = true;
    const fd = new FormData(formCareReport);
    const id = fd.get("case_id");
    const summary = (fd.get("summary") || "").toString().trim();
    if (!id || !summary) return;
    const rawStaff = fd.get("staff_id");
    let staff_id = null;
    if (rawStaff != null && String(rawStaff).trim() !== "") {
      const n = Number(rawStaff);
      if (!Number.isNaN(n) && n > 0) staff_id = n;
    }
    if (!staff_id && myStaffId) staff_id = myStaffId;
    try {
      await reqJson(`/api/crm/cases/${id}/care-reports`, {
        method: "POST",
        body: JSON.stringify({
          summary,
          contact_type: fd.get("contact_type"),
          care_status: fd.get("care_status"),
          next_action: fd.get("next_action") || "",
          staff_id,
        }),
      });
      formCareReport.reset();
      formCareReport.elements.case_id.value = String(id);
      detailOk.textContent = "Đã gửi báo cáo chăm sóc.";
      detailOk.hidden = false;
      await reload();
      await openDetail(Number(id));
    } catch (err) {
      detailErr.textContent = err instanceof Error ? err.message : "Không gửi được báo cáo.";
      detailErr.hidden = false;
    }
  });

  myStaffSelect?.addEventListener("change", async () => {
    const v = myStaffSelect.value;
    myStaffId = v ? Number(v) : null;
    if (v) localStorage.setItem(STAFF_STORAGE_KEY, v);
    else localStorage.removeItem(STAFF_STORAGE_KEY);
    await reload();
  });

  document.querySelectorAll("[data-crm-view]").forEach((btn) => {
    btn.addEventListener("click", async () => {
      const mode = btn.getAttribute("data-crm-view");
      viewMode = mode === "all" ? "all" : "mine";
      document.querySelectorAll("[data-crm-view]").forEach((b) => {
        b.classList.toggle("is-active", b === btn);
      });
      await reload();
    });
  });

  searchEl?.addEventListener("input", () => {
    window.clearTimeout(searchDebounceTimer);
    searchDebounceTimer = window.setTimeout(() => renderBoard(), 80);
  });

  loadStaffForSelects().catch(() => {});
  if (staffPortal) {
    document.getElementById("crm-stats")?.setAttribute("hidden", "hidden");
    const sub = document.querySelector(".crm-staff-workspace-sub");
    if (sub) {
      sub.textContent =
        "Chỉ hiển thị khách được gán cho bạn và đang trong pipeline chăm sóc.";
    }
  }
  loadChannelsForSelects().catch(() => {});
  loadCampaignDropdowns().catch(() => {});
  reload().catch(() => {
    boardEl.innerHTML =
      '<p class="crm-load-fail muted">Không tải được danh sách. Kiểm tra máy chủ hoặc tải lại trang.</p>';
  });
  const openCaseParam = new URLSearchParams(window.location.search).get("open_case");
  if (openCaseParam) {
    const cid = Number(openCaseParam);
    if (cid > 0) {
      reload()
        .then(() => openDetail(cid))
        .catch(() => {});
    }
  }
  window.setInterval(() => {
    if (!staffPortal) loadFunnel().catch(() => {});
  }, 30000);
})();
