(function () {
  "use strict";

  var STATUS_LABELS = {
    active: "Hoạt động",
    onboarding: "Onboarding",
    paused: "Tạm dừng",
    prospect: "Tiềm năng",
  };

  var TOKEN_LABELS = {
    valid: "OK",
    expiring: "Sắp hết hạn",
    expired: "Hết hạn",
    missing: "Thiếu token",
    none: "Chưa có kênh",
    revoked: "Thu hồi",
    unknown: "—",
  };

  var state = { days: 7, status: "" };

  function esc(s) {
    var d = document.createElement("div");
    d.textContent = s == null ? "" : String(s);
    return d.innerHTML;
  }

  function fmtVnd(n) {
    if (n == null || n === "") return "—";
    var v = Number(n);
    if (isNaN(v)) return "—";
    return Math.round(v).toLocaleString("vi-VN") + " \u20ab";
  }

  function fmtDate(iso) {
    if (!iso) return "—";
    var p = String(iso).slice(0, 10).split("-");
    if (p.length !== 3) return iso;
    return p[2] + "/" + p[1] + "/" + p[0];
  }

  function tokenBadge(status) {
    var label = TOKEN_LABELS[status] || status || "—";
    var cls = "agency-token-badge agency-token-badge--valid";
    if (status === "expiring") cls = "agency-token-badge agency-token-badge--expiring";
    else if (status === "expired" || status === "revoked") cls = "agency-token-badge agency-token-badge--expired";
    else if (status === "missing" || status === "none" || status === "unknown") cls = "agency-token-badge agency-token-badge--unknown";
    return '<span class="' + cls + '">' + esc(label) + "</span>";
  }

  function clientStatusBadge(status) {
    var label = STATUS_LABELS[status] || status || "—";
    var cls = "agency-badge agency-badge--active";
    if (status === "onboarding") cls = "agency-badge agency-badge--onboarding";
    else if (status === "paused") cls = "agency-badge agency-badge--paused";
    else if (status === "prospect") cls = "agency-badge agency-badge--prospect";
    return '<span class="' + cls + '">' + esc(label) + "</span>";
  }

  function renderAlerts(alerts) {
    var box = document.getElementById("fb-hub-alerts");
    if (!box) return;
    if (!alerts || !alerts.length) {
      box.innerHTML = "";
      return;
    }
    box.innerHTML = alerts
      .map(function (a) {
        var cls = a.severity === "danger" ? "agency-banner--danger" : "agency-banner--warn";
        return (
          '<div class="agency-banner ' +
          cls +
          '">' +
          esc(a.message) +
          ' <a href="' +
          esc(a.link) +
          '">' +
          esc(a.link_label || "Xem") +
          "</a></div>"
        );
      })
      .join("");
  }

  function renderStats(summary) {
    document.getElementById("fb-stat-clients").textContent = summary.meta_clients ?? "0";
    document.getElementById("fb-stat-spend").textContent = fmtVnd(summary.total_spend);
    document.getElementById("fb-stat-leads").textContent = Number(summary.total_leads || 0).toLocaleString("vi-VN");
    document.getElementById("fb-stat-cpl").textContent = fmtVnd(summary.avg_cpl);
    var tokenIssues = (summary.token_expired || 0) + (summary.token_expiring || 0) + (summary.no_token_clients || 0);
    var tokenEl = document.getElementById("fb-stat-token");
    tokenEl.textContent = String(tokenIssues);
    tokenEl.closest(".agency-stat-card").classList.toggle("agency-stat-card--warn", tokenIssues > 0);
    var unmappedEl = document.getElementById("fb-stat-unmapped");
    unmappedEl.textContent = String(summary.unmapped_campaigns || 0);
    unmappedEl.closest(".agency-stat-card").classList.toggle("agency-stat-card--warn", (summary.unmapped_campaigns || 0) > 0);
  }

  function renderClients(clients) {
    var body = document.getElementById("fb-hub-clients-body");
    if (!body) return;
    if (!clients || !clients.length) {
      body.innerHTML =
        '<tr><td colspan="9" class="agency-muted">Chưa có client Meta — thêm kênh tại Agency Ops → Client → tab Kênh ads.</td></tr>';
      return;
    }
    body.innerHTML = clients
      .map(function (c) {
        var acct = c.ad_account_id
          ? esc(c.ad_account_id) + (c.ad_account_name ? '<div class="agency-muted">' + esc(c.ad_account_name) + "</div>" : "")
          : '<span class="agency-muted">—</span>';
        var overCls = c.over_target_rows > 0 ? ' class="agency-cpl-over"' : "";
        return (
          "<tr>" +
          "<td><a href=\"" +
          esc(c.detail_url) +
          '"><strong>' +
          esc(c.code) +
          "</strong></a><div class=\"agency-muted\">" +
          esc(c.name) +
          "</div></td>" +
          "<td>" +
          clientStatusBadge(c.status) +
          "</td>" +
          "<td>" +
          acct +
          "</td>" +
          "<td>" +
          tokenBadge(c.token_status) +
          (c.token_expires_at
            ? '<div class="agency-muted">' + esc(fmtDate(c.token_expires_at.slice(0, 10))) + "</div>"
            : "") +
          "</td>" +
          '<td class="num">' +
          fmtVnd(c.spend) +
          "</td>" +
          '<td class="num">' +
          Number(c.leads_crm || 0).toLocaleString("vi-VN") +
          "</td>" +
          "<td class=\"num\"" +
          overCls +
          ">" +
          fmtVnd(c.cpl) +
          (c.over_target_rows > 0
            ? ' <span class="agency-muted" title="CPL vượt target">⚠</span>'
            : "") +
          "</td>" +
          '<td class="num">' +
          esc(String(c.campaigns || 0)) +
          (c.unmapped_campaigns > 0
            ? ' <span class="agency-muted">(' + esc(String(c.unmapped_campaigns)) + " chưa map)</span>"
            : "") +
          "</td>" +
          '<td class="agency-row-actions">' +
          '<a class="btn btn-secondary btn-sm" href="' +
          esc(c.channels_url) +
          '">Kênh</a> ' +
          '<a class="btn btn-secondary btn-sm" href="' +
          esc(c.performance_url) +
          '">CPL</a>' +
          "</td>" +
          "</tr>"
        );
      })
      .join("");
  }

  function setWindowButtons(days) {
    document.querySelectorAll("[data-fb-window]").forEach(function (btn) {
      var d = Number(btn.getAttribute("data-fb-window"));
      btn.classList.toggle("btn-secondary", d !== days);
      btn.classList.toggle("btn", d === days);
    });
  }

  function loadHub() {
    var qs = "?days=" + encodeURIComponent(String(state.days));
    if (state.status) qs += "&status=" + encodeURIComponent(state.status);
    var body = document.getElementById("fb-hub-clients-body");
    if (body) body.innerHTML = '<tr><td colspan="9" class="agency-muted">Đang tải…</td></tr>';

    fetch("/api/v1/facebook-ads/hub" + qs, { credentials: "same-origin" })
      .then(function (r) {
        return r.json().then(function (j) {
          return { ok: r.ok, data: j };
        });
      })
      .then(function (res) {
        var data = res.data || {};
        var pgBanner = document.getElementById("fb-hub-pg-banner");
        if (!res.ok || !data.ok) {
          if (pgBanner) pgBanner.hidden = false;
          renderAlerts([]);
          renderClients([]);
          return;
        }
        if (pgBanner) pgBanner.hidden = true;
        var period = document.getElementById("fb-hub-period");
        if (period) {
          period.textContent =
            fmtDate(data.date_from) + " → " + fmtDate(data.date_to) + " · T-" + String(data.window_days || state.days);
        }
        renderStats(data.summary || {});
        renderAlerts(data.alerts || []);
        renderClients(data.clients || []);
      })
      .catch(function () {
        var pgBanner = document.getElementById("fb-hub-pg-banner");
        if (pgBanner) pgBanner.hidden = false;
        renderClients([]);
      });
  }

  function init() {
    if (!document.querySelector("[data-fb-hub-page]")) return;

    document.querySelectorAll("[data-fb-window]").forEach(function (btn) {
      btn.addEventListener("click", function () {
        state.days = Number(btn.getAttribute("data-fb-window")) || 7;
        setWindowButtons(state.days);
        loadHub();
      });
    });

    var refresh = document.getElementById("fb-hub-refresh");
    if (refresh) refresh.addEventListener("click", loadHub);

    var statusSel = document.getElementById("fb-hub-status");
    if (statusSel) {
      statusSel.addEventListener("change", function () {
        state.status = statusSel.value || "";
        loadHub();
      });
    }

    setWindowButtons(state.days);
    loadHub();
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", init);
  } else {
    init();
  }
})();
