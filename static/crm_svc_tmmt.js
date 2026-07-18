/**
 * P2 — TMMT chính thức trên Service Workflow (Onboard → Deliver gate)
 */
(function () {
  "use strict";

  const metaEl = document.getElementById("crm-svc-tmmt-meta");
  if (!metaEl) return;
  let meta = {};
  try {
    meta = JSON.parse(metaEl.textContent || "{}");
  } catch {
    meta = {};
  }

  const lifecycleId = Number(meta.lifecycle_id || 0);
  const initialPayload = meta.initial || null;
  const strategyLabels = meta.strategy_labels || {};
  const profLabels = meta.prof_labels || {};
  const coreKeys = Array.isArray(meta.core_keys) ? meta.core_keys : [];
  const tmmtMinFilled = Number(meta.tmmt_min_filled || 6);

  let planData = initialPayload;

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
    if (!r.ok) throw new Error(d.error || r.statusText || "Lỗi");
    return d;
  }

  function profFilledCount(prof) {
    if (!prof || typeof prof !== "object") return 0;
    return Object.values(prof).filter((v) => String(v ?? "").trim()).length;
  }

  function renderChecklist(validation, prof) {
    const el = $("crm-svc-tmmt-checklist");
    if (!el) return;
    const filled = profFilledCount(prof);
    const total = Object.keys(profLabels).length || 12;
    const coreDone = coreKeys.filter((k) => String(prof?.[k] || "").trim()).length;
    el.innerHTML = `
      <li class="${validation?.complete ? "is-done" : ""}">TMMT tóm tắt (target_market)</li>
      <li class="${coreDone >= coreKeys.length ? "is-done" : ""}">4 trụ TMMT cốt lõi: ${coreDone}/${coreKeys.length}</li>
      <li class="${filled >= tmmtMinFilled ? "is-done" : ""}">Chi tiết TMMT: ${filled}/${total} (tối thiểu ${tmmtMinFilled})</li>`;
  }

  function renderPanel(payload) {
    planData = payload || planData;
    const wrap = $("crm-svc-tmmt-panel");
    const fieldsEl = $("crm-svc-tmmt-fields");
    const statusEl = $("crm-svc-tmmt-status");
    const errEl = $("crm-svc-tmmt-err");
    const gateEl = $("crm-svc-tmmt-gate-banner");
    if (!wrap || !fieldsEl) return;

    if (errEl) {
      errEl.hidden = true;
      errEl.textContent = "";
    }

    const plan = planData?.plan;
    const validation = planData?.validation || {};
    if (!plan) {
      wrap.hidden = false;
      fieldsEl.innerHTML =
        '<p class="muted">Chưa có Kế hoạch MKT chính thức — promote từ pre-sales hoặc liên kết plan trên lifecycle.</p>';
      if (statusEl) statusEl.textContent = "Chưa có plan";
      renderChecklist(validation, {});
      if (gateEl) gateEl.hidden = true;
      return;
    }

    wrap.hidden = false;
    const sf = plan.strategy_framework || {};
    const prof = plan.target_market_prof || {};
    const statusColor = validation.complete ? "#166534" : "#b45309";
    if (statusEl) {
      statusEl.innerHTML = `<span style="color:${statusColor};font-weight:600;">${
        validation.complete ? "Đủ điều kiện Deliver" : "Chưa đủ TMMT"
      }</span>`;
    }

    if (gateEl) {
      gateEl.hidden = !!validation.complete;
      if (!validation.complete && validation.messages?.length) {
        gateEl.textContent = validation.messages.join(" · ");
      }
    }

    renderChecklist(validation, prof);

    const coreFields = coreKeys
      .map((key) => {
        const label = profLabels[key] || key;
        return `<label class="crm-svc-tmmt-field"><span>${esc(label)}</span>
          <textarea rows="2" class="crm-svc-tmmt-input" data-tmmt-prof="${esc(key)}">${esc(prof[key] || "")}</textarea></label>`;
      })
      .join("");

    const otherKeys = Object.keys(profLabels).filter((k) => !coreKeys.includes(k));
    const otherFields = otherKeys
      .map((key) => {
        const label = profLabels[key] || key;
        return `<label class="crm-svc-tmmt-field crm-svc-tmmt-field--compact"><span>${esc(label)}</span>
          <textarea rows="2" class="crm-svc-tmmt-input" data-tmmt-prof="${esc(key)}">${esc(prof[key] || "")}</textarea></label>`;
      })
      .join("");

    fieldsEl.innerHTML = `
      <label class="crm-svc-tmmt-field"><span>${esc(strategyLabels.target_market || "TMMT tóm tắt")}</span>
        <textarea rows="3" class="crm-svc-tmmt-input" data-tmmt-sf="target_market">${esc(sf.target_market || "")}</textarea>
      </label>
      <div class="crm-svc-tmmt-section">
        <strong>TMMT chi tiết — 4 trụ cốt lõi</strong>
        ${coreFields}
      </div>
      <details class="crm-svc-tmmt-more">
        <summary>Các trường TMMT khác (${otherKeys.length})</summary>
        ${otherFields}
      </details>
      ${
        validation.messages?.length && !validation.complete
          ? `<ul class="crm-svc-tmmt-msgs">${validation.messages
              .map((m) => `<li>${esc(m)}</li>`)
              .join("")}</ul>`
          : ""
      }
      <div class="crm-svc-tmmt-actions">
        <button type="button" class="btn btn-sm" id="crm-svc-tmmt-save">Lưu TMMT</button>
        ${
          plan.id
            ? `<a href="/crm/marketing-plan" class="btn btn-secondary btn-sm" target="_blank" rel="noopener">Mở editor đầy đủ</a>`
            : ""
        }
      </div>`;

    $("crm-svc-tmmt-save")?.addEventListener("click", saveTmmt);
  }

  async function saveTmmt() {
    const errEl = $("crm-svc-tmmt-err");
    if (errEl) {
      errEl.hidden = true;
      errEl.textContent = "";
    }
    const body = { strategy_framework: {}, target_market_prof: {} };
    document.querySelectorAll(".crm-svc-tmmt-input[data-tmmt-sf]").forEach((el) => {
      body.strategy_framework[el.dataset.tmmtSf] = el.value;
    });
    document.querySelectorAll(".crm-svc-tmmt-input[data-tmmt-prof]").forEach((el) => {
      body.target_market_prof[el.dataset.tmmtProf] = el.value;
    });
    try {
      const data = await reqJson(`/api/crm/service-lifecycle/${lifecycleId}/marketing-plan`, {
        method: "PATCH",
        body: JSON.stringify(body),
      });
      renderPanel(data);
      const hint = $("svc-advance-hint");
      if (hint && data.validation) {
        if (data.validation.complete) {
          hint.style.display = "none";
        } else if (data.validation.messages?.[0]) {
          hint.style.display = "block";
          hint.style.color = "#b45309";
          hint.textContent = data.validation.messages[0];
        }
      }
      const advBtn = $("svc-advance-next-btn");
      if (advBtn && data.validation?.complete) {
        advBtn.disabled = false;
        advBtn.style.background = "#6366f1";
        advBtn.style.cursor = "pointer";
      }
    } catch (e) {
      if (errEl) {
        errEl.textContent = e instanceof Error ? e.message : String(e);
        errEl.hidden = false;
      }
    }
  }

  renderPanel(initialPayload);
})();
