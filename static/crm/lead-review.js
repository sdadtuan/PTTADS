/** @file GDKD inbox tra soát B2 (P1). */
(function (global) {
  "use strict";

  function createCrmLeadReview(ctx) {
    const {
      $,
      esc,
      canManageReviewQueue,
      formatViDateTime,
      reqJson,
      getSelectedId,
      getSelectedLead,
      setSelectedLead,
      renderDetail,
      loadLeads,
      loadStats,
      fillOwnerSelectForLead,
      getLeadsListPage,
      setLeadsListPage,
    } = ctx;

    function enableReviewQueueFilter() {
      const cb = $("crm-leads-review-only");
      if (cb) cb.checked = true;
      setLeadsListPage(1);
      loadLeads().catch(() => {});
      $("crm-leads-review-inbox")?.scrollIntoView({ behavior: "smooth", block: "nearest" });
    }

    function renderReviewInboxBanner(stats) {
      const banner = $("crm-leads-review-inbox");
      const countEl = $("crm-leads-review-inbox-count");
      if (!banner || !canManageReviewQueue) return;
      const n = Number(stats?.review_queue_count || 0);
      banner.hidden = n <= 0;
      if (countEl) countEl.textContent = String(n);
    }

    function bindReviewInboxUi() {
      $("crm-leads-review-inbox-open")?.addEventListener("click", enableReviewQueueFilter);
      $("crm-leads-stats")?.addEventListener("click", (ev) => {
        if (ev.target.closest(".crm-leads-stat--review")) enableReviewQueueFilter();
      });
    }

    function renderReviewQueuePanel(lead) {
      const panel = $("crm-leads-review-panel");
      if (!panel || !lead || !canManageReviewQueue) return;
      const rq = lead.review_queue || {};
      if (!rq.active) {
        panel.hidden = true;
        return;
      }
      panel.hidden = false;
      const msgEl = $("crm-leads-review-msg");
      if (msgEl) msgEl.textContent = rq.message || "Lead phải tra soát — quá hạn B2 chưa Liên hệ OK.";
      const metaEl = $("crm-leads-review-meta");
      if (metaEl) {
        metaEl.innerHTML = `
        <div><dt>Thu hồi lúc</dt><dd>${esc(formatViDateTime(rq.queued_at))}</dd></div>
        <div><dt>Phân công lúc</dt><dd>${esc(formatViDateTime(rq.assigned_at))}</dd></div>
        <div><dt>Thời hạn</dt><dd>${esc(String(rq.deadline_hours || 24))} giờ</dd></div>
        <div><dt>AM trước</dt><dd>${rq.previous_owner_id ? `#${rq.previous_owner_id}` : "—"}</dd></div>`;
      }
      const actions = $("crm-leads-review-actions");
      if (actions) actions.hidden = false;
      fillOwnerSelectForLead(lead).catch(() => {});
      const reviewOwner = $("crm-leads-review-owner");
      const mainOwner = $("crm-leads-f-owner");
      if (reviewOwner && mainOwner && reviewOwner.options.length <= 1) {
        reviewOwner.innerHTML = mainOwner.innerHTML;
      }
    }

    async function releaseReviewQueue(mode) {
      const selectedId = getSelectedId();
      const selectedLead = getSelectedLead();
      if (!selectedId || !selectedLead) return;
      const errEl = $("crm-leads-review-err");
      const okEl = $("crm-leads-review-ok");
      if (errEl) errEl.hidden = true;
      if (okEl) okEl.hidden = true;
      const payload = { mode, note: "" };
      if (mode === "manual") {
        const ownerId = Number($("crm-leads-review-owner")?.value || 0);
        if (!ownerId) {
          if (errEl) {
            errEl.textContent = "Chọn AM để gán lại.";
            errEl.hidden = false;
          }
          return;
        }
        payload.owner_id = ownerId;
      }
      try {
        const res = await reqJson(`/api/crm/leads/${selectedId}/review-queue/release`, {
          method: "POST",
          body: JSON.stringify(payload),
        });
        if (res.lead) {
          setSelectedLead(res.lead);
          renderDetail(res.lead);
        }
        if (okEl) okEl.hidden = false;
        await loadLeads();
        await loadStats();
      } catch (err) {
        if (errEl) {
          errEl.textContent = err.message || "Lỗi tra soát.";
          errEl.hidden = false;
        }
      }
    }

    return {
      enableReviewQueueFilter,
      renderReviewInboxBanner,
      bindReviewInboxUi,
      renderReviewQueuePanel,
      releaseReviewQueue,
    };
  }

  global.createCrmLeadReview = createCrmLeadReview;
})(window);
