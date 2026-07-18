/** @file Lead workspace funnel + gate checklist (P1). */
(function (global) {
  "use strict";

  function createCrmLeadWorkspace(ctx) {
    const {
      $,
      esc,
      meta,
      isDetailPage,
      detailTab,
      switchDetailTab,
      selectedLead,
      leadInReviewQueue,
      leadInLifecycleHandoff,
      leadPresalesCareReady,
      leadPresalesCareGate,
      navigateToCareStage,
      canManageReviewQueue,
    } = ctx;

    const presalesStageLabels = meta.presales_stage_labels || {
      lead: "Lead",
      consult: "Tư vấn",
      proposal: "Báo giá",
    };

    function isAddonMinimalComplete(addon) {
      if (!addon?.has_pack) return true;
      const data = addon.data || {};
      return Object.values(data).some((v) => String(v ?? "").trim());
    }

    function presalesSnapshot() {
      return typeof global.CrmLeadPresales?.getSnapshot === "function"
        ? global.CrmLeadPresales.getSnapshot()
        : null;
    }

    function workspaceFunnelSteps(lead) {
      const steps = [
        { key: "assigned", label: "Phân công" },
        { key: "b2", label: "B2 chăm sóc" },
      ];
      if (lead?.industry_addon?.has_pack) {
        steps.push({ key: "addon", label: "Add-on ngành" });
      }
      if (meta.presales_on_lead) {
        steps.push({ key: "presales", label: "Pre-sales" });
        steps.push({ key: "contract", label: "HĐ draft" });
      }
      steps.push({ key: "lifecycle", label: "Lifecycle" });
      return steps;
    }

    function funnelStepStatus(stepKey, lead) {
      if (leadInLifecycleHandoff(lead)) {
        return stepKey === "lifecycle" ? "done" : "done";
      }
      if (leadInReviewQueue(lead) && stepKey !== "assigned") {
        return stepKey === "assigned" && lead.owner_id ? "done" : "blocked";
      }
      switch (stepKey) {
        case "assigned":
          return lead.owner_id ? "done" : "current";
        case "b2":
          if (!lead.owner_id) return "pending";
          return leadPresalesCareReady(lead) ? "done" : "current";
        case "addon": {
          const addon = lead.industry_addon;
          if (!addon?.has_pack) return "skip";
          if (!leadPresalesCareReady(lead)) return "pending";
          return isAddonMinimalComplete(addon) ? "done" : "current";
        }
        case "presales": {
          if (!meta.presales_on_lead) return "skip";
          if (!leadPresalesCareReady(lead)) return "pending";
          const snap = presalesSnapshot();
          const ps = snap?.presales;
          if (!ps) return "current";
          const stage = String(ps.stage || "lead");
          if (stage === "proposal" && ps.status === "active") {
            const adv = snap.advance || {};
            if (adv.next_stage === null && adv.current_complete) return "done";
          }
          return "current";
        }
        case "contract": {
          if (!meta.presales_on_lead) return "skip";
          const snap = presalesSnapshot();
          const ps = snap?.presales;
          if (!ps || String(ps.stage || "") !== "proposal") return "pending";
          if (snap?.contract?.id) return "done";
          return "current";
        }
        case "lifecycle":
          return leadInLifecycleHandoff(lead) ? "done" : "pending";
        default:
          return "pending";
      }
    }

    function buildGateChecklist(lead) {
      const items = [];
      if (leadInLifecycleHandoff(lead)) {
        return {
          status: "done",
          title: "Đã chuyển lifecycle",
          items: [{ label: "Lead đã có KH / Case — tiếp tục trên CRM Hub.", done: true, step: null }],
        };
      }
      if (leadInReviewQueue(lead)) {
        items.push({
          label: canManageReviewQueue
            ? "Inbox tra soát — phân lại AM cho lead"
            : "Lead đang chờ GDKD tra soát (quá hạn B2)",
          done: false,
          step: canManageReviewQueue ? "review" : null,
          urgent: true,
        });
      }
      if (!lead.owner_id) {
        items.push({ label: "Chưa phân công AM", done: false, step: null });
      }
      if (!leadPresalesCareReady(lead)) {
        const gate = leadPresalesCareGate(lead);
        const pending = (gate?.stages || []).filter((s) => !s.done);
        const detail =
          pending.length > 0
            ? pending.map((s) => s.label || s.key).join(", ")
            : gate?.message || "Liên hệ OK + hoàn thành B2";
        items.push({ label: `Hoàn thành B2: ${detail}`, done: false, step: "b2", urgent: true });
      }
      const addon = lead.industry_addon;
      if (addon?.has_pack && leadPresalesCareReady(lead) && !isAddonMinimalComplete(addon)) {
        items.push({
          label: "Điền add-on ngành (ít nhất một trường)",
          done: false,
          step: "addon",
        });
      }
      if (meta.presales_on_lead && leadPresalesCareReady(lead) && !leadInReviewQueue(lead)) {
        const snap = presalesSnapshot();
        const ps = snap?.presales;
        if (!ps) {
          items.push({ label: "Bắt đầu pre-sales — chọn dịch vụ", done: false, step: "presales" });
        } else {
          const adv = snap.advance || {};
          const stage = String(ps.stage || "lead");
          if (adv.block_reason && !adv.can_advance_forward) {
            items.push({ label: adv.block_reason, done: false, step: "presales" });
          } else if (adv.next_stage && adv.can_advance_forward) {
            const nextLbl = presalesStageLabels[adv.next_stage] || adv.next_stage;
            items.push({
              label: `Chuyển pre-sales → ${nextLbl}`,
              done: false,
              step: "presales",
            });
          }
          if (stage === "proposal") {
            const mpVal = snap.marketing_plan?.validation;
            if (mpVal && !mpVal.complete) {
              const msg = (mpVal.messages && mpVal.messages[0]) || "Hoàn thành KH MKT sơ bộ @ Proposal";
              items.push({ label: msg, done: false, step: "presales" });
            }
            if (!snap.contract?.id) {
              items.push({ label: "Tạo HĐ draft sau khi chốt báo giá", done: false, step: "presales" });
            }
          }
        }
      }
      const open = items.filter((i) => !i.done);
      let status = "done";
      if (open.some((i) => i.urgent)) status = "urgent";
      else if (open.length) status = "blocked";
      const title =
        status === "done"
          ? "Sẵn sàng bước tiếp theo"
          : status === "urgent"
            ? "Cần xử lý ngay"
            : "Còn thiếu để mở bước tiếp";
      return {
        status,
        title,
        items: items.length ? items : [{ label: "Không còn gate — tiếp tục quy trình.", done: true, step: null }],
      };
    }

    function scrollToWorkspaceStep(stepKey) {
      if (!stepKey) return;
      if (isDetailPage && detailTab !== "process") switchDetailTab("process");
      const section = document.querySelector(`[data-workspace-step="${stepKey}"]`);
      if (!section || section.hidden) {
        if (stepKey === "b2") navigateToCareStage(selectedLead?.care_pipeline?.current_stage_key || "first_contact");
        return;
      }
      section.scrollIntoView({ behavior: "smooth", block: "start" });
      section.classList.remove("is-workspace-flash");
      void section.offsetWidth;
      section.classList.add("is-workspace-flash");
      window.setTimeout(() => section.classList.remove("is-workspace-flash"), 900);
    }

    function renderLeadWorkspace(lead) {
      const head = $("crm-lead-workspace-head");
      const funnelEl = $("crm-lead-funnel");
      const gateEl = $("crm-lead-gate-panel");
      if (!head || !funnelEl || !gateEl || !lead || !isDetailPage) return;
      head.hidden = false;
      const steps = workspaceFunnelSteps(lead);
      funnelEl.innerHTML = steps
        .map((st) => {
          const status = funnelStepStatus(st.key, lead);
          if (status === "skip") return "";
          const clickable = st.key !== "assigned" && st.key !== "lifecycle";
          return `<div class="crm-funnel-step is-${status}${clickable ? " is-clickable" : ""}"
          ${clickable ? `data-funnel-step="${esc(st.key)}" role="button" tabindex="0"` : ""}
          title="${esc(st.label)}">
          <span class="crm-funnel-step-dot"></span>
          <span class="crm-funnel-step-label">${esc(st.label)}</span>
        </div>`;
        })
        .join("");
      const gate = buildGateChecklist(lead);
      gateEl.className = `crm-gate-panel is-${gate.status}`;
      gateEl.innerHTML = `
      <div class="crm-gate-panel-head">
        <strong>${esc(gate.title)}</strong>
        ${gate.status === "done" ? '<span class="crm-gate-badge is-ok">OK</span>' : ""}
      </div>
      <ul class="crm-gate-list">
        ${gate.items
          .map(
            (it) =>
              `<li class="crm-gate-item${it.done ? " is-done" : ""}${it.urgent ? " is-urgent" : ""}">
                <span class="crm-gate-item-mark">${it.done ? "✓" : "○"}</span>
                ${
                  it.step && !it.done
                    ? `<button type="button" class="crm-gate-link" data-gate-step="${esc(it.step)}">${esc(it.label)}</button>`
                    : `<span>${esc(it.label)}</span>`
                }
              </li>`,
          )
          .join("")}
      </ul>`;
    }

    function bindWorkspaceUi() {
      $("crm-lead-gate-panel")?.addEventListener("click", (ev) => {
        const btn = ev.target.closest("[data-gate-step]");
        if (!btn) return;
        scrollToWorkspaceStep(btn.dataset.gateStep);
      });
      $("crm-lead-funnel")?.addEventListener("click", (ev) => {
        const step = ev.target.closest("[data-funnel-step]");
        if (!step) return;
        scrollToWorkspaceStep(step.dataset.funnelStep);
      });
      $("crm-lead-funnel")?.addEventListener("keydown", (ev) => {
        if (ev.key !== "Enter" && ev.key !== " ") return;
        const step = ev.target.closest("[data-funnel-step]");
        if (!step) return;
        ev.preventDefault();
        scrollToWorkspaceStep(step.dataset.funnelStep);
      });
    }

    return {
      isAddonMinimalComplete,
      renderLeadWorkspace,
      bindWorkspaceUi,
      scrollToWorkspaceStep,
    };
  }

  global.createCrmLeadWorkspace = createCrmLeadWorkspace;
})(window);
