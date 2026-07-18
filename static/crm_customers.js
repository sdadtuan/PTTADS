(function () {
  window.addEventListener("pageshow", (ev) => {
    if (ev.persisted) window.location.reload();
  });

  const metaEl = document.getElementById("crm-cu-meta");
  const meta = metaEl ? JSON.parse(metaEl.textContent) : {};
  const pipelineLabels = meta.pipeline_labels || {};
  const careStatusLabels = meta.care_status_labels || {};
  const careContactLabels = meta.care_contact_labels || {};
  const contractStatusLabels = meta.contract_status_labels || {};
  const leadSourceLabels = meta.lead_sources || {};
  const genderLabels = meta.genders || {};
  const relationTypeLabels = meta.relation_types || {};
  const purchaseStatusLabels = meta.purchase_statuses || {};
  const issueTypeLabels = meta.issue_types || {};
  const issueStatusLabels = meta.issue_statuses || {};
  const issuePriorityLabels = meta.issue_priorities || {};
  const staffPortal = Boolean(meta.staff_portal);

  const cardListEl = document.getElementById("crm-cu-card-list");
  const emptyEl = document.getElementById("crm-cu-empty");
  const searchEl = document.getElementById("crm-cu-search");
  const summaryEl = document.getElementById("crm-cu-filter-summary");
  const detailEmpty = document.getElementById("crm-cu-detail-empty");
  const detailPanel = document.getElementById("crm-cu-detail-panel");
  const detailPane = document.getElementById("crm-cu-detail-pane");
  const profileForm = document.getElementById("crm-cu-profile-form");
  const demoForm = document.getElementById("crm-cu-demographics-form");
  const careForm = document.getElementById("crm-cu-care-form");
  const createForm = document.getElementById("crm-cu-create-form");
  const modalCreate = document.getElementById("crm-cu-modal-create");
  const relationForm = document.getElementById("crm-cu-relation-form");
  const purchaseForm = document.getElementById("crm-cu-purchase-form");
  const issueForm = document.getElementById("crm-cu-issue-form");

  const MOBILE_BP = 960;

  /** @type {Array<Record<string, unknown>>} */
  let cachedCustomers = [];
  /** @type {Record<string, unknown>|null} */
  let activeCustomer = null;
  /** @type {"active"|"all"} */
  let listFilter = staffPortal ? "active" : "active";
  /** @type {number|null} */
  let activeCustomerId = null;
  let searchTimer;

  function isMobileLayout() {
    return window.matchMedia(`(max-width: ${MOBILE_BP}px)`).matches;
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
    if (res.status === 401 && typeof data.login === "string") {
      window.location.href = data.login;
      throw new Error("Chưa đăng nhập");
    }
    if (!res.ok) throw new Error(data.error || res.statusText || "Lỗi mạng");
    return data;
  }

  function esc(s) {
    const d = document.createElement("div");
    d.textContent = s ?? "";
    return d.innerHTML;
  }

  function escapeAttr(s) {
    return esc(s).replace(/"/g, "&quot;");
  }

  function formatViDateTime(isoLike) {
    const raw = String(isoLike || "");
    const m = raw.match(/^(\d{4})-(\d{2})-(\d{2})[ T](\d{2}):(\d{2})/);
    if (!m) return raw ? raw.slice(0, 10) : "—";
    const [, y, mo, d, h, mi] = m;
    return `${d}/${mo}/${y} · ${h}:${mi}`;
  }

  function initials(name) {
    const parts = String(name || "")
      .trim()
      .split(/\s+/)
      .filter(Boolean);
    if (!parts.length) return "?";
    if (parts.length === 1) return parts[0].slice(0, 2).toUpperCase();
    return (parts[0][0] + parts[parts.length - 1][0]).toUpperCase();
  }

  const AVATAR_PALETTE = [
    ["#398b43", "#2f7238"],
    ["#2563eb", "#1d4ed8"],
    ["#7c3aed", "#6d28d9"],
    ["#db2777", "#be185d"],
    ["#ea580c", "#c2410c"],
    ["#0891b2", "#0e7490"],
    ["#4f46e5", "#4338ca"],
    ["#059669", "#047857"],
  ];

  function avatarStyle(name) {
    const s = String(name || "");
    let h = 0;
    for (let i = 0; i < s.length; i += 1) h = (h * 31 + s.charCodeAt(i)) >>> 0;
    const [a, b] = AVATAR_PALETTE[h % AVATAR_PALETTE.length];
    return `background:linear-gradient(135deg,${a},${b})`;
  }

  function formatTimeAgo(isoLike) {
    const raw = String(isoLike || "");
    const m = raw.match(/^(\d{4})-(\d{2})-(\d{2})/);
    if (!m) return "";
    const dt = new Date(`${m[1]}-${m[2]}-${m[3]}T00:00:00`);
    const diff = Date.now() - dt.getTime();
    const days = Math.floor(diff / 86400000);
    if (days < 0) return "";
    if (days === 0) return "Hôm nay";
    if (days === 1) return "Hôm qua";
    if (days < 7) return `${days} ngày trước`;
    if (days < 30) return `${Math.floor(days / 7)} tuần trước`;
    return formatViDateTime(raw).slice(0, 10);
  }

  function carePillClass(code) {
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

  function issuePillClass(status) {
    const map = {
      moi: "is-bad",
      dang_xu_ly: "is-pending",
      cho_khach: "is-pending",
      da_xu_ly: "is-ok",
      dong: "is-done",
    };
    return map[String(status)] || "is-neutral";
  }

  function setStats(stats) {
    const s = stats || {};
    const set = (id, v) => {
      const el = document.getElementById(id);
      if (el) el.textContent = String(v ?? 0);
    };
    set("crm-cu-stat-total", s.total);
    set("crm-cu-stat-active", s.active_care);
    set("crm-cu-stat-issues", s.issues_open);
    set("crm-cu-stat-contracts", s.with_contracts);
  }

  function applyLocalFilter(list) {
    if (listFilter === "active") {
      return list.filter((c) => Number(c.cases_open || 0) > 0);
    }
    return list;
  }

  function customerCard(c) {
    const phone = String(c.phone || "").trim();
    const email = String(c.email || "").trim();
    const issuesOpen = Number(c.issues_open || 0);
    const casesOpen = Number(c.cases_open || 0);
    const stage = escapeAttr(String(c.primary_pipeline_stage || "none"));
    const stageLabel = esc(String(c.primary_pipeline_label || "Chưa gán"));
    const srcLabel = String(c.lead_source_label || "").trim();
    const careLabel = c.last_care_status_label
      ? `<span class="crm-care-status-pill ${carePillClass(String(c.last_care_status))}">${esc(String(c.last_care_status_label))}</span>`
      : "";
    const isSelected = activeCustomerId === Number(c.id);
    const name = String(c.name || "—");
    const avStyle = avatarStyle(name);
    const updated = formatTimeAgo(String(c.last_case_updated || c.created_at || ""));

    return `
      <article class="crm-cu-card${isSelected ? " is-selected" : ""}" data-customer-id="${c.id}" role="listitem" tabindex="0">
        <div class="crm-cu-card-avatar" style="${avStyle}" aria-hidden="true">${esc(initials(name))}</div>
        <div class="crm-cu-card-body">
          <div class="crm-cu-card-top">
            <strong class="crm-cu-card-name">${esc(name)}</strong>
            ${updated ? `<time class="crm-cu-card-time muted">${esc(updated)}</time>` : ""}
          </div>
          ${c.company ? `<p class="crm-cu-card-company muted">${esc(String(c.company))}</p>` : ""}
          <div class="crm-cu-card-contact-row">
            ${phone ? `<span class="crm-cu-card-chip"><svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M22 16.92v3a2 2 0 0 1-2.18 2 19.79 19.79 0 0 1-8.63-3.07 19.5 19.5 0 0 1-6-6 19.79 19.79 0 0 1-3.07-8.67A2 2 0 0 1 4.11 2h3a2 2 0 0 1 2 1.72 12.84 12.84 0 0 0 .7 2.81 2 2 0 0 1-.45 2.11L8.09 9.91a16 16 0 0 0 6 6l1.27-1.27a2 2 0 0 1 2.11-.45 12.84 12.84 0 0 0 2.81.7A2 2 0 0 1 22 16.92z"/></svg>${esc(phone)}</span>` : ""}
            ${email ? `<span class="crm-cu-card-chip crm-cu-card-chip--email"><svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M4 4h16c1.1 0 2 .9 2 2v12c0 1.1-.9 2-2 2H4c-1.1 0-2-.9-2-2V6c0-1.1.9-2 2-2z"/><polyline points="22,6 12,13 2,6"/></svg>${esc(email)}</span>` : ""}
            ${!phone && !email ? '<span class="muted crm-cu-card-no-contact">Chưa có liên hệ</span>' : ""}
          </div>
          <div class="crm-cu-card-foot">
            <span class="crm-customers-stage crm-customers-stage--${stage}">${stageLabel}</span>
            ${srcLabel ? `<span class="crm-cu-source-pill">${esc(srcLabel)}</span>` : ""}
            ${careLabel}
            ${issuesOpen ? `<span class="crm-cu-issue-badge">${issuesOpen}</span>` : ""}
            ${casesOpen ? `<span class="crm-cu-card-cases muted">${casesOpen} HS</span>` : ""}
            <button class="btn btn--sm" onclick="event.stopPropagation();window.openBriefPanel(${c.id},${JSON.stringify(esc(name))})" title="Meeting Brief" style="padding:.2rem .4rem;font-size:.75rem;">📋</button>
            <a href="/crm/customers/${c.id}/lifecycle/new" onclick="event.stopPropagation()" class="btn btn--sm" title="Tạo Lifecycle" style="padding:.2rem .4rem;font-size:.75rem;text-decoration:none;">⚡ LC</a>
          </div>
        </div>
      </article>
    `;
  }

  function renderLoadingSkeleton() {
    if (!cardListEl) return;
    cardListEl.innerHTML = Array.from({ length: 6 })
      .map(
        () => `
        <div class="crm-cu-card crm-cu-card--skeleton" aria-hidden="true">
          <div class="crm-cu-skeleton crm-cu-skeleton--avatar"></div>
          <div class="crm-cu-skeleton-body">
            <div class="crm-cu-skeleton crm-cu-skeleton--line crm-cu-skeleton--w70"></div>
            <div class="crm-cu-skeleton crm-cu-skeleton--line crm-cu-skeleton--w50"></div>
            <div class="crm-cu-skeleton crm-cu-skeleton--line crm-cu-skeleton--w90"></div>
          </div>
        </div>`,
      )
      .join("");
  }

  function renderList() {
    if (!cardListEl) return;
    const list = applyLocalFilter(cachedCustomers);
    if (summaryEl) {
      summaryEl.textContent = list.length ? `${list.length} khách hàng` : "";
    }
    if (!list.length) {
      cardListEl.innerHTML = "";
      if (emptyEl) emptyEl.hidden = false;
      return;
    }
    if (emptyEl) emptyEl.hidden = true;
    cardListEl.innerHTML = list.map(customerCard).join("");
    cardListEl.querySelectorAll(".crm-cu-card").forEach((el) => {
      el.addEventListener("click", () => {
        const id = el instanceof HTMLElement ? el.dataset.customerId : null;
        if (id) openCustomer(Number(id));
      });
      el.addEventListener("keydown", (ev) => {
        if (ev.key !== "Enter" && ev.key !== " ") return;
        if (!(el instanceof HTMLElement) || !el.dataset.customerId) return;
        ev.preventDefault();
        openCustomer(Number(el.dataset.customerId));
      });
    });
  }

  async function reload() {
    const q = (searchEl?.value || "").trim();
    renderLoadingSkeleton();
    const params = new URLSearchParams({ overview: "1", limit: "300" });
    if (q) params.set("q", q);
    if (listFilter === "active" || staffPortal) params.set("active_only", "1");
    const data = await reqJson(`/api/crm/customers?${params}`);
    cachedCustomers = data.customers || [];
    setStats(data.stats);
    renderList();
  }

  function fillSelect(sel, map, emptyOption) {
    if (!(sel instanceof HTMLSelectElement)) return;
    sel.innerHTML = "";
    if (emptyOption) {
      const opt = document.createElement("option");
      opt.value = "";
      opt.textContent = emptyOption;
      sel.appendChild(opt);
    }
    Object.entries(map).forEach(([k, label]) => {
      const opt = document.createElement("option");
      opt.value = k;
      opt.textContent = label;
      sel.appendChild(opt);
    });
  }

  function setFormReadOnly(form, readOnly) {
    if (!form) return;
    form.querySelectorAll("input, textarea, select, button[type='submit']").forEach((el) => {
      if (el instanceof HTMLButtonElement && el.type === "submit") {
        el.disabled = readOnly;
        return;
      }
      if (el instanceof HTMLSelectElement) el.disabled = readOnly;
      else if (el instanceof HTMLInputElement || el instanceof HTMLTextAreaElement) {
        el.readOnly = readOnly;
      }
    });
  }

  function switchTab(tabId) {
    document.querySelectorAll(".crm-cu-nav-item").forEach((btn) => {
      const on = btn.getAttribute("data-cu-tab") === tabId;
      btn.classList.toggle("is-active", on);
      btn.setAttribute("aria-selected", on ? "true" : "false");
    });
    document.querySelectorAll(".crm-cu-tab-panel").forEach((panel) => {
      const on = panel.getAttribute("data-cu-panel") === tabId;
      panel.classList.toggle("is-active", on);
      panel.hidden = !on;
    });
  }

  function renderSources(sources) {
    const wrap = document.getElementById("crm-cu-source-tags");
    const list = document.getElementById("crm-cu-source-list");
    if (!wrap || !list) return;
    const items = sources || [];
    if (!items.length) {
      wrap.hidden = true;
      return;
    }
    wrap.hidden = false;
    list.innerHTML = items
      .map(
        (s) =>
          `<li><span class="crm-cu-source-pill">${esc(String(s.label || ""))}</span> <span class="muted">${esc(String(s.origin || ""))}</span></li>`,
      )
      .join("");
  }

  function renderRelations(relations) {
    const el = document.getElementById("crm-cu-relations-list");
    if (!el) return;
    const list = relations || [];
    if (!list.length) {
      el.innerHTML = '<p class="crm-cu-empty-hint muted">Chưa có người liên hệ / quan hệ gia đình.</p>';
      return;
    }
    el.innerHTML = list
      .map(
        (r) => `
        <article class="crm-cu-relation-card panel" data-relation-id="${r.id}">
          <div class="crm-cu-relation-head">
            <strong>${esc(String(r.full_name || ""))}</strong>
            <span class="crm-cu-source-pill">${esc(String(r.relation_type_label || r.relation_type || ""))}</span>
          </div>
          <p class="muted">${[r.phone, r.email].filter(Boolean).map(String).join(" · ") || "—"}</p>
          ${r.notes ? `<p>${esc(String(r.notes))}</p>` : ""}
          ${staffPortal ? "" : `<button type="button" class="btn-secondary btn-sm crm-cu-relation-edit" data-id="${r.id}">Sửa</button>`}
        </article>
      `,
      )
      .join("");
    el.querySelectorAll(".crm-cu-relation-edit").forEach((btn) => {
      btn.addEventListener("click", () => {
        const id = Number(btn.getAttribute("data-id"));
        const row = list.find((x) => Number(x.id) === id);
        if (!row || !relationForm) return;
        relationForm.hidden = false;
        relationForm.elements.relation_id.value = String(id);
        relationForm.elements.relation_type.value = String(row.relation_type || "other");
        relationForm.elements.full_name.value = String(row.full_name || "");
        relationForm.elements.phone.value = String(row.phone || "");
        relationForm.elements.email.value = String(row.email || "");
        relationForm.elements.notes.value = String(row.notes || "");
      });
    });
  }

  function renderPurchases(purchases) {
    const el = document.getElementById("crm-cu-purchases-list");
    if (!el) return;
    const list = purchases || [];
    if (!list.length) {
      el.innerHTML = '<p class="crm-cu-empty-hint muted">Chưa có lịch sử mua hàng.</p>';
      return;
    }
    el.innerHTML = list
      .map((p) => {
        const amt = Number(p.amount_vnd || 0);
        const amtTxt = amt ? `${amt.toLocaleString("vi-VN")} ₫` : "—";
        return `
          <article class="crm-cu-purchase-card panel">
            <div class="crm-cu-purchase-head">
              <strong>${esc(String(p.product_name || ""))}</strong>
              <span class="crm-cu-source-pill">${esc(String(p.status_label || p.status || ""))}</span>
            </div>
            <p class="muted">${esc(String(p.order_date || p.created_at || "").slice(0, 10))} · SL ${Number(p.quantity || 1)} · ${amtTxt}</p>
            ${p.reference_code ? `<p class="muted">Mã: ${esc(String(p.reference_code))}</p>` : ""}
            ${p.notes ? `<p>${esc(String(p.notes))}</p>` : ""}
          </article>
        `;
      })
      .join("");
  }

  function renderIssues(issues) {
    const el = document.getElementById("crm-cu-issues-list");
    if (!el) return;
    const list = issues || [];
    if (!list.length) {
      el.innerHTML = '<p class="crm-cu-empty-hint muted">Chưa có phản ánh / khiếu nại.</p>';
      return;
    }
    el.innerHTML = list
      .map((i) => {
        const st = String(i.status || "");
        const canEdit = !staffPortal || st !== "dong";
        return `
          <article class="crm-cu-issue-card panel" data-issue-id="${i.id}">
            <div class="crm-cu-issue-head">
              <strong>${esc(String(i.title || ""))}</strong>
              <span class="crm-care-status-pill ${issuePillClass(st)}">${esc(String(i.status_label || st))}</span>
            </div>
            <p class="muted">${esc(String(i.issue_type_label || ""))} · ${esc(String(i.priority_label || ""))} · ${esc(formatViDateTime(String(i.created_at || "")))}</p>
            <p>${esc(String(i.description || ""))}</p>
            ${i.resolution ? `<p class="muted">Xử lý: ${esc(String(i.resolution))}</p>` : ""}
            ${i.assigned_staff_name ? `<p class="muted">NV: ${esc(String(i.assigned_staff_name))}</p>` : ""}
            ${canEdit ? `
              <div class="crm-cu-issue-actions">
                <select class="crm-cu-issue-status-select" data-issue-id="${i.id}" aria-label="Cập nhật trạng thái">
                  ${Object.entries(issueStatusLabels)
                    .map(
                      ([k, lbl]) =>
                        `<option value="${escapeAttr(k)}"${k === st ? " selected" : ""}>${esc(lbl)}</option>`,
                    )
                    .join("")}
                </select>
                <input type="text" class="crm-cu-issue-resolution" data-issue-id="${i.id}" placeholder="Ghi chú xử lý" value="${escapeAttr(String(i.resolution || ""))}" />
                <button type="button" class="btn-secondary crm-cu-issue-save" data-issue-id="${i.id}">Cập nhật</button>
              </div>
            ` : ""}
          </article>
        `;
      })
      .join("");
    el.querySelectorAll(".crm-cu-issue-save").forEach((btn) => {
      btn.addEventListener("click", async () => {
        const iid = Number(btn.getAttribute("data-issue-id"));
        if (!activeCustomerId || !iid) return;
        const card = btn.closest(".crm-cu-issue-card");
        const sel = card?.querySelector(".crm-cu-issue-status-select");
        const resInp = card?.querySelector(".crm-cu-issue-resolution");
        try {
          await reqJson(`/api/crm/customers/${activeCustomerId}/issues/${iid}`, {
            method: "PATCH",
            body: JSON.stringify({
              status: sel instanceof HTMLSelectElement ? sel.value : undefined,
              resolution: resInp instanceof HTMLInputElement ? resInp.value : "",
            }),
          });
          await reload();
          await openCustomer(activeCustomerId);
          switchTab("issues");
        } catch (e) {
          window.alert(e instanceof Error ? e.message : "Lỗi");
        }
      });
    });
  }

  function renderCases(cases) {
    const el = document.getElementById("crm-cu-cases-list");
    if (!el) return;
    if (!cases.length) {
      el.innerHTML = '<p class="crm-cu-empty-hint muted">Chưa có hồ sơ CSKH.</p>';
      return;
    }
    el.innerHTML = cases
      .map((c) => {
        const stage = esc(String(c.pipeline_stage_label || c.pipeline_stage || ""));
        const care = c.last_care_report?.care_status_label
          ? esc(String(c.last_care_report.care_status_label))
          : "Chưa báo cáo";
        return `
          <article class="crm-cu-case-card panel">
            <div class="crm-cu-case-head">
              <h3>${esc(String(c.title || "Hồ sơ"))}</h3>
              <span class="crm-customers-stage">${stage}</span>
            </div>
            <p class="muted crm-cu-case-meta">
              #${c.id} · ${esc(String(c.assigned_to || "Chưa gán"))} · CSKH: ${care}
            </p>
            <div class="crm-cu-case-actions">
              <a class="btn-secondary btn-sm crm-staff-row-action-btn" href="/crm?open_case=${c.id}">Mở Bảng CSKH</a>
            </div>
          </article>
        `;
      })
      .join("");
  }

  function renderCareTimeline(reports) {
    const el = document.getElementById("crm-cu-care-timeline");
    if (!el) return;
    if (!reports.length) {
      el.innerHTML = '<li class="muted crm-cu-empty-hint">Chưa có báo cáo chăm sóc.</li>';
      return;
    }
    el.innerHTML = reports
      .map(
        (r) => `
        <li class="crm-cu-care-item">
          <time>${esc(formatViDateTime(String(r.created_at || "")))}</time>
          <p><strong>${esc(String(r.care_status_label || r.care_status))}</strong> · ${esc(String(r.contact_type_label || ""))}</p>
          <p>${esc(String(r.summary || ""))}</p>
          ${r.next_action ? `<p class="muted">Tiếp: ${esc(String(r.next_action))}</p>` : ""}
          ${r.case_title ? `<p class="muted">Hồ sơ: ${esc(String(r.case_title))}</p>` : ""}
        </li>
      `,
      )
      .join("");
  }

  function renderContracts(contracts) {
    const el = document.getElementById("crm-cu-contracts-list");
    if (!el) return;
    if (!contracts.length) {
      el.innerHTML = '<p class="crm-cu-empty-hint muted">Chưa có hợp đồng.</p>';
      return;
    }
    el.innerHTML = contracts
      .map((ct) => {
        const st = esc(String(ct.status_label || ct.status || ""));
        const amt = Number(ct.amount_vnd || 0);
        const amtTxt = amt ? `${amt.toLocaleString("vi-VN")} ₫` : "—";
        return `
          <article class="crm-cu-contract-card panel">
            <h3>${esc(String(ct.title || "Hợp đồng"))}</h3>
            <p class="muted">${esc(String(ct.reference_code || ""))} · ${st} · ${amtTxt}</p>
            <a class="btn-secondary btn-sm crm-staff-row-action-btn" href="/crm/hub">Xem Hub</a>
          </article>
        `;
      })
      .join("");
  }

  function renderQuickStats(stats) {
    const el = document.getElementById("crm-cu-quick-stats");
    if (!el) return;
    const s = stats || {};
    const items = [
      { val: s.cases_open ?? 0, lbl: "Hồ sơ mở", icon: "folder", cls: "" },
      { val: s.purchases_total ?? 0, lbl: "Giao dịch", icon: "cart", cls: "" },
      { val: s.issues_open ?? 0, lbl: "Vấn đề", icon: "alert", cls: s.issues_open ? "crm-cu-metric--warn" : "" },
      { val: s.relations_total ?? 0, lbl: "Quan hệ", icon: "users", cls: "" },
    ];
    const icons = {
      folder: '<svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M22 19a2 2 0 0 1-2 2H4a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h5l2 3h9a2 2 0 0 1 2 2z"/></svg>',
      cart: '<svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><circle cx="9" cy="21" r="1"/><circle cx="20" cy="21" r="1"/><path d="M1 1h4l2.68 13.39a2 2 0 0 0 2 1.61h9.72a2 2 0 0 0 2-1.61L23 6H6"/></svg>',
      alert: '<svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M10.29 3.86L1.82 18a2 2 0 0 0 1.71 3h16.94a2 2 0 0 0 1.71-3L13.71 3.86a2 2 0 0 0-3.42 0z"/><line x1="12" y1="9" x2="12" y2="13"/></svg>',
      users: '<svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M17 21v-2a4 4 0 0 0-4-4H5a4 4 0 0 0-4 4v2"/><circle cx="9" cy="7" r="4"/></svg>',
    };
    el.innerHTML = items
      .map(
        (it) =>
          `<div class="crm-cu-metric ${it.cls}"><span class="crm-cu-metric-icon" aria-hidden="true">${icons[it.icon] || ""}</span><span class="crm-cu-metric-val">${it.val}</span><span class="crm-cu-metric-lbl">${it.lbl}</span></div>`,
      )
      .join("");
  }

  function renderContactGrid(cu) {
    const el = document.getElementById("crm-cu-contact-grid");
    if (!el) return;
    const phone = String(cu.phone || "").trim();
    const email = String(cu.email || "").trim();
    const address = String(cu.address || "").trim();
    const company = String(cu.company || "").trim();
    const cards = [
      {
        key: "phone",
        label: "Điện thoại",
        val: phone,
        href: phone ? `tel:${phone.replace(/\s/g, "")}` : "",
        icon: '<svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M22 16.92v3a2 2 0 0 1-2.18 2 19.79 19.79 0 0 1-8.63-3.07 19.5 19.5 0 0 1-6-6 19.79 19.79 0 0 1-3.07-8.67A2 2 0 0 1 4.11 2h3a2 2 0 0 1 2 1.72 12.84 12.84 0 0 0 .7 2.81 2 2 0 0 1-.45 2.11L8.09 9.91a16 16 0 0 0 6 6l1.27-1.27a2 2 0 0 1 2.11-.45 12.84 12.84 0 0 0 2.81.7A2 2 0 0 1 22 16.92z"/></svg>',
      },
      {
        key: "email",
        label: "Email",
        val: email,
        href: email ? `mailto:${email}` : "",
        icon: '<svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M4 4h16c1.1 0 2 .9 2 2v12c0 1.1-.9 2-2 2H4c-1.1 0-2-.9-2-2V6c0-1.1.9-2 2-2z"/><polyline points="22,6 12,13 2,6"/></svg>',
      },
      {
        key: "address",
        label: "Địa chỉ",
        val: address,
        href: address ? `https://maps.google.com/?q=${encodeURIComponent(address)}` : "",
        icon: '<svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M21 10c0 7-9 13-9 13s-9-6-9-13a9 9 0 0 1 18 0z"/><circle cx="12" cy="10" r="3"/></svg>',
      },
      {
        key: "company",
        label: "Công ty",
        val: company,
        href: "",
        icon: '<svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><rect x="2" y="7" width="20" height="14" rx="2"/><path d="M16 21V5a2 2 0 0 0-2-2h-4a2 2 0 0 0-2 2v16"/></svg>',
      },
    ];
    el.innerHTML = cards
      .map((c) => {
        const empty = !c.val;
        const inner = empty
          ? `<span class="crm-cu-contact-val crm-cu-contact-val--empty">Chưa có</span>`
          : c.href
            ? `<a class="crm-cu-contact-val" href="${escapeAttr(c.href)}"${c.key === "address" ? ' target="_blank" rel="noopener"' : ""}>${esc(c.val)}</a>`
            : `<span class="crm-cu-contact-val">${esc(c.val)}</span>`;
        return `
          <div class="crm-cu-contact-card${empty ? " is-empty" : ""}">
            <span class="crm-cu-contact-icon" aria-hidden="true">${c.icon}</span>
            <div class="crm-cu-contact-text">
              <span class="crm-cu-contact-lbl">${c.label}</span>
              ${inner}
            </div>
          </div>`;
      })
      .join("");
  }

  function updateNavBadges(stats) {
    const s = stats || {};
    const purchasesBadge = document.getElementById("crm-cu-badge-purchases");
    const issuesBadge = document.getElementById("crm-cu-badge-issues");
    const pTotal = Number(s.purchases_total || 0);
    const iOpen = Number(s.issues_open || 0);
    if (purchasesBadge) {
      purchasesBadge.textContent = String(pTotal);
      purchasesBadge.hidden = pTotal <= 0;
    }
    if (issuesBadge) {
      issuesBadge.textContent = String(iOpen);
      issuesBadge.hidden = iOpen <= 0;
    }
  }

  function renderHeroBadges(cu, stats) {
    const el = document.getElementById("crm-cu-hero-badges");
    if (!el) return;
    const badges = [];
    if (cu.lead_source_label) {
      badges.push(`<span class="crm-cu-hero-badge">${esc(String(cu.lead_source_label))}</span>`);
    }
    const stage = cu.primary_pipeline_label || stats?.primary_pipeline_label;
    if (stage) {
      badges.push(`<span class="crm-cu-hero-badge crm-cu-hero-badge--stage">${esc(String(stage))}</span>`);
    }
    if (Number(stats?.issues_open || 0) > 0) {
      badges.push(`<span class="crm-cu-hero-badge crm-cu-hero-badge--warn">${Number(stats.issues_open)} vấn đề</span>`);
    }
    el.innerHTML = badges.join("");
  }

  function populateCareCaseSelect(cases) {
    const sel = document.getElementById("crm-cu-care-case");
    if (!(sel instanceof HTMLSelectElement)) return;
    sel.innerHTML = cases
      .map(
        (c) =>
          `<option value="${c.id}">#${c.id} — ${escapeAttr(String(c.title || ""))}</option>`,
      )
      .join("");
  }

  function populateCustomerForms(cu) {
    if (profileForm) {
      profileForm.elements.name.value = cu.name || "";
      profileForm.elements.phone.value = cu.phone || "";
      profileForm.elements.email.value = cu.email || "";
      if (profileForm.elements.address) profileForm.elements.address.value = cu.address || "";
      profileForm.elements.company.value = cu.company || "";
      if (profileForm.elements.lead_source) {
        profileForm.elements.lead_source.value = cu.lead_source || "";
      }
      if (profileForm.elements.lead_source_note) {
        profileForm.elements.lead_source_note.value = cu.lead_source_note || "";
      }
    }
    if (demoForm) {
      demoForm.elements.date_of_birth.value = String(cu.date_of_birth || "").slice(0, 10);
      demoForm.elements.gender.value = cu.gender || "";
      demoForm.elements.id_number.value = cu.id_number || "";
      demoForm.elements.occupation.value = cu.occupation || "";
      demoForm.elements.interests.value = cu.interests || "";
      demoForm.elements.profile_notes.value = cu.profile_notes || "";
    }
  }

  function showDetailPanel() {
    if (detailEmpty) detailEmpty.hidden = true;
    if (detailPanel) detailPanel.hidden = false;
    if (detailPane) detailPane.classList.add("is-open");
    if (isMobileLayout()) document.body.style.overflow = "hidden";
  }

  function closeDetail() {
    activeCustomerId = null;
    activeCustomer = null;
    if (detailEmpty) detailEmpty.hidden = false;
    if (detailPanel) detailPanel.hidden = true;
    if (detailPane) detailPane.classList.remove("is-open");
    document.body.style.overflow = modalCreate && !modalCreate.hidden ? "hidden" : "";
    renderList();
  }

  async function openCustomer(id) {
    activeCustomerId = id;
    window._lcCid = id;
    if (detailPanel) detailPanel.dataset.customerId = String(id);
    const lcLink = document.getElementById("crm-cu-lc-open");
    if (lcLink) lcLink.href = `/crm/customers/${id}/lifecycle/new`;
    const data = await reqJson(`/api/crm/customers/${id}`);
    activeCustomer = data.customer;
    const cu = data.customer || {};
    const stats = data.stats || {};

    const titleEl = document.getElementById("crm-cu-drawer-title");
    const subEl = document.getElementById("crm-cu-drawer-sub");
    const avatarEl = document.getElementById("crm-cu-avatar");
    const callBtn = document.getElementById("crm-cu-quick-call");
    const emailBtn = document.getElementById("crm-cu-quick-email");

    if (titleEl) titleEl.textContent = String(cu.name || "—");
    if (avatarEl) {
      avatarEl.textContent = initials(String(cu.name || ""));
      avatarEl.setAttribute("style", avatarStyle(String(cu.name || "")));
    }
    if (subEl) {
      const parts = [cu.company, cu.phone, cu.email].filter(Boolean);
      subEl.textContent = parts.join(" · ") || "Chưa có thông tin liên hệ";
    }

    const phone = String(cu.phone || "").trim();
    const email = String(cu.email || "").trim();
    if (callBtn instanceof HTMLAnchorElement) {
      if (phone) {
        callBtn.href = `tel:${phone.replace(/\s/g, "")}`;
        callBtn.hidden = false;
      } else callBtn.hidden = true;
    }
    if (emailBtn instanceof HTMLAnchorElement) {
      if (email) {
        emailBtn.href = `mailto:${email}`;
        emailBtn.hidden = false;
      } else emailBtn.hidden = true;
    }

    renderHeroBadges(cu, stats);
    renderContactGrid(cu);
    populateCustomerForms(cu);

    const createdEl = document.getElementById("crm-cu-created-at");
    if (createdEl) {
      createdEl.textContent = cu.created_at
        ? `Khách hàng từ ${formatViDateTime(String(cu.created_at))}`
        : "";
    }

    const profileActions = document.getElementById("crm-cu-profile-actions");
    const demoActions = document.getElementById("crm-cu-demo-actions");
    if (profileActions) profileActions.hidden = staffPortal;
    if (demoActions) demoActions.hidden = staffPortal;
    setFormReadOnly(profileForm, staffPortal);
    setFormReadOnly(demoForm, staffPortal);

    renderSources(data.lead_sources || []);
    renderRelations(data.relations || []);
    renderPurchases(data.purchases || []);
    renderIssues(data.issues || []);
    renderQuickStats(stats);
    updateNavBadges(stats);
    renderCases(data.cases || []);
    renderCareTimeline(data.care_reports || []);
    renderContracts(data.contracts || []);
    populateCareCaseSelect(data.cases || []);
    if (relationForm) relationForm.hidden = true;

    switchTab("overview");
    showDetailPanel();
    renderList();
  }

  async function patchCustomer(body) {
    if (!activeCustomerId) return;
    await reqJson(`/api/crm/customers/${activeCustomerId}`, {
      method: "PATCH",
      body: JSON.stringify(body),
    });
    await reload();
    await openCustomer(activeCustomerId);
  }

  document.querySelectorAll(".crm-cu-nav-item").forEach((btn) => {
    btn.addEventListener("click", () => {
      switchTab(btn.getAttribute("data-cu-tab") || "overview");
    });
  });

  document.getElementById("crm-cu-detail-close")?.addEventListener("click", closeDetail);
  document.getElementById("crm-cu-mobile-backdrop")?.addEventListener("click", closeDetail);

  document.addEventListener("keydown", (e) => {
    if (e.key !== "Escape") return;
    if (detailPane?.classList.contains("is-open") && isMobileLayout()) closeDetail();
    else if (modalCreate && !modalCreate.hidden) closeCreateModal();
  });

  searchEl?.addEventListener("input", () => {
    window.clearTimeout(searchTimer);
    searchTimer = window.setTimeout(() => reload().catch(() => {}), 200);
  });

  document.querySelectorAll(".crm-chip[data-cu-filter]").forEach((btn) => {
    btn.addEventListener("click", () => {
      listFilter = btn.getAttribute("data-cu-filter") === "all" ? "all" : "active";
      document.querySelectorAll(".crm-chip[data-cu-filter]").forEach((b) => {
        b.classList.toggle("is-active", b === btn);
      });
      renderList();
    });
  });

  function openCreateModal() {
    if (!modalCreate) return;
    modalCreate.hidden = false;
    modalCreate.classList.add("is-open");
    document.body.style.overflow = "hidden";
  }

  function closeCreateModal() {
    if (!modalCreate) return;
    modalCreate.classList.remove("is-open");
    modalCreate.hidden = true;
    document.body.style.overflow =
      detailPane?.classList.contains("is-open") && isMobileLayout() ? "hidden" : "";
  }

  document.getElementById("crm-cu-open-create")?.addEventListener("click", () => {
    createForm?.reset();
    const err = document.getElementById("crm-cu-create-err");
    if (err) err.hidden = true;
    openCreateModal();
  });

  document.querySelectorAll("[data-cu-close]").forEach((el) => {
    el.addEventListener("click", () => {
      closeCreateModal();
    });
  });

  createForm?.addEventListener("submit", async (ev) => {
    ev.preventDefault();
    const err = document.getElementById("crm-cu-create-err");
    if (err) err.hidden = true;
    const fd = new FormData(createForm);
    try {
      const row = await reqJson("/api/crm/customers", {
        method: "POST",
        body: JSON.stringify({
          name: fd.get("name"),
          phone: fd.get("phone") || "",
          email: fd.get("email") || "",
          address: fd.get("address") || "",
          company: fd.get("company") || "",
          lead_source: fd.get("lead_source") || "",
        }),
      });
      closeCreateModal();
      await reload();
      if (row.id) openCustomer(Number(row.id));
    } catch (e) {
      if (err) {
        err.textContent = e instanceof Error ? e.message : "Lỗi";
        err.hidden = false;
      }
    }
  });

  profileForm?.addEventListener("submit", async (ev) => {
    ev.preventDefault();
    if (staffPortal || !activeCustomerId) return;
    const err = document.getElementById("crm-cu-profile-err");
    if (err) err.hidden = true;
    const fd = new FormData(profileForm);
    try {
      await patchCustomer({
        name: fd.get("name"),
        phone: fd.get("phone") || "",
        email: fd.get("email") || "",
        address: fd.get("address") || "",
        company: fd.get("company") || "",
        lead_source: fd.get("lead_source") || "",
        lead_source_note: fd.get("lead_source_note") || "",
      });
    } catch (e) {
      if (err) {
        err.textContent = e instanceof Error ? e.message : "Không lưu được";
        err.hidden = false;
      }
    }
  });

  demoForm?.addEventListener("submit", async (ev) => {
    ev.preventDefault();
    if (staffPortal || !activeCustomerId) return;
    const err = document.getElementById("crm-cu-demo-err");
    if (err) err.hidden = true;
    const fd = new FormData(demoForm);
    try {
      await patchCustomer({
        date_of_birth: fd.get("date_of_birth") || "",
        gender: fd.get("gender") || "",
        id_number: fd.get("id_number") || "",
        occupation: fd.get("occupation") || "",
        interests: fd.get("interests") || "",
        profile_notes: fd.get("profile_notes") || "",
      });
      switchTab("profile");
    } catch (e) {
      if (err) {
        err.textContent = e instanceof Error ? e.message : "Không lưu được";
        err.hidden = false;
      }
    }
  });

  document.getElementById("crm-cu-relation-add")?.addEventListener("click", () => {
    if (!relationForm) return;
    relationForm.hidden = false;
    relationForm.reset();
    relationForm.elements.relation_id.value = "";
  });

  document.getElementById("crm-cu-relation-cancel")?.addEventListener("click", () => {
    if (relationForm) relationForm.hidden = true;
  });

  relationForm?.addEventListener("submit", async (ev) => {
    ev.preventDefault();
    if (!activeCustomerId) return;
    const fd = new FormData(relationForm);
    const rid = String(fd.get("relation_id") || "").trim();
    const body = {
      relation_type: fd.get("relation_type"),
      full_name: fd.get("full_name"),
      phone: fd.get("phone") || "",
      email: fd.get("email") || "",
      notes: fd.get("notes") || "",
    };
    try {
      if (rid) {
        await reqJson(`/api/crm/customers/${activeCustomerId}/relations/${rid}`, {
          method: "PATCH",
          body: JSON.stringify(body),
        });
      } else {
        await reqJson(`/api/crm/customers/${activeCustomerId}/relations`, {
          method: "POST",
          body: JSON.stringify(body),
        });
      }
      relationForm.hidden = true;
      await reload();
      await openCustomer(activeCustomerId);
      switchTab("profile");
    } catch (e) {
      window.alert(e instanceof Error ? e.message : "Lỗi");
    }
  });

  purchaseForm?.addEventListener("submit", async (ev) => {
    ev.preventDefault();
    if (!activeCustomerId) return;
    const err = document.getElementById("crm-cu-purchase-err");
    if (err) err.hidden = true;
    const fd = new FormData(purchaseForm);
    try {
      await reqJson(`/api/crm/customers/${activeCustomerId}/purchases`, {
        method: "POST",
        body: JSON.stringify({
          order_date: fd.get("order_date"),
          product_name: fd.get("product_name"),
          quantity: fd.get("quantity"),
          amount_vnd: fd.get("amount_vnd"),
          status: fd.get("status"),
          reference_code: fd.get("reference_code") || "",
          notes: fd.get("notes") || "",
        }),
      });
      purchaseForm.reset();
      const parent = purchaseForm.closest("details");
      if (parent instanceof HTMLDetailsElement) parent.open = false;
      await reload();
      await openCustomer(activeCustomerId);
      switchTab("purchases");
    } catch (e) {
      if (err) {
        err.textContent = e instanceof Error ? e.message : "Lỗi";
        err.hidden = false;
      }
    }
  });

  issueForm?.addEventListener("submit", async (ev) => {
    ev.preventDefault();
    if (!activeCustomerId) return;
    const err = document.getElementById("crm-cu-issue-err");
    if (err) err.hidden = true;
    const fd = new FormData(issueForm);
    try {
      await reqJson(`/api/crm/customers/${activeCustomerId}/issues`, {
        method: "POST",
        body: JSON.stringify({
          issue_type: fd.get("issue_type"),
          priority: fd.get("priority"),
          title: fd.get("title"),
          description: fd.get("description"),
        }),
      });
      issueForm.reset();
      await reload();
      await openCustomer(activeCustomerId);
      switchTab("issues");
    } catch (e) {
      if (err) {
        err.textContent = e instanceof Error ? e.message : "Lỗi";
        err.hidden = false;
      }
    }
  });

  careForm?.addEventListener("submit", async (ev) => {
    ev.preventDefault();
    if (!activeCustomerId) return;
    const err = document.getElementById("crm-cu-care-err");
    if (err) err.hidden = true;
    const fd = new FormData(careForm);
    const caseId = fd.get("case_id");
    if (!caseId) return;
    try {
      await reqJson(`/api/crm/cases/${caseId}/care-reports`, {
        method: "POST",
        body: JSON.stringify({
          summary: fd.get("summary"),
          contact_type: fd.get("contact_type"),
          care_status: fd.get("care_status"),
          next_action: fd.get("next_action") || "",
        }),
      });
      careForm.reset();
      await reload();
      await openCustomer(activeCustomerId);
      switchTab("care");
    } catch (e) {
      if (err) {
        err.textContent = e instanceof Error ? e.message : "Không gửi được báo cáo";
        err.hidden = false;
      }
    }
  });

  fillSelect(document.getElementById("crm-cu-care-contact"), careContactLabels);
  fillSelect(document.getElementById("crm-cu-care-status"), careStatusLabels);
  fillSelect(document.getElementById("crm-cu-lead-source"), leadSourceLabels, "— Chọn nguồn —");
  fillSelect(document.getElementById("crm-cu-create-lead-source"), leadSourceLabels, "— Chọn nguồn —");
  fillSelect(document.getElementById("crm-cu-gender"), genderLabels, "— Chưa rõ —");
  fillSelect(document.getElementById("crm-cu-relation-type"), relationTypeLabels);
  fillSelect(document.getElementById("crm-cu-purchase-status"), purchaseStatusLabels);
  fillSelect(document.getElementById("crm-cu-issue-type"), issueTypeLabels);
  fillSelect(document.getElementById("crm-cu-issue-priority"), issuePriorityLabels);

  reload().catch(() => {
    if (cardListEl) {
      cardListEl.innerHTML = '<p class="muted crm-cu-empty-hint">Không tải được danh sách khách hàng.</p>';
    }
  });
})();
