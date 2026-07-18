/**
 * Pre-sales panel on CRM Lead (PTT_PRESALES_ON_LEAD=1)
 */
(function () {
  "use strict";

  const metaEl = document.getElementById("crm-leads-meta");
  const meta = metaEl ? JSON.parse(metaEl.textContent || "{}") : {};
  if (!meta.presales_on_lead) return;

  const stageLabels = meta.presales_stage_labels || {
    lead: "Lead",
    consult: "Tư vấn",
    proposal: "Báo giá",
  };
  const serviceSlugs = meta.service_slugs || [];
  let serviceLabels = meta.service_labels || {};
  const presalesCategories = [
    ["dien_thoai", "Điện thoại / SIM"],
    ["di_lai", "Đi lại / gặp KH"],
    ["cong_lead", "Công AM Lead / Intake"],
    ["cong_tu_van", "Công Consult (nội bộ)"],
    ["cong_cu", "Công cụ / phần mềm"],
    ["khac_presales", "Khác (pre-sales)"],
  ];

  let leadId = null;
  let presalesData = null;
  let careGate = null;
  let activeTab = "lead";

  function isCareGateComplete() {
    if (careGate && typeof careGate.complete === "boolean") return careGate.complete;
    return false;
  }

  function setCareGate(gate) {
    careGate = gate || null;
    applyPresalesLockState();
  }

  function presalesTabIndex(st, stages) {
    const list = stages || (presalesData && presalesData.stages) || ["lead", "consult", "proposal"];
    return list.indexOf(st);
  }

  function applyPresalesLockState() {
    const panel = $("crm-leads-presales-panel");
    const locked = !isCareGateComplete();
    if (panel) panel.classList.toggle("is-locked", locked);
    const banner = $("crm-leads-presales-locked-banner");
    if (banner) banner.hidden = !locked;
    const slugSel = $("crm-leads-presales-slug");
    const startBtn = $("crm-leads-presales-start");
    if (slugSel) slugSel.disabled = locked || !!(presalesData && presalesData.presales);
    if (startBtn) startBtn.disabled = locked || !!(presalesData && presalesData.presales);
  }

  function $(id) {
    return document.getElementById(id);
  }

  function esc(s) {
    return String(s ?? "")
      .replace(/&/g, "&amp;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;")
      .replace(/"/g, "&quot;");
  }

  async function reqJson(url, opts) {
    const r = await fetch(url, {
      headers: { "Content-Type": "application/json", Accept: "application/json" },
      credentials: "same-origin",
      ...opts,
    });
    const d = await r.json().catch(() => ({}));
    if (!r.ok) {
      const err = new Error(d.error || r.statusText || "Lỗi");
      err.payload = d;
      throw err;
    }
    return d;
  }

  function showErr(msg) {
    const el = $("crm-leads-presales-err");
    if (!el) return;
    el.textContent = msg || "";
    el.hidden = !msg;
  }

  function fillSlugSelect() {
    const sel = $("crm-leads-presales-slug");
    if (!sel) return;
    sel.innerHTML =
      '<option value="">— Chọn dịch vụ —</option>' +
      serviceSlugs
        .map(
          (slug) =>
            `<option value="${esc(slug)}">${esc(serviceLabels[slug] || slug)}</option>`
        )
        .join("");
  }

  function renderBrief(brief) {
    const el = $("crm-leads-presales-brief");
    if (!el) return;
    if (!brief || activeTab !== "consult") {
      el.innerHTML = "";
      return;
    }
    const rd = brief.readiness || {};
    const gate = rd.consult_gate_level || "warn";
    const gateColors = {
      ok: "#166534",
      warn: "#92400e",
      block: "#991b1b",
    };
    el.innerHTML = `
      <div class="crm-leads-presales-brief-inner" style="background:#f5f3ff;border:1px solid #ddd6fe;border-radius:8px;padding:.75rem;margin:.75rem 0;font-size:.8rem;">
        <div style="display:flex;justify-content:space-between;align-items:flex-start;gap:.5rem;">
          <strong style="color:#5b21b6;">Consult Brief</strong>
          <span style="font-size:.7rem;font-weight:600;color:${gateColors[gate] || "#64748b"}">Gate: ${esc(gate).toUpperCase()}</span>
        </div>
        <div style="margin-top:.35rem;color:#4c1d95;">
          Decision: <strong>${esc(rd.decision_label)}</strong> · BANT <strong>${rd.bant_total || 0}/30</strong>
        </div>
        ${
          brief.latest_intake_summary
            ? `<div style="margin-top:.5rem;white-space:pre-wrap;color:#3730a3;">${esc(brief.latest_intake_summary.slice(0, 500))}</div>`
            : ""
        }
      </div>`;
  }

  function renderTasks(tasks) {
    const el = $("crm-leads-presales-tasks");
    if (!el) return;
    const list = (tasks && tasks[activeTab]) || [];
    const currentStage = (presalesData && presalesData.presales && presalesData.presales.stage) || "lead";
    const viewOnly = presalesTabIndex(activeTab) < presalesTabIndex(currentStage);
    if (!list.length) {
      el.innerHTML = `<p class="muted">Chưa có task — reload hoặc chọn lại dịch vụ.</p>`;
      return;
    }
    el.innerHTML = list
      .map((task) => {
        const fields = (task.form_fields || [])
          .map((f) => {
            const val = (task.form_data || {})[f.key] || "";
            const dis = viewOnly ? " disabled readonly" : "";
            if (f.type === "textarea") {
              return `<label style="display:block;font-size:.75rem;margin:.35rem 0">${esc(f.label)}
                <textarea rows="2" data-task-id="${task.id}" data-field-key="${esc(f.key)}"
                  class="crm-leads-ps-field"${dis}>${esc(val)}</textarea></label>`;
            }
            return `<label style="display:block;font-size:.75rem;margin:.35rem 0">${esc(f.label)}
              <input type="text" data-task-id="${task.id}" data-field-key="${esc(f.key)}"
                class="crm-leads-ps-field" value="${esc(val)}"${dis} /></label>`;
          })
          .join("");
        const doneDis = viewOnly ? " disabled" : "";
        return `
          <div class="crm-leads-presales-task${viewOnly ? " is-readonly" : ""}" style="border:1px solid #e2e8f0;border-radius:8px;padding:.75rem;margin:.5rem 0;background:#fff;">
            <label style="display:flex;align-items:flex-start;gap:.5rem;font-weight:600;font-size:.85rem;">
              <input type="checkbox" class="crm-leads-ps-done" data-task-id="${task.id}" ${task.is_done ? "checked" : ""}${doneDis} />
              ${esc(task.title)}
            </label>
            ${task.description ? `<p class="muted" style="font-size:.75rem;margin:.25rem 0 .5rem 1.5rem">${esc(task.description)}</p>` : ""}
            <div style="margin-left:1.5rem">${fields}</div>
            <label style="display:block;font-size:.75rem;margin-top:.5rem">Ghi chú AM
              <textarea rows="2" class="crm-leads-ps-notes" data-task-id="${task.id}"${dis}>${esc(task.notes || "")}</textarea>
            </label>
          </div>`;
      })
      .join("");
    if (viewOnly) {
      el.insertAdjacentHTML(
        "afterbegin",
        `<p class="muted crm-leads-presales-readonly-hint">Đang xem lại bước đã qua — chỉ đọc.</p>`,
      );
    }
  }

  const mpStrategyLabels = {
    market_message: "Thông điệp tới TMMT",
    media_reach: "Phương tiện truyền thông",
    conversion_strategy: "Chuyển đổi khách",
  };

  function renderMarketingPlan(mp) {
    const wrap = $("crm-leads-presales-marketing-plan");
    if (!wrap) return;
    const show = activeTab === "proposal" || activeTab === "consult";
    wrap.hidden = !show;
    if (!show || !mp || !mp.plan) {
      wrap.innerHTML = "";
      return;
    }
    const plan = mp.plan;
    const val = mp.validation || {};
    const sf = plan.strategy_framework || {};
    const readonly =
      presalesTabIndex(activeTab) < presalesTabIndex((presalesData.presales || {}).stage);
    const dis = readonly ? " disabled readonly" : "";
    const statusColor = val.complete ? "#166534" : "#92400e";
    wrap.innerHTML = `
      <div class="crm-leads-presales-mp-inner" style="background:#fffbeb;border:1px solid #fde68a;border-radius:8px;padding:.75rem;margin:.75rem 0;font-size:.8rem;">
        <div style="display:flex;justify-content:space-between;align-items:flex-start;gap:.5rem;">
          <strong style="color:#92400e;">Kế hoạch MKT sơ bộ (Báo giá)</strong>
          <span style="font-size:.7rem;font-weight:600;color:${statusColor}">
            ${val.complete ? "Đủ điều kiện Proposal" : "Chưa đủ"}
          </span>
        </div>
        ${
          val.messages && val.messages.length && !val.complete
            ? `<ul style="margin:.35rem 0 0 1rem;color:#b45309;font-size:.75rem;">${val.messages
                .map((m) => `<li>${esc(m)}</li>`)
                .join("")}</ul>`
            : ""
        }
        <label style="display:block;margin-top:.5rem;font-size:.75rem;">Tên kế hoạch
          <input type="text" class="crm-leads-mp-field" data-mp-field="name" value="${esc(plan.name || "")}"${dis} style="width:100%;margin-top:.2rem;">
        </label>
        <label style="display:block;margin-top:.35rem;font-size:.75rem;">North Star
          <textarea rows="2" class="crm-leads-mp-field" data-mp-field="north_star"${dis} style="width:100%;margin-top:.2rem;">${esc(plan.north_star || "")}</textarea>
        </label>
        <label style="display:block;margin-top:.35rem;font-size:.75rem;">Mục tiêu chiến lược
          <textarea rows="2" class="crm-leads-mp-field" data-mp-field="objectives"${dis} style="width:100%;margin-top:.2rem;">${esc(plan.objectives || "")}</textarea>
        </label>
        ${(mp.strategy_keys || Object.keys(mpStrategyLabels))
          .map((key) => {
            const label = mpStrategyLabels[key] || key;
            return `<label style="display:block;margin-top:.35rem;font-size:.75rem;">${esc(label)}
              <textarea rows="2" class="crm-leads-mp-field" data-mp-strategy="${esc(key)}"${dis} style="width:100%;margin-top:.2rem;">${esc(sf[key] || "")}</textarea>
            </label>`;
          })
          .join("")}
        ${
          readonly
            ? ""
            : `<button type="button" class="btn btn-secondary btn-sm" id="crm-leads-mp-save" style="margin-top:.5rem;">Lưu KH MKT sơ bộ</button>`
        }
      </div>`;
    if (!readonly) {
      $("crm-leads-mp-save")?.addEventListener("click", saveMarketingPlan);
    }
  }

  async function saveMarketingPlan() {
    if (!leadId) return;
    showErr("");
    const body = { strategy_framework: {} };
    document.querySelectorAll(".crm-leads-mp-field[data-mp-field]").forEach((el) => {
      body[el.dataset.mpField] = el.value;
    });
    document.querySelectorAll(".crm-leads-mp-field[data-mp-strategy]").forEach((el) => {
      body.strategy_framework[el.dataset.mpStrategy] = el.value;
    });
    try {
      const data = await reqJson(`/api/crm/leads/${leadId}/presales/marketing-plan`, {
        method: "PATCH",
        body: JSON.stringify(body),
      });
      if (presalesData) presalesData.marketing_plan = data;
      renderMarketingPlan(data);
      if (typeof window.CrmLeadPresales?.onChanged === "function") {
        window.CrmLeadPresales.onChanged();
      }
      if (presalesData && presalesData.advance && presalesData.presales) {
        const adv = presalesData.advance;
        if (presalesData.presales.stage === "consult" && data.validation) {
          const tasksOk = adv.current_complete !== false;
          adv.can_advance_forward = !!data.validation.complete && tasksOk;
          if (!data.validation.complete) {
            adv.block_reason =
              (data.validation.messages && data.validation.messages[0]) || adv.block_reason;
          }
        }
      }
      const advBtn = $("crm-leads-presales-advance");
      if (advBtn && presalesData && presalesData.advance) {
        advBtn.disabled = !presalesData.advance.can_advance_forward;
        advBtn.title = presalesData.advance.block_reason || "";
      }
    } catch (e) {
      showErr(e.message);
    }
  }

  function renderTabs(currentStage) {
    const el = $("crm-leads-presales-tabs");
    if (!el) return;
    const stages = (presalesData && presalesData.stages) || ["lead", "consult", "proposal"];
    const curIdx = presalesTabIndex(currentStage, stages);
    el.innerHTML = stages
      .map((st) => {
        const on = st === activeTab;
        const cur = st === currentStage;
        const locked = presalesTabIndex(st, stages) > curIdx;
        return `<button type="button"
          class="crm-leads-presales-tab${on ? " is-active" : ""}${cur ? " is-current" : ""}${locked ? " is-tab-locked" : ""}"
          data-stage="${esc(st)}"
          role="tab"
          ${locked ? 'disabled aria-disabled="true" title="Chưa tới bước này"' : ""}>${esc(stageLabels[st] || st)}</button>`;
      })
      .join("");
    el.querySelectorAll(".crm-leads-presales-tab:not([disabled])").forEach((btn) => {
      btn.addEventListener("click", () => {
        activeTab = btn.getAttribute("data-stage") || "lead";
        renderTabs(currentStage);
        renderTasks(presalesData && presalesData.tasks_by_stage);
        renderBrief(presalesData && presalesData.brief);
        renderMarketingPlan(presalesData && presalesData.marketing_plan);
      });
    });
  }

  function renderMeta(ps, advance) {
    const el = $("crm-leads-presales-meta");
    if (!el || !ps) return;
    const slugLabel = serviceLabels[ps.service_slug] || ps.service_slug;
    const contract = presalesData && presalesData.contract;
    const contractHtml = contract
      ? `<a href="/crm/hub" target="_blank" rel="noopener">HĐ #${esc(contract.id)} (${esc(contract.status)})</a>`
      : "";
    const intakeLinks = isCareGateComplete()
      ? `<a href="/crm/intake?lead_id=${leadId}&mode=phone&auto_create=1" target="_blank" rel="noopener">📞 Intake gọi</a>
        <a href="/crm/intake?lead_id=${leadId}&mode=in_person&auto_create=1" target="_blank" rel="noopener">🤝 Intake gặp</a>`
      : "";
    el.innerHTML = `
      <div style="display:flex;flex-wrap:wrap;gap:.75rem;align-items:center;font-size:.8rem;margin-bottom:.5rem;">
        <span><strong>${esc(slugLabel)}</strong></span>
        <span>Bước hiện tại: <strong>${esc(stageLabels[ps.stage] || ps.stage)}</strong></span>
        ${
          advance && advance.next_stage
            ? `<span class="muted">Tiếp: ${esc(stageLabels[advance.next_stage] || advance.next_stage)}</span>`
            : `<span class="muted">Chờ ký HĐ → Lifecycle Onboard</span>`
        }
        ${contractHtml ? `<span>Hợp đồng: ${contractHtml}</span>` : ""}
        ${intakeLinks}
      </div>`;
    const draftBtn = $("crm-leads-presales-draft-contract");
    if (draftBtn) {
      draftBtn.disabled = !!(contract && contract.status === "draft");
      draftBtn.title =
        contract && contract.status === "draft"
          ? `Đã có HĐ draft #${contract.id}`
          : "Tạo HĐ draft trên Hub (KH placeholder)";
    }
  }

  function bindTaskEvents() {
    const currentStage = (presalesData && presalesData.presales && presalesData.presales.stage) || "lead";
    const viewOnly = presalesTabIndex(activeTab) < presalesTabIndex(currentStage);
    if (viewOnly) return;
    document.querySelectorAll(".crm-leads-ps-done").forEach((cb) => {
      cb.addEventListener("change", () => saveTask(cb.dataset.taskId, { is_done: cb.checked }));
    });
    document.querySelectorAll(".crm-leads-ps-field").forEach((inp) => {
      inp.addEventListener("change", () => {
        const tid = inp.dataset.taskId;
        const key = inp.dataset.fieldKey;
        const card = inp.closest(".crm-leads-presales-task");
        const formData = {};
        card.querySelectorAll(".crm-leads-ps-field").forEach((f) => {
          formData[f.dataset.fieldKey] = f.value;
        });
        saveTask(tid, { form_data: formData });
      });
    });
    document.querySelectorAll(".crm-leads-ps-notes").forEach((ta) => {
      ta.addEventListener("change", () => saveTask(ta.dataset.taskId, { notes: ta.value }));
    });
  }

  async function saveTask(taskId, body) {
    if (!leadId || !taskId) return;
    showErr("");
    try {
      const data = await reqJson(`/api/crm/leads/${leadId}/presales/tasks/${taskId}`, {
        method: "PATCH",
        body: JSON.stringify(body),
      });
      presalesData = data.presales;
      renderAll();
    } catch (e) {
      showErr(e.message);
    }
  }

  function fmtVnd(n) {
    return Number(n || 0).toLocaleString("vi-VN") + " ₫";
  }

  function renderCostPanel(cost) {
    const el = $("crm-leads-presales-cost");
    if (!el) return;
    if (!cost || !presalesData || !presalesData.presales) {
      el.hidden = true;
      el.innerHTML = "";
      return;
    }
    el.hidden = false;
    const ps = presalesData.presales;
    const rows = cost.recent_expenses || [];
    const over = cost.over_cap && cost.cap_alert_message;
    const catOpts = presalesCategories
      .map(([k, lbl]) => `<option value="${esc(k)}">${esc(lbl)}</option>`)
      .join("");
    const tableRows = rows.length
      ? rows
          .map(
            (e) => `
        <tr>
          <td>${esc(e.expense_on || "—")}</td>
          <td>${esc(e.title)}</td>
          <td><span class="crm-leads-ps-cost-cat">${esc(e.category)}</span></td>
          <td>${esc(e.lifecycle_stage || ps.stage || "")}</td>
          <td class="crm-leads-ps-cost-amt">${esc(fmtVnd(e.amount_vnd))}</td>
          <td><button type="button" class="crm-leads-ps-cost-del" data-expense-id="${esc(e.id)}">✕</button></td>
        </tr>`
          )
          .join("")
      : `<tr><td colspan="6" class="muted">Chưa ghi chi phí pre-sales.</td></tr>`;

    el.innerHTML = `
      <div class="crm-leads-presales-cost-inner">
        ${over ? `<div class="crm-leads-ps-cost-alert">⚠ ${esc(cost.cap_alert_message)}</div>` : ""}
        <div class="crm-leads-ps-cost-head">
          <div>
            <strong>Chi phí pre-sales (nội bộ PTT)</strong>
            <p class="muted">Khách chưa trả — không tính vào margin HĐ.</p>
          </div>
          <div class="crm-leads-ps-cost-total">
            <span class="muted">Tổng</span>
            <strong>${esc(fmtVnd(cost.total_presales_vnd))}</strong>
            <span class="muted">${rows.length} khoản</span>
          </div>
        </div>
        <div class="crm-leads-ps-cost-cap">
          <label>Cap (₫)</label>
          <input type="number" id="crm-leads-ps-cap" min="0" step="100000"
            value="${cost.presales_cost_cap_vnd || ""}" placeholder="VD: 3000000">
          <button type="button" class="btn btn-secondary btn-sm" id="crm-leads-ps-cap-save">Lưu cap</button>
          <span id="crm-leads-ps-cap-status" class="muted"></span>
          ${
            cost.presales_cost_cap_vnd
              ? `<span class="muted">Còn ${esc(fmtVnd(cost.cap_remaining_vnd || 0))} (${esc(String(cost.cap_utilization_pct || 0))}%)</span>`
              : ""
          }
        </div>
        <table class="crm-leads-ps-cost-table">
          <thead><tr>
            <th>Ngày</th><th>Nội dung</th><th>Loại</th><th>Stage</th><th>Số tiền</th><th></th>
          </tr></thead>
          <tbody>${tableRows}</tbody>
        </table>
        <details class="crm-leads-ps-cost-form-wrap">
          <summary>+ Ghi chi phí pre-sales</summary>
          <div class="crm-leads-ps-cost-form">
            <input type="date" id="crm-leads-ps-exp-date">
            <input type="text" id="crm-leads-ps-exp-title" placeholder="Mô tả (VD: cước gọi qualify)">
            <select id="crm-leads-ps-exp-category">${catOpts}</select>
            <input type="number" id="crm-leads-ps-exp-amount" min="0" step="1000" placeholder="Số tiền ₫">
            <input type="text" id="crm-leads-ps-exp-notes" placeholder="Ghi chú (tuỳ chọn)">
            <button type="button" class="btn btn-sm" id="crm-leads-ps-exp-save">Lưu chi phí</button>
            <p class="crm-form-msg is-error" id="crm-leads-ps-exp-err" hidden></p>
          </div>
        </details>
      </div>`;

    $("crm-leads-ps-cap-save")?.addEventListener("click", saveCostCap);
    $("crm-leads-ps-exp-save")?.addEventListener("click", createCostExpense);
    el.querySelectorAll(".crm-leads-ps-cost-del").forEach((btn) => {
      btn.addEventListener("click", () => deleteCostExpense(btn.dataset.expenseId));
    });
  }

  async function refreshCostSummary() {
    if (!leadId || !presalesData) return;
    try {
      const cost = await reqJson(`/api/crm/leads/${leadId}/presales-cost-summary`);
      presalesData.cost_summary = cost;
      renderCostPanel(cost);
    } catch (e) {
      renderCostPanel(presalesData.cost_summary);
    }
  }

  async function saveCostCap() {
    const capInput = $("crm-leads-ps-cap");
    const status = $("crm-leads-ps-cap-status");
    const capVal = parseInt(capInput && capInput.value ? capInput.value : "0", 10);
    if (status) status.textContent = "Đang lưu…";
    try {
      const cost = await reqJson(`/api/crm/leads/${leadId}/presales-cost-cap`, {
        method: "PATCH",
        body: JSON.stringify({ presales_cost_cap_vnd: capVal > 0 ? capVal : 0 }),
      });
      presalesData.cost_summary = cost;
      renderCostPanel(cost);
      if (status) status.textContent = "Đã lưu cap";
    } catch (e) {
      if (status) status.textContent = e.message || "Lỗi";
    }
  }

  async function createCostExpense() {
    const errEl = $("crm-leads-ps-exp-err");
    const date = ($("crm-leads-ps-exp-date") || {}).value;
    const title = (($("crm-leads-ps-exp-title") || {}).value || "").trim();
    const category = ($("crm-leads-ps-exp-category") || {}).value;
    const amount = parseInt(($("crm-leads-ps-exp-amount") || {}).value || "0", 10);
    const notes = (($("crm-leads-ps-exp-notes") || {}).value || "").trim();
    if (errEl) errEl.hidden = true;
    if (!date || !title || !amount) {
      if (errEl) {
        errEl.textContent = "Cần ngày, mô tả và số tiền.";
        errEl.hidden = false;
      }
      return;
    }
    try {
      await reqJson("/api/crm/svc-expenses", {
        method: "POST",
        body: JSON.stringify({
          lead_id: leadId,
          title,
          category,
          amount_vnd: amount,
          expense_on: date,
          notes,
          cost_phase: "presales",
        }),
      });
      await refreshCostSummary();
      if ($("crm-leads-ps-exp-title")) $("crm-leads-ps-exp-title").value = "";
      if ($("crm-leads-ps-exp-amount")) $("crm-leads-ps-exp-amount").value = "";
      if ($("crm-leads-ps-exp-notes")) $("crm-leads-ps-exp-notes").value = "";
    } catch (e) {
      if (errEl) {
        errEl.textContent = e.message || "Không lưu được.";
        errEl.hidden = false;
      }
    }
  }

  async function deleteCostExpense(expenseId) {
    if (!expenseId || !window.confirm("Xoá chi phí pre-sales này?")) return;
    try {
      await reqJson(`/api/crm/svc-expenses/${expenseId}`, { method: "DELETE" });
      await refreshCostSummary();
    } catch (e) {
      showErr(e.message);
    }
  }

  function renderAll() {
    if (!presalesData || !isCareGateComplete()) return;
    const ps = presalesData.presales || {};
    activeTab = activeTab || ps.stage || "lead";
    if (presalesTabIndex(activeTab) > presalesTabIndex(ps.stage)) {
      activeTab = ps.stage || "lead";
    }
    $("crm-leads-presales-setup").hidden = true;
    $("crm-leads-presales-active").hidden = false;
    applyPresalesLockState();
    renderMeta(ps, presalesData.advance);
    renderTabs(ps.stage);
    renderTasks(presalesData.tasks_by_stage);
    renderBrief(presalesData.brief);
    renderMarketingPlan(presalesData.marketing_plan);
    renderCostPanel(presalesData.cost_summary);
    bindTaskEvents();
    const advBtn = $("crm-leads-presales-advance");
    if (advBtn) {
      advBtn.disabled = !(presalesData.advance && presalesData.advance.can_advance_forward);
      advBtn.title = (presalesData.advance && presalesData.advance.block_reason) || "";
    }
    const convBtn = $("crm-leads-convert-btn");
    if (convBtn) convBtn.hidden = true;
    if (typeof window.CrmLeadPresales?.onChanged === "function") {
      window.CrmLeadPresales.onChanged();
    }
  }

  async function loadPresales(id) {
    leadId = id;
    showErr("");
    const panel = $("crm-leads-presales-panel");
    if (!panel || !leadId) {
      if (panel) panel.hidden = true;
      return;
    }
    panel.hidden = false;
    const convBtn = $("crm-leads-convert-btn");
    if (convBtn) convBtn.hidden = true;
    fillSlugSelect();
    try {
      const data = await reqJson(`/api/crm/leads/${leadId}/presales`);
      careGate = data.presales_care_gate || null;
      serviceLabels = data.service_labels || {};
      fillSlugSelect();
      applyPresalesLockState();
      if (!data.presales) {
        presalesData = null;
        $("crm-leads-presales-setup").hidden = !isCareGateComplete();
        $("crm-leads-presales-active").hidden = true;
        if (typeof window.CrmLeadPresales?.onChanged === "function") {
          window.CrmLeadPresales.onChanged();
        }
        return;
      }
      if (!isCareGateComplete()) {
        presalesData = null;
        $("crm-leads-presales-setup").hidden = true;
        $("crm-leads-presales-active").hidden = true;
        showErr("Pre-sales đã tạo trước khi có gate B1–B3 — hoàn thành chăm sóc ở panel phía trên.");
        if (typeof window.CrmLeadPresales?.onChanged === "function") {
          window.CrmLeadPresales.onChanged();
        }
        return;
      }
      presalesData = data.presales;
      activeTab = (presalesData.presales && presalesData.presales.stage) || "lead";
      renderAll();
    } catch (e) {
      showErr(e.message);
    }
  }

  async function startPresales() {
    if (!isCareGateComplete()) {
      showErr("Hoàn thành chăm sóc B1–B3 trước khi bắt đầu pre-sales.");
      window.CrmLeadCare?.navigateToCareStage?.("first_contact");
      return;
    }
    const slug = ($("crm-leads-presales-slug") || {}).value;
    if (!slug) {
      showErr("Chọn dịch vụ trước");
      return;
    }
    showErr("");
    try {
      const data = await reqJson(`/api/crm/leads/${leadId}/presales`, {
        method: "POST",
        body: JSON.stringify({ service_slug: slug }),
      });
      presalesData = data.presales;
      activeTab = "lead";
      renderAll();
    } catch (e) {
      showErr(e.message);
    }
  }

  async function advanceStage(extraBody) {
    if (!presalesData || !presalesData.advance || !presalesData.advance.next_stage) return;
    showErr("");
    try {
      const data = await reqJson(`/api/crm/leads/${leadId}/presales`, {
        method: "PATCH",
        body: JSON.stringify({
          stage: presalesData.advance.next_stage,
          ...(extraBody || {}),
        }),
      });
      presalesData = data.presales;
      activeTab = (presalesData.presales && presalesData.presales.stage) || activeTab;
      renderAll();
    } catch (e) {
      const p = e.payload || {};
      if (p.requires_confirm && !extraBody?.confirm) {
        const msg = (p.gate && p.gate.messages && p.gate.messages[0]) || e.message;
        if (window.confirm(`${msg}\n\nTiếp tục chuyển Consult?`)) {
          return advanceStage({ confirm: true, ...(extraBody || {}) });
        }
        return;
      }
      if (p.requires_override) {
        const reason = window.prompt("Director override — nhập lý do:");
        if (reason) return advanceStage({ override_reason: reason, confirm: true });
        return;
      }
      showErr(e.message);
    }
  }

  async function prefillConsult() {
    showErr("");
    try {
      const data = await reqJson(`/api/crm/leads/${leadId}/presales/consult-prefill`, {
        method: "POST",
        body: JSON.stringify({ overwrite: false }),
      });
      presalesData = data.presales;
      activeTab = "consult";
      renderAll();
    } catch (e) {
      showErr(e.message);
    }
  }

  async function createDraftContract() {
    showErr("");
    try {
      const data = await reqJson(`/api/crm/leads/${leadId}/presales/draft-contract`, {
        method: "POST",
        body: JSON.stringify({}),
      });
      presalesData = data.presales;
      renderAll();
      if (data.contract && data.contract.id) {
        window.open("/crm/hub", "_blank", "noopener");
      }
    } catch (e) {
      showErr(e.message);
    }
  }

  document.addEventListener("DOMContentLoaded", () => {
    $("crm-leads-presales-start")?.addEventListener("click", startPresales);
    $("crm-leads-presales-advance")?.addEventListener("click", () => advanceStage({}));
    $("crm-leads-presales-prefill")?.addEventListener("click", prefillConsult);
    $("crm-leads-presales-draft-contract")?.addEventListener("click", createDraftContract);
  });

  window.CrmLeadPresales = {
    load: loadPresales,
    isActive: () => !!(presalesData && presalesData.presales && isCareGateComplete()),
    isCareGateComplete,
    setCareGate,
    getSnapshot: () => presalesData,
    onChanged: null,
  };
})();
