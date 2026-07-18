(function () {
  "use strict";

  var STATUS_LABELS = {
    onboarding: "Đang onboard",
    active: "Hoạt động",
    paused: "Tạm dừng",
    prospect: "Tiềm năng",
    pending: "Chờ xử lý",
    running: "Đang chạy",
    done: "Hoàn thành",
    failed: "Lỗi",
    dead: "DLQ",
  };

  var CATEGORY_LABELS = {
    sla: "SLA",
    ingest: "Ingest",
    system: "Hệ thống",
  };

  function esc(s) {
    var d = document.createElement("div");
    d.textContent = s == null ? "" : String(s);
    return d.innerHTML;
  }

  function fmtTime(iso) {
    if (!iso) return "—";
    return String(iso).slice(0, 16).replace("T", " ");
  }

  function fmtVnd(n) {
    if (n == null || n === "") return "—";
    var v = Number(n);
    if (isNaN(v)) return "—";
    return Math.round(v).toLocaleString("vi-VN") + " \u20ab";
  }

  function fmtCpl(n) {
    if (n == null || n === "") return "—";
    var v = Number(n);
    if (isNaN(v)) return "—";
    return Math.round(v).toLocaleString("vi-VN") + " \u20ab";
  }

  function fmtRoas(row) {
    if (row.roas != null && row.roas !== "") {
      return Number(row.roas).toFixed(2) + "×";
    }
    if (row.roas_stub) {
      return '<span class="agency-muted" title="conversion_value=0 — chờ CAPI Purchase / CRM revenue">stub</span>';
    }
    return "—";
  }

  function cplDeltaBadge(row) {
    if (row.cpl == null || row.target_cpl_vnd == null) {
      return '<span class="agency-cpl-delta agency-cpl-delta--na">—</span>';
    }
    var pct = row.cpl_delta_pct;
    if (pct == null) return '<span class="agency-cpl-delta agency-cpl-delta--na">—</span>';
    var cls = "agency-cpl-delta--ok";
    var label = pct <= 0 ? (Math.abs(pct).toFixed(1) + "% dưới target") : ("+" + pct.toFixed(1) + "%");
    if (pct > 0 && pct <= 10) cls = "agency-cpl-delta--warn";
    else if (pct > 10) cls = "agency-cpl-delta--bad";
    else label = "Đạt target";
    return '<span class="agency-cpl-delta ' + cls + '">' + esc(label) + "</span>";
  }

  function defaultPerfDates() {
    var end = new Date();
    end.setDate(end.getDate() - 1);
    var start = new Date(end);
    start.setDate(start.getDate() - 6);
    function iso(d) {
      return d.toISOString().slice(0, 10);
    }
    return { from: iso(start), to: iso(end) };
  }

  function relTime(iso) {
    if (!iso) return "";
    var t = new Date(iso).getTime();
    if (isNaN(t)) return fmtTime(iso);
    var diff = Math.max(0, Date.now() - t);
    var m = Math.floor(diff / 60000);
    if (m < 1) return "Vừa xong";
    if (m < 60) return m + " phút trước";
    var h = Math.floor(m / 60);
    if (h < 24) return h + " giờ trước";
    return fmtTime(iso);
  }

  function toast(msg, ok) {
    var root = document.getElementById("agency-toast-root");
    if (!root) return;
    var el = document.createElement("div");
    el.className = "agency-toast " + (ok !== false ? "agency-toast--ok" : "agency-toast--err");
    el.textContent = msg;
    root.appendChild(el);
    setTimeout(function () {
      el.remove();
    }, 4200);
  }

  function statusBadge(status) {
    var s = String(status || "").toLowerCase();
    var cls = "agency-badge";
    if (s === "active" || s === "done") cls += " agency-badge--" + s;
    else if (s === "onboarding" || s === "running") cls += " agency-badge--" + s;
    else if (s === "paused" || s === "dead" || s === "failed") cls += " agency-badge--" + s;
    else if (s === "pending") cls += " agency-badge--pending";
    else cls += " agency-badge--" + (s || "prospect");
    return '<span class="' + cls + '">' + esc(STATUS_LABELS[s] || s || "—") + "</span>";
  }

  function tokenBadge(status) {
    var s = String(status || "unknown").toLowerCase();
    var labels = {
      valid: "Token OK",
      expiring: "Sắp hết hạn",
      expired: "Hết hạn",
      revoked: "Thu hồi",
      unknown: "Chưa có token",
    };
    return '<span class="agency-token-badge agency-token-badge--' + s + '">' +
      esc(labels[s] || s) + "</span>";
  }

  function channelBadge(channel) {
    var ch = String(channel || "meta").toLowerCase();
    var label = ch === "google" ? "Google" : ch === "meta" ? "Meta" : ch;
    return '<span class="agency-badge agency-badge--' + esc(ch) + '">' + esc(label) + "</span>";
  }

  function renderChannelAccounts(accounts, clientId) {
    var chList = document.getElementById("agency-ch-list");
    if (!chList) return;
    chList.innerHTML = (accounts || []).map(function (a) {
      var isMeta = String(a.channel || "") === "meta";
      var isGoogle = String(a.channel || "") === "google";
      var tokenForm = isMeta
        ? (
          '<form class="agency-ch-token-form" data-account-id="' + esc(a.id) + '">' +
          '<label>Token mới<input type="password" name="access_token" placeholder="EAA…" autocomplete="new-password"></label>' +
          '<label>Hết hạn<input type="date" name="token_expires_at"></label>' +
          '<button type="submit" class="btn btn-secondary">Lưu token</button>' +
          (a.has_token ? ' <button type="button" class="btn agency-ch-revoke" data-account-id="' + esc(a.id) + '">Thu hồi</button>' : "") +
          "</form>" +
          '<form class="agency-ch-pixel-form" data-account-id="' + esc(a.id) + '">' +
          '<label>Meta Pixel ID<input type="text" name="pixel_id" inputmode="numeric" placeholder="123456789012345" value="' +
          esc(String(a.pixel_id || "")) + '" maxlength="20"></label>' +
          '<button type="submit" class="btn btn-secondary">Lưu pixel</button>' +
          (a.pixel_configured ? ' <span class="agency-muted">CAPI/tracking</span>' : "") +
          "</form>"
        )
        : isGoogle
        ? (
          '<div class="agency-ch-google-oauth">' +
          '<button type="button" class="btn btn-secondary agency-ch-google-connect" data-account-id="' + esc(a.id) + '">' +
          (a.has_token ? "Kết nối lại Google Ads" : "Kết nối Google Ads (OAuth)") +
          "</button></div>"
        )
        : "";
      return (
        "<li>" +
        '<div class="agency-ch-row-top">' +
        "<span><strong>" + esc(a.channel) + "</strong> · " + esc(a.display_name || a.external_account_id) +
        (isMeta ? " " + tokenBadge(a.token_status) : "") + "</span>" +
        "<code>" + esc(a.external_account_id) + "</code></div>" +
        (a.token_expires_at ? '<span class="agency-muted" style="font-size:0.75rem">Hết hạn: ' + esc(String(a.token_expires_at).slice(0, 10)) + "</span>" : "") +
        (a.credential_ref ? '<span class="agency-muted" style="font-size:0.75rem">Env: ' + esc(a.credential_ref) + "</span>" : "") +
        tokenForm +
        "</li>"
      );
    }).join("") || "<li class=\"agency-muted\">Chưa liên kết kênh quảng cáo</li>";

    chList.querySelectorAll(".agency-ch-google-connect").forEach(function (btn) {
      btn.addEventListener("click", function () {
        var accountId = btn.getAttribute("data-account-id") || "";
        var q = accountId ? "?account_id=" + encodeURIComponent(accountId) : "";
        api("/api/v1/clients/" + clientId + "/google/oauth/url" + q)
          .then(function (r) {
            if (r.authorization_url) {
              window.location.href = r.authorization_url;
            } else {
              toast("Không lấy được OAuth URL", false);
            }
          })
          .catch(function (e) { toast(e.message, false); });
      });
    });

    chList.querySelectorAll(".agency-ch-token-form").forEach(function (form) {
      form.addEventListener("submit", function (ev) {
        ev.preventDefault();
        var accountId = form.getAttribute("data-account-id");
        var token = form.querySelector('[name="access_token"]').value.trim();
        var exp = form.querySelector('[name="token_expires_at"]').value;
        if (!token) {
          toast("Nhập access token Meta", false);
          return;
        }
        api("/api/v1/clients/" + clientId + "/channel-accounts/" + accountId + "/token", {
          method: "PATCH",
          body: JSON.stringify({
            access_token: token,
            token_expires_at: exp || null,
          }),
        }).then(function () {
          toast("Đã lưu token (mã hóa vault)");
          form.querySelector('[name="access_token"]').value = "";
          load();
        }).catch(function (e) { toast(e.message, false); });
      });
    });

    chList.querySelectorAll(".agency-ch-revoke").forEach(function (btn) {
      btn.addEventListener("click", function () {
        if (!confirm("Thu hồi token Meta cho account này?")) return;
        var accountId = btn.getAttribute("data-account-id");
        api("/api/v1/clients/" + clientId + "/channel-accounts/" + accountId + "/token", {
          method: "PATCH",
          body: JSON.stringify({ revoke: true }),
        }).then(function () {
          toast("Đã thu hồi token");
          load();
        }).catch(function (e) { toast(e.message, false); });
      });
    });

    chList.querySelectorAll(".agency-ch-pixel-form").forEach(function (form) {
      form.addEventListener("submit", function (ev) {
        ev.preventDefault();
        var accountId = form.getAttribute("data-account-id");
        var pixel = form.querySelector('[name="pixel_id"]').value.trim();
        if (!pixel) {
          toast("Nhập Meta Pixel ID", false);
          return;
        }
        api("/api/v1/clients/" + clientId + "/channel-accounts/" + accountId + "/meta", {
          method: "PATCH",
          body: JSON.stringify({ pixel_id: pixel }),
        }).then(function () {
          toast("Đã lưu Pixel ID");
          load();
        }).catch(function (e) { toast(e.message, false); });
      });
    });
  }

  function api(path, opts) {
    return fetch(path, Object.assign({
      credentials: "same-origin",
      headers: { "Content-Type": "application/json", Accept: "application/json" },
    }, opts || {})).then(function (res) {
      return res.json().catch(function () { return {}; }).then(function (data) {
        if (res.status === 401 && data.login) {
          window.location.href = data.login;
          throw new Error("Chưa đăng nhập");
        }
        if (!res.ok) throw new Error(data.error || data.hint || res.statusText || "Lỗi mạng");
        return data;
      });
    });
  }

  function skeletonRows(cols, n) {
    var rows = "";
    for (var i = 0; i < n; i++) {
      rows += "<tr class='agency-skeleton-row'>";
      for (var j = 0; j < cols; j++) rows += "<td><div class='agency-skeleton'></div></td>";
      rows += "</tr>";
    }
    return rows;
  }

  function emptyState(title, desc, ctaHtml) {
    return (
      '<div class="agency-empty">' +
      '<div class="agency-empty-icon" aria-hidden="true">◇</div>' +
      "<p class=\"agency-empty-title\">" + esc(title) + "</p>" +
      (desc ? "<p class=\"agency-empty-desc\">" + esc(desc) + "</p>" : "") +
      (ctaHtml || "") +
      "</div>"
    );
  }

  function bindModals() {
    document.querySelectorAll("[data-agency-modal-close]").forEach(function (el) {
      el.addEventListener("click", function () {
        var modal = el.closest(".agency-modal-root");
        if (modal) modal.hidden = true;
      });
    });
  }

  function openModal(id) {
    var m = document.getElementById(id);
    if (m) m.hidden = false;
  }

  function closeModal(id) {
    var m = document.getElementById(id);
    if (m) m.hidden = true;
  }

  function bindTabs(tabsEl, panesRoot) {
    if (!tabsEl) return;
    panesRoot = panesRoot || tabsEl.closest(".agency-wrap") || document;
    tabsEl.querySelectorAll(".agency-tab").forEach(function (btn) {
      btn.addEventListener("click", function () {
        var tab = btn.getAttribute("data-tab");
        tabsEl.querySelectorAll(".agency-tab").forEach(function (b) {
          b.classList.toggle("is-active", b === btn);
        });
        panesRoot.querySelectorAll(".agency-tab-pane").forEach(function (pane) {
          pane.hidden = pane.getAttribute("data-tab-pane") !== tab;
        });
      });
    });
  }

  var root = document.querySelector("[data-agency-page]");
  if (!root) return;

  bindModals();
  var page = root.getAttribute("data-agency-page");

  if (page === "dashboard") {
    var feedEl = document.getElementById("agency-activity-feed");
    var slaEl = document.getElementById("agency-stat-sla");

    Promise.all([
      api("/api/v1/jobs?limit=8").catch(function () { return { jobs: [] }; }),
      api("/api/v1/notifications?unread=1").catch(function () { return { notifications: [] }; }),
    ]).then(function (results) {
      var jobs = results[0].jobs || [];
      var notifs = results[1].notifications || [];
      var slaUnread = notifs.filter(function (n) { return n.category === "sla"; }).length;
      if (slaEl) slaEl.textContent = String(slaUnread);

      var items = [];
      jobs.forEach(function (j) {
        items.push({
          ts: j.created_at,
          kind: j.status === "dead" || j.status === "failed" ? "err" : "ok",
          text: j.job_type + " · " + (j.channel || "—") + " · " + statusBadge(j.status),
          link: "/crm/agency/ingest?status=" + encodeURIComponent(j.status || ""),
        });
      });
      notifs.slice(0, 5).forEach(function (n) {
        items.push({
          ts: n.created_at,
          kind: n.category === "sla" ? "err" : "info",
          text: n.title,
          link: n.link_url || "/crm/agency/notifications",
        });
      });
      items.sort(function (a, b) { return String(b.ts).localeCompare(String(a.ts)); });

      if (!feedEl) return;
      if (!items.length) {
        feedEl.innerHTML = emptyState("Chưa có hoạt động", "Webhook và SLA sẽ hiển thị tại đây.");
        return;
      }
      feedEl.innerHTML =
        '<ul class="agency-activity-list">' +
        items.slice(0, 10).map(function (it) {
          return (
            '<li class="agency-activity-item">' +
            '<span class="agency-activity-dot agency-activity-dot--' + it.kind + '"></span>' +
            '<div class="agency-activity-main"><a href="' + esc(it.link) + '">' + it.text + "</a></div>" +
            '<span class="agency-activity-time">' + esc(relTime(it.ts)) + "</span></li>"
          );
        }).join("") +
        "</ul>";
    });
  }

  if (page === "clients") {
    var tbody = document.querySelector("#agency-clients-table tbody");
    var form = document.getElementById("agency-client-form");

    document.getElementById("agency-btn-new-client").addEventListener("click", function () {
      form.hidden = !form.hidden;
      if (!form.hidden) document.getElementById("agency-f-code").focus();
    });
    if (root.getAttribute("data-is-new") === "1") form.hidden = false;

    function load() {
      var wrap = document.getElementById("agency-clients-table-wrap");
      var emptyEl = document.getElementById("agency-clients-empty");
      if (tbody) tbody.innerHTML = skeletonRows(7, 5);
      var q = document.getElementById("agency-client-search").value.trim();
      var st = document.getElementById("agency-client-status").value;
      var am = document.getElementById("agency-client-am").value.trim();
      var ind = document.getElementById("agency-client-industry").value.trim();
      var url = "/api/v1/clients?";
      if (q) url += "q=" + encodeURIComponent(q) + "&";
      if (st) url += "status=" + encodeURIComponent(st) + "&";
      if (am) url += "owner_am_id=" + encodeURIComponent(am) + "&";
      if (ind) url += "industry=" + encodeURIComponent(ind);
      api(url).then(function (data) {
        var list = data.clients || [];
        if (!list.length) {
          if (wrap) wrap.hidden = true;
          if (emptyEl) {
            emptyEl.hidden = false;
            emptyEl.innerHTML = emptyState(
              "Chưa có khách hàng agency",
              "Tạo client đầu tiên để bắt đầu onboarding.",
              '<button type="button" class="btn" id="agency-empty-create">+ Tạo client đầu tiên</button>'
            );
            var btn = document.getElementById("agency-empty-create");
            if (btn) btn.addEventListener("click", function () {
              form.hidden = false;
              document.getElementById("agency-f-code").focus();
            });
          }
          return;
        }
        if (wrap) wrap.hidden = false;
        if (emptyEl) emptyEl.hidden = true;
        tbody.innerHTML = list.map(function (c) {
          return (
            "<tr><td><a href=\"/crm/agency/clients/" + esc(c.id) + "\">" + esc(c.code) + "</a></td>" +
            "<td>" + esc(c.name) + "</td>" +
            "<td>" + esc(c.owner_am_id || "—") + "</td>" +
            "<td>" + esc(c.industry_slug || "—") + "</td>" +
            "<td>" + statusBadge(c.status) + "</td>" +
            "<td>" + esc(c.channels || "—") + "</td>" +
            "<td>" + esc(fmtTime(c.updated_at)) + "</td></tr>"
          );
        }).join("");
      }).catch(function (e) {
        if (tbody) tbody.innerHTML = "<tr><td colspan=\"7\" class=\"agency-error\">" + esc(e.message) + "</td></tr>";
      });
    }

    ["agency-client-search", "agency-client-am", "agency-client-industry"].forEach(function (id) {
      var el = document.getElementById(id);
      if (el) el.addEventListener("input", debounce(load, 300));
    });
    document.getElementById("agency-client-status").addEventListener("change", load);
    document.getElementById("agency-client-refresh").addEventListener("click", load);

    document.getElementById("agency-f-submit").addEventListener("click", function () {
      var err = document.getElementById("agency-f-error");
      err.hidden = true;
      api("/api/v1/clients", {
        method: "POST",
        body: JSON.stringify({
          code: document.getElementById("agency-f-code").value,
          name: document.getElementById("agency-f-name").value,
          industry_slug: document.getElementById("agency-f-industry").value,
          owner_am_id: document.getElementById("agency-f-am").value,
        }),
      }).then(function (client) {
        toast("Client đã được tạo");
        window.location.href = "/crm/agency/clients/" + client.id;
      }).catch(function (e) {
        err.textContent = e.message;
        err.hidden = false;
      });
    });
    load();
  }

  if (page === "client-detail") {
    var clientId = root.getAttribute("data-client-id");
    var checklist = document.getElementById("agency-checklist");
    var activateBtn = document.getElementById("agency-btn-activate");
    var clientTabs = document.getElementById("agency-client-tabs");
    bindTabs(clientTabs, root);
    var hashTab = (location.hash || "").replace(/^#/, "");
    if (hashTab && clientTabs) {
      var hashBtn = clientTabs.querySelector('.agency-tab[data-tab="' + hashTab + '"]');
      if (hashBtn) hashBtn.click();
    }
    var leadsLoaded = false;
    var perfLoaded = false;
    var leadsTabBtn = document.querySelector('#agency-client-tabs .agency-tab[data-tab="leads"]');
    var perfTabBtn = document.querySelector('#agency-client-tabs .agency-tab[data-tab="performance"]');

    function loadClientPerformance() {
      var tbody = document.getElementById("agency-perf-body");
      var statsEl = document.getElementById("agency-perf-stats");
      var banner = document.getElementById("agency-perf-banner");
      var thead = document.getElementById("agency-perf-thead");
      if (!tbody) return;

      var fromEl = document.getElementById("agency-perf-from");
      var toEl = document.getElementById("agency-perf-to");
      var groupEl = document.getElementById("agency-perf-group");
      var dates = defaultPerfDates();
      if (fromEl && !fromEl.value) fromEl.value = dates.from;
      if (toEl && !toEl.value) toEl.value = dates.to;

      var groupBy = groupEl ? groupEl.value : "day";
      var url = "/api/v1/clients/" + clientId + "/performance?from=" +
        encodeURIComponent(fromEl.value) + "&to=" + encodeURIComponent(toEl.value) +
        "&group_by=" + encodeURIComponent(groupBy);

      if (thead) {
        thead.innerHTML = groupBy === "campaign"
          ? "<tr><th>Kênh</th><th>Campaign</th><th>Spend</th><th>Leads CRM</th><th>CPL</th><th>ROAS</th><th>Target CPL</th><th>Δ vs target</th><th>Hub</th></tr>"
          : "<tr><th>Ngày</th><th>Kênh</th><th>Campaign</th><th>Spend</th><th>Leads CRM</th><th>CPL</th><th>ROAS</th><th>Target CPL</th><th>Δ vs target</th><th>Hub</th></tr>";
      }
      tbody.innerHTML = skeletonRows(groupBy === "campaign" ? 9 : 10, 5);
      if (statsEl) statsEl.innerHTML = "";
      if (banner) banner.hidden = true;

      api(url).then(function (data) {
        var rows = data.rows || [];
        var summary = data.summary || {};
        if (perfTabBtn) {
          perfTabBtn.textContent = rows.length
            ? "Campaign CPL (" + rows.length + ")"
            : "Campaign CPL";
        }
        if (statsEl) {
          statsEl.innerHTML = [
            { label: "Tổng spend", value: fmtVnd(summary.total_spend) },
            { label: "Leads CRM", value: String(summary.total_leads_crm || 0) },
            { label: "CPL TB", value: fmtCpl(summary.avg_cpl) },
            {
              label: "ROAS TB",
              value: summary.avg_roas != null
                ? Number(summary.avg_roas).toFixed(2) + "×"
                : (summary.roas_stub ? "stub" : "—"),
            },
            { label: "Dữ liệu mới nhất", value: summary.latest_performance_date ? String(summary.latest_performance_date).slice(0, 10) : "—" },
          ].map(function (item) {
            return '<div class="agency-stat-card"><span class="agency-stat-label">' +
              esc(item.label) + '</span><strong style="font-size:1.1rem">' + esc(item.value) + "</strong></div>";
          }).join("");
        }

        if (banner && summary.over_target_rows > 0) {
          banner.hidden = false;
          banner.textContent = summary.over_target_rows + " dòng vượt target CPL — kiểm tra campaign và tối ưu creative/audience.";
        }

        if (!rows.length) {
          tbody.innerHTML = "<tr><td colspan=\"" + (groupBy === "campaign" ? 9 : 10) + "\">" +
            emptyState(
              "Chưa có dữ liệu performance",
              "Chạy Meta/Google insights sync sau khi map Hub campaign và cấu hình token.",
              '<a class="btn btn-secondary" href="/crm/agency/ingest">Xem job queue</a>'
            ) + "</td></tr>";
          loadHubCampaignMaps();
          return;
        }

        tbody.innerHTML = rows.map(function (r) {
          var roasCell = typeof fmtRoas(r) === "string" && fmtRoas(r).indexOf("<") === 0 ? fmtRoas(r) : esc(fmtRoas(r));
          var hubCell = r.hub_mapped
            ? '<a href="' + esc(r.hub_url || "/crm/hub") + '" target="_blank" rel="noopener" class="agency-perf-hub-link">Hub #' +
              esc(String(r.hub_campaign_id || "")) + "</a>"
            : '<span class="agency-badge agency-badge--unmap">Chưa map</span>';
          var mapBadge = r.hub_mapped ? "" : ' title="Map campaign trong Hub trước khi tin CPL closed-loop"';
          var rowClass = r.hub_mapped ? " agency-perf-row--clickable" : "";
          var hubUrl = r.hub_url || "/crm/hub";

          if (groupBy === "campaign") {
            return (
              '<tr class="' + rowClass.trim() + '" data-hub-url="' + esc(hubUrl) + '"' + mapBadge + ">" +
              "<td>" + channelBadge(r.channel) + "</td>" +
              "<td><strong>" + esc(r.external_campaign_name || r.external_campaign_id) + "</strong><br>" +
              '<span class="agency-muted" style="font-size:0.72rem">' + esc(r.external_campaign_id) + "</span></td>" +
              "<td>" + fmtVnd(r.spend) + "</td>" +
              "<td>" + esc(r.leads_crm) + "</td>" +
              "<td>" + fmtCpl(r.cpl) + "</td>" +
              "<td>" + roasCell + "</td>" +
              "<td>" + fmtCpl(r.target_cpl_vnd) + "</td>" +
              "<td>" + cplDeltaBadge(r) + "</td>" +
              "<td>" + hubCell + "</td></tr>"
            );
          }
          return (
            '<tr class="' + rowClass.trim() + '" data-hub-url="' + esc(hubUrl) + '"' + mapBadge + ">" +
            "<td>" + esc(String(r.performance_date || "").slice(0, 10)) + "</td>" +
            "<td>" + channelBadge(r.channel) + "</td>" +
            "<td><strong>" + esc(r.external_campaign_name || r.external_campaign_id) + "</strong></td>" +
            "<td>" + fmtVnd(r.spend) + "</td>" +
            "<td>" + esc(r.leads_crm) + "</td>" +
            "<td>" + fmtCpl(r.cpl) + "</td>" +
            "<td>" + roasCell + "</td>" +
            "<td>" + fmtCpl(r.target_cpl_vnd) + "</td>" +
            "<td>" + cplDeltaBadge(r) + "</td>" +
            "<td>" + hubCell + "</td></tr>"
          );
        }).join("");

        tbody.querySelectorAll(".agency-perf-row--clickable").forEach(function (tr) {
          tr.addEventListener("click", function (ev) {
            if (ev.target.closest("a")) return;
            var href = tr.getAttribute("data-hub-url");
            if (href) window.open(href, "_blank", "noopener");
          });
        });
        loadHubCampaignMaps();
      }).catch(function (e) {
        tbody.innerHTML = "<tr><td colspan=\"9\" class=\"agency-error\">" + esc(e.message) + "</td></tr>";
      });
    }

    function loadHubCampaignMaps() {
      var el = document.getElementById("agency-hub-map-list");
      if (!el) return;
      api("/api/v1/clients/" + clientId + "/hub-campaign-maps").then(function (data) {
        var maps = data.maps || [];
        if (!maps.length) {
          el.innerHTML = '<p class="agency-muted">Chưa có Hub map — cấu hình Meta Campaign ID + target CPL tại <a href="/crm/hub" target="_blank" rel="noopener">CRM Hub</a>.</p>';
          return;
        }
        el.innerHTML = '<table class="agency-table agency-table--compact"><thead><tr><th>Hub #</th><th>Kênh</th><th>Campaign</th><th>Target CPL</th><th></th></tr></thead><tbody>' +
          maps.map(function (m) {
            return "<tr><td>" + esc(String(m.hub_campaign_id || "")) + "</td>" +
              "<td>" + channelBadge(m.channel) + "</td>" +
              "<td><strong>" + esc(m.external_campaign_name || m.external_campaign_id) + "</strong><br>" +
              '<span class="agency-muted" style="font-size:0.72rem">' + esc(m.external_campaign_id) + "</span></td>" +
              "<td>" + fmtCpl(m.target_cpl_vnd) + "</td>" +
              '<td><a href="' + esc(m.hub_url || "/crm/hub") + '" target="_blank" rel="noopener">Hub</a></td></tr>';
          }).join("") + "</tbody></table>";
      }).catch(function () {
        el.innerHTML = '<p class="agency-muted">Không tải được hub map.</p>';
      });
    }

    if (perfTabBtn) {
      perfTabBtn.addEventListener("click", function () {
        if (!perfLoaded) {
          perfLoaded = true;
          loadClientPerformance();
        }
      });
    }
    var perfApply = document.getElementById("agency-perf-apply");
    var perfRefresh = document.getElementById("agency-perf-refresh");
    if (perfApply) perfApply.addEventListener("click", loadClientPerformance);
    if (perfRefresh) perfRefresh.addEventListener("click", loadClientPerformance);

    function loadClientLeads() {
      var tbody = document.getElementById("agency-client-leads-body");
      if (!tbody) return;
      tbody.innerHTML = skeletonRows(7, 4);
      api("/api/v1/clients/" + clientId + "/leads").then(function (data) {
        var leads = data.leads || [];
        if (leadsTabBtn) {
          leadsTabBtn.textContent = leads.length ? "Leads liên kết (" + leads.length + ")" : "Leads liên kết";
        }
        if (!leads.length) {
          tbody.innerHTML =
            "<tr><td colspan=\"7\">" +
            emptyState(
              "Chưa có lead liên kết",
              "Lead xuất hiện khi webhook/form gửi kèm X-PTT-Client-Id trùng client này.",
              '<a class="btn btn-secondary" href="/crm/leads">Mở CRM Leads</a>'
            ) +
            "</td></tr>";
          return;
        }
        tbody.innerHTML = leads.map(function (l) {
          return (
            "<tr><td>#" + esc(l.id) + "</td>" +
            "<td>" + esc(l.full_name || "—") + "</td>" +
            "<td>" + esc(l.phone || "—") + "</td>" +
            "<td>" + statusBadge(String(l.status || "new").replace(/_/g, "-")) + "</td>" +
            "<td>" + esc(l.source || l.channel || "—") + "</td>" +
            "<td>" + esc(fmtTime(l.created_at)) + "</td>" +
            '<td><a class="btn btn-secondary btn-sm" href="/crm/leads/' + esc(l.id) + '">Mở lead</a></td></tr>'
          );
        }).join("");
      }).catch(function (e) {
        tbody.innerHTML = "<tr><td colspan=\"7\" class=\"agency-error\">" + esc(e.message) + "</td></tr>";
      });
    }

    if (leadsTabBtn) {
      leadsTabBtn.addEventListener("click", function () {
        if (!leadsLoaded) {
          leadsLoaded = true;
          loadClientLeads();
        }
      });
    }

    function load() {
      api("/api/v1/clients/" + clientId).then(function (c) {
        document.getElementById("agency-client-title").textContent = c.code + " — " + c.name;
        document.getElementById("agency-client-status-badge").innerHTML = statusBadge(c.status);
        var meta = document.getElementById("agency-client-meta-grid");
        if (meta) {
          meta.innerHTML =
            '<dl class="agency-meta-grid">' +
            "<div><dt>AM phụ trách</dt><dd>" + esc(c.owner_am_id || "—") + "</dd></div>" +
            "<div><dt>Ngành</dt><dd>" + esc(c.industry_slug || "—") + "</dd></div>" +
            "<div><dt>Tạo lúc</dt><dd>" + esc(fmtTime(c.created_at)) + "</dd></div>" +
            "<div><dt>Cập nhật</dt><dd>" + esc(fmtTime(c.updated_at)) + "</dd></div></dl>";
        }
        var pct = (c.progress && c.progress.percent) || 0;
        document.getElementById("agency-progress-fill").style.width = pct + "%";
        document.getElementById("agency-progress-text").textContent = pct + "%";
        var tabCheck = document.querySelector('[data-tab-count="checklist"]');
        if (tabCheck) tabCheck.textContent = "Checklist " + pct + "%";
        activateBtn.disabled = c.status === "active" || pct < 100;

        return api("/api/v1/clients/" + clientId + "/checklist").then(function (cl) {
          checklist.innerHTML = (cl.items || []).map(function (it) {
            return (
              '<li><input type="checkbox" data-key="' + esc(it.item_key) + '" ' +
              (it.completed ? "checked" : "") + ' id="chk-' + esc(it.item_key) + '">' +
              '<label class="agency-checklist-label" for="chk-' + esc(it.item_key) + '">' + esc(it.label) + "</label></li>"
            );
          }).join("") || "<li class=\"agency-muted\">Chưa có checklist</li>";

          checklist.querySelectorAll("input[type=checkbox]").forEach(function (cb) {
            cb.addEventListener("change", function () {
              api("/api/v1/clients/" + clientId + "/checklist/" + cb.getAttribute("data-key"), {
                method: "PATCH",
                body: JSON.stringify({ completed: cb.checked }),
              }).then(load).catch(function (e) { toast(e.message, false); cb.checked = !cb.checked; });
            });
          });

          renderChannelAccounts(c.channel_accounts || [], clientId);
        });
      }).catch(function (e) { toast(e.message, false); });
    }

    activateBtn.addEventListener("click", function () {
      api("/api/v1/clients/" + clientId + "/activate", { method: "POST", body: "{}" })
        .then(function () { toast("Client đã kích hoạt"); load(); })
        .catch(function (e) { toast(e.message, false); });
    });

    var onboardingWfBtn = document.getElementById("agency-btn-onboarding-wf");
    if (onboardingWfBtn) {
      onboardingWfBtn.addEventListener("click", function () {
        api("/api/v1/clients/" + clientId + "/workflows/onboarding/start", { method: "POST", body: "{}" })
          .then(function (r) {
            toast(r.workflow_started ? "Onboarding WF started" : "Onboarding WF queued (Temporal stub/off)");
          })
          .catch(function (e) { toast(e.message, false); });
      });
    }

    var crSubmit = document.getElementById("agency-cr-submit");
    if (crSubmit) {
      crSubmit.addEventListener("click", function () {
        var payload = {
          title: (document.getElementById("agency-cr-title") || {}).value,
          version: Number((document.getElementById("agency-cr-version") || {}).value || 1),
          external_campaign_id: (document.getElementById("agency-cr-campaign-id") || {}).value,
          external_campaign_name: (document.getElementById("agency-cr-campaign-name") || {}).value,
          asset_url: (document.getElementById("agency-cr-asset-url") || {}).value,
          description: (document.getElementById("agency-cr-desc") || {}).value,
        };
        api("/api/v1/clients/" + clientId + "/creatives/submit", {
          method: "POST",
          body: JSON.stringify(payload),
        }).then(function (r) {
          var el = document.getElementById("agency-cr-result");
          if (el) {
            el.textContent = "OK — creative " + (r.creative && r.creative.id) + " · WF " + (r.workflow_id || "—");
          }
          toast("Creative đã gửi client duyệt");
        }).catch(function (e) { toast(e.message, false); });
      });
    }

    var lqaLoaded = false;
    function renderLaunchQaRuns(data) {
      var root = document.getElementById("agency-lqa-runs");
      if (!root) return;
      var runs = (data && data.runs) || [];
      if (!runs.length) {
        root.innerHTML = "<p class=\"agency-muted\">Chưa có Launch QA run.</p>";
        return;
      }
      root.innerHTML = runs.map(function (run) {
        var pct = (run.progress && run.progress.percent) || 0;
        var checklist = run.checklist || {};
        var items = Object.keys(checklist).map(function (key) {
          var it = checklist[key] || {};
          return (
            "<li><label><input type=\"checkbox\" data-run=\"" + esc(run.id) + "\" data-key=\"" + esc(key) + "\" " +
            (it.completed ? "checked" : "") + "> " + esc(it.label || key) + "</label></li>"
          );
        }).join("");
        return (
          "<div class=\"agency-panel-sub\" style=\"margin-bottom:0.75rem\">" +
          "<h3 style=\"margin:0 0 0.35rem;font-size:0.95rem\">" + esc(run.external_campaign_id) +
          " · " + esc(run.status) + " · " + pct + "%</h3>" +
          "<ul class=\"agency-checklist\">" + items + "</ul></div>"
        );
      }).join("");
      root.querySelectorAll("input[type=checkbox][data-run]").forEach(function (cb) {
        cb.addEventListener("change", function () {
          var runId = cb.getAttribute("data-run");
          var key = cb.getAttribute("data-key");
          api("/api/v1/clients/" + clientId + "/launch-qa/" + runId + "/checklist/" + key, {
            method: "PATCH",
            body: JSON.stringify({ completed: cb.checked }),
          }).then(function () { loadLaunchQa(); }).catch(function (e) {
            toast(e.message, false);
            cb.checked = !cb.checked;
          });
        });
      });
    }

    function loadLaunchQa() {
      return api("/api/v1/clients/" + clientId + "/launch-qa").then(renderLaunchQaRuns);
    }

    var lqaStart = document.getElementById("agency-lqa-start");
    if (lqaStart) {
      lqaStart.addEventListener("click", function () {
        var payload = {
          external_campaign_id: (document.getElementById("agency-lqa-campaign-id") || {}).value,
          campaign_name: (document.getElementById("agency-lqa-campaign-name") || {}).value,
        };
        api("/api/v1/clients/" + clientId + "/launch-qa/start", {
          method: "POST",
          body: JSON.stringify(payload),
        }).then(function () {
          toast("Launch QA started");
          loadLaunchQa();
        }).catch(function (e) { toast(e.message, false); });
      });
    }
    var lqaRefresh = document.getElementById("agency-lqa-refresh");
    if (lqaRefresh) lqaRefresh.addEventListener("click", function () { loadLaunchQa().catch(function (e) { toast(e.message, false); }); });
    var lqaTab = document.querySelector('.agency-tab[data-tab="launch-qa"]');
    if (lqaTab) {
      lqaTab.addEventListener("click", function () {
        if (!lqaLoaded) {
          lqaLoaded = true;
          loadLaunchQa().catch(function (e) { toast(e.message, false); });
        }
      });
    }

    var cwLoaded = false;
    function renderCampaignWrites(data) {
      var root = document.getElementById("agency-cw-queue");
      if (!root) return;
      var rows = (data && data.rows) || [];
      if (!rows.length) {
        root.innerHTML = "<p class=\"agency-muted\">Không có yêu cầu chờ duyệt.</p>";
        return;
      }
      root.innerHTML =
        "<div class=\"agency-table-wrap\"><table class=\"agency-table\"><thead><tr>" +
        "<th>Campaign</th><th>Thay đổi</th><th>Trạng thái</th><th>Gửi bởi</th><th></th>" +
        "</tr></thead><tbody>" +
        rows.map(function (row) {
          var budget = (row.new_value && row.new_value.daily_budget_vnd) || "—";
          var actions =
            row.status === "pending_approval"
              ? '<button type="button" class="btn btn-secondary agency-cw-approve" data-id="' + esc(row.id) + '">Duyệt</button> ' +
                '<button type="button" class="btn btn-secondary agency-cw-reject" data-id="' + esc(row.id) + '">Từ chối</button>'
              : "";
          return (
            "<tr><td>" + esc(row.external_campaign_id) + "<br><span class=\"agency-muted\">" + esc(row.external_campaign_name || "") + "</span></td>" +
            "<td>" + esc(row.change_type) + " → " + esc(String(budget)) + " VND</td>" +
            "<td>" + esc(row.status) + "</td>" +
            "<td>" + esc(row.submitted_by || "") + "</td>" +
            "<td>" + actions + "</td></tr>"
          );
        }).join("") +
        "</tbody></table></div>";
      root.querySelectorAll(".agency-cw-approve").forEach(function (btn) {
        btn.addEventListener("click", function () {
          var id = btn.getAttribute("data-id");
          api("/api/v1/clients/" + clientId + "/campaign-writes/" + id + "/approve", {
            method: "POST",
            body: "{}",
          }).then(function () {
            toast("Đã duyệt — Temporal sẽ gọi Meta API");
            loadCampaignWrites();
          }).catch(function (e) { toast(e.message, false); });
        });
      });
      root.querySelectorAll(".agency-cw-reject").forEach(function (btn) {
        btn.addEventListener("click", function () {
          var id = btn.getAttribute("data-id");
          api("/api/v1/clients/" + clientId + "/campaign-writes/" + id + "/reject", {
            method: "POST",
            body: "{}",
          }).then(function () {
            toast("Đã từ chối yêu cầu");
            loadCampaignWrites();
          }).catch(function (e) { toast(e.message, false); });
        });
      });
    }

    function loadCampaignWrites() {
      return api("/api/v1/clients/" + clientId + "/campaign-writes").then(renderCampaignWrites);
    }

    var cwSubmit = document.getElementById("agency-cw-submit");
    if (cwSubmit) {
      cwSubmit.addEventListener("click", function () {
        var payload = {
          external_campaign_id: (document.getElementById("agency-cw-campaign-id") || {}).value,
          external_campaign_name: (document.getElementById("agency-cw-campaign-name") || {}).value,
          daily_budget_vnd: Number((document.getElementById("agency-cw-budget") || {}).value || 0),
        };
        api("/api/v1/clients/" + clientId + "/campaign-writes", {
          method: "POST",
          body: JSON.stringify(payload),
        }).then(function (r) {
          var el = document.getElementById("agency-cw-result");
          if (el) {
            el.textContent = "OK — request " + (r.request && r.request.id) + " · WF " + (r.workflow_id || "—");
          }
          toast("Campaign write đã gửi chờ duyệt");
          loadCampaignWrites();
        }).catch(function (e) { toast(e.message, false); });
      });
    }
    var cwRefresh = document.getElementById("agency-cw-refresh");
    if (cwRefresh) cwRefresh.addEventListener("click", function () { loadCampaignWrites().catch(function (e) { toast(e.message, false); }); });
    var cwTab = document.querySelector('.agency-tab[data-tab="campaign-writes"]');
    if (cwTab) {
      cwTab.addEventListener("click", function () {
        if (!cwLoaded) {
          cwLoaded = true;
          loadCampaignWrites().catch(function (e) { toast(e.message, false); });
        }
      });
    }

    document.getElementById("agency-ch-add").addEventListener("click", function () {
      var payload = {
        channel: document.getElementById("agency-ch-channel").value,
        external_account_id: document.getElementById("agency-ch-ext").value,
        display_name: document.getElementById("agency-ch-name").value,
      };
      var tok = (document.getElementById("agency-ch-token") || {}).value;
      var exp = (document.getElementById("agency-ch-expires") || {}).value;
      var cred = (document.getElementById("agency-ch-cred-ref") || {}).value;
      var pixel = (document.getElementById("agency-ch-pixel") || {}).value;
      if (tok) payload.access_token = tok;
      if (exp) payload.token_expires_at = exp;
      if (cred) payload.credential_ref = cred;
      if (pixel) payload.pixel_id = String(pixel).trim();
      api("/api/v1/clients/" + clientId + "/channel-accounts", {
        method: "POST",
        body: JSON.stringify(payload),
      }).then(function () {
        toast("Đã thêm kênh");
        document.getElementById("agency-ch-ext").value = "";
        document.getElementById("agency-ch-name").value = "";
        if (document.getElementById("agency-ch-token")) document.getElementById("agency-ch-token").value = "";
        if (document.getElementById("agency-ch-expires")) document.getElementById("agency-ch-expires").value = "";
        if (document.getElementById("agency-ch-cred-ref")) document.getElementById("agency-ch-cred-ref").value = "";
        if (document.getElementById("agency-ch-pixel")) document.getElementById("agency-ch-pixel").value = "";
        load();
      }).catch(function (e) { toast(e.message, false); });
    });
    load();
  }

  if (page === "ingest") {
    var tbody = document.querySelector("#agency-jobs-table tbody");
    var statsEl = document.getElementById("agency-ingest-stats");
    var tabsEl = document.getElementById("agency-ingest-tabs");
    var autoRefresh = document.getElementById("agency-ingest-autorefresh");
    var refreshTimer = null;
    var currentStatus = "";
    var replayJobId = null;

    var params = new URLSearchParams(window.location.search);
    if (params.get("status")) currentStatus = params.get("status");

    function setActiveTab(st) {
      currentStatus = st || "";
      if (tabsEl) {
        tabsEl.querySelectorAll(".agency-tab").forEach(function (btn) {
          btn.classList.toggle("is-active", (btn.getAttribute("data-status") || "") === currentStatus);
        });
      }
    }

    if (tabsEl) {
      tabsEl.querySelectorAll(".agency-tab").forEach(function (btn) {
        btn.addEventListener("click", function () {
          setActiveTab(btn.getAttribute("data-status") || "");
          load();
        });
      });
      setActiveTab(currentStatus);
    }

    function showJobModal(jobId) {
      var body = document.getElementById("agency-job-modal-body");
      var replayBtn = document.getElementById("agency-job-modal-replay");
      body.innerHTML = '<p class="agency-loading-inline">Đang tải job…</p>';
      replayBtn.hidden = true;
      replayBtn.onclick = null;
      openModal("agency-job-modal");
      api("/api/v1/jobs/" + jobId).then(function (j) {
        body.innerHTML =
          '<dl class="agency-dl">' +
          "<div><dt>ID</dt><dd><code>" + esc(j.id) + "</code></dd></div>" +
          "<div><dt>Loại</dt><dd>" + esc(j.job_type) + "</dd></div>" +
          "<div><dt>Trạng thái</dt><dd>" + statusBadge(j.status) + "</dd></div>" +
          "<div><dt>Kênh</dt><dd>" + esc(j.channel || "—") + "</dd></div>" +
          "<div><dt>Client</dt><dd>" + esc(j.client_code || j.client_id || "—") + "</dd></div>" +
          "<div><dt>Correlation</dt><dd><code>" + esc(j.correlation_id || "—") + "</code></dd></div>" +
          "<div><dt>Attempts</dt><dd>" + esc(j.attempts) + " / " + esc(j.max_attempts) + "</dd></div>" +
          "<div><dt>Tạo lúc</dt><dd>" + esc(fmtTime(j.created_at)) + "</dd></div>" +
          (j.last_error ? "<div><dt>Lỗi</dt><dd>" + esc(j.last_error) + "</dd></div>" : "") +
          "<div><dt>Payload</dt><dd><pre>" + esc(JSON.stringify(j.payload || {}, null, 2)) + "</pre></dd></div>" +
          "</dl>";
        if (j.status === "dead") {
          replayBtn.hidden = false;
          replayBtn.onclick = function () { promptReplay(j.id, j.job_type); };
        }
      }).catch(function (e) {
        body.innerHTML = '<p class="agency-error">' + esc(e.message) + "</p>";
      });
    }

    function promptReplay(jobId, jobType) {
      replayJobId = jobId;
      document.getElementById("agency-replay-modal-hint").textContent = jobType ? "Job: " + jobType : "";
      openModal("agency-replay-modal");
    }

    document.getElementById("agency-replay-modal-confirm").addEventListener("click", function () {
      if (!replayJobId) return;
      var id = replayJobId;
      closeModal("agency-replay-modal");
      api("/api/v1/jobs/" + id + "/replay", { method: "POST", body: "{}" })
        .then(function () { toast("Job replay đã xếp hàng"); closeModal("agency-job-modal"); load(); })
        .catch(function (e) { toast(e.message, false); });
    });

    function loadEvents() {
      var evTbody = document.querySelector("#agency-events-table tbody");
      var evStats = document.getElementById("agency-events-stats");
      if (evTbody) evTbody.innerHTML = skeletonRows(5, 4);
      api("/api/v1/events?limit=30").then(function (data) {
        var st = data.stats || {};
        if (evStats) {
          evStats.innerHTML = [
            { k: "lead_created", label: "LeadCreated" },
            { k: "unpublished", label: "Chưa publish RMQ" },
            { k: "job_dead", label: "JobDead" },
            { k: "total", label: "Tổng events" },
          ].map(function (item) {
            var warn = item.k === "unpublished" && st[item.k] ? " agency-stat-card--warn" : "";
            return '<div class="agency-stat-card' + warn + '"><span class="agency-stat-label">' +
              esc(item.label) + '</span><strong>' + (st[item.k] || 0) + "</strong></div>";
          }).join("");
        }
        var events = data.events || [];
        if (!events.length) {
          evTbody.innerHTML = "<tr><td colspan=\"5\">" + emptyState("Chưa có event", "Events xuất hiện sau ingest thành công.") + "</td></tr>";
          return;
        }
        evTbody.innerHTML = events.map(function (ev) {
          var agg = (ev.aggregate_type || "") + " / " + (ev.aggregate_id || "—");
          var pub = ev.published_at
            ? '<span class="agency-badge agency-badge--done">Đã publish</span>'
            : '<span class="agency-badge agency-badge--pending">Outbox</span>';
          return (
            "<tr><td>" + esc(fmtTime(ev.created_at)) + "</td>" +
            "<td><code>" + esc(ev.event_type) + "</code></td>" +
            "<td>" + esc(agg) + "</td>" +
            "<td><code>" + esc(ev.correlation_id || "—") + "</code></td>" +
            "<td>" + pub + "</td></tr>"
          );
        }).join("");
      }).catch(function (e) {
        if (evTbody) evTbody.innerHTML = "<tr><td colspan=\"5\" class=\"agency-error\">" + esc(e.message) + "</td></tr>";
      });
    }

    function loadSpillover() {
      var spillBanner = document.getElementById("agency-form-spillover-banner");
      var spillTbody = document.querySelector("#agency-spillover-table tbody");
      if (spillTbody) spillTbody.innerHTML = skeletonRows(3, 4);
      api("/api/v1/form-ingest/spillover?limit=50").then(function (data) {
        var st = data.stats || {};
        var open = st.open || 0;
        if (spillBanner) {
          if (open > 0) {
            spillBanner.hidden = false;
            spillBanner.innerHTML =
              "Có " + open + " form ingest spillover cần replay — xem bảng bên dưới.";
          } else {
            spillBanner.hidden = true;
            spillBanner.innerHTML = "";
          }
        }
        var items = data.items || [];
        if (!spillTbody) return;
        if (!items.length) {
          spillTbody.innerHTML = "<tr><td colspan=\"5\">" +
            emptyState("Không có spillover", "Form ingest thất bại sẽ hiện ở đây khi queue down.") +
            "</td></tr>";
          return;
        }
        spillTbody.innerHTML = items.map(function (it) {
          var replayBtn = it.resolved_at
            ? '<span class="agency-muted">Đã xử lý</span>'
            : '<button type="button" class="btn btn-secondary btn-sm agency-spillover-replay" data-id="' +
              esc(String(it.id)) + '">Replay</button>';
          return (
            "<tr><td>" + esc(fmtTime(it.created_at)) + "</td>" +
            "<td>" + esc(it.full_name || "—") + "</td>" +
            "<td>" + esc(it.phone || "—") + "</td>" +
            "<td>" + esc((it.error || "").slice(0, 120)) + "</td>" +
            "<td>" + replayBtn + "</td></tr>"
          );
        }).join("");
        spillTbody.querySelectorAll(".agency-spillover-replay").forEach(function (btn) {
          btn.addEventListener("click", function () {
            var sid = btn.getAttribute("data-id");
            btn.disabled = true;
            api("/api/v1/form-ingest/spillover/" + sid + "/replay", { method: "POST", body: "{}" })
              .then(function () { toast("Form spillover replay thành công"); load(); })
              .catch(function (e) { toast(e.message, false); btn.disabled = false; });
          });
        });
      }).catch(function (e) {
        if (spillTbody) {
          spillTbody.innerHTML = "<tr><td colspan=\"5\" class=\"agency-error\">" + esc(e.message) + "</td></tr>";
        }
      });
    }

    function load() {
      loadEvents();
      loadSpillover();
      if (tbody) tbody.innerHTML = skeletonRows(7, 6);
      var url = "/api/v1/jobs?limit=50" + (currentStatus ? "&status=" + encodeURIComponent(currentStatus) : "");
      api(url).then(function (data) {
        var s = data.stats || {};
        if (statsEl) {
          statsEl.innerHTML = ["pending", "running", "dead", "failed", "done"].map(function (k) {
            return '<div class="agency-stat-card' + (k === "dead" && s[k] ? " agency-stat-card--warn" : "") +
              '"><span class="agency-stat-label">' + esc(STATUS_LABELS[k] || k) +
              '</span><strong>' + (s[k] || 0) + "</strong></div>";
          }).join("");
        }
        var jobs = data.jobs || [];
        if (!jobs.length) {
          tbody.innerHTML = "<tr><td colspan=\"7\">" + emptyState("Không có job", currentStatus ? "Không có job ở trạng thái này." : "Queue đang trống.") + "</td></tr>";
          return;
        }
        tbody.innerHTML = jobs.map(function (j) {
          var replay = j.status === "dead"
            ? '<button type="button" class="btn btn-secondary btn-sm agency-replay" data-id="' + esc(j.id) + '">Replay</button> ' : "";
          return (
            "<tr><td>" + esc(fmtTime(j.created_at)) + "</td>" +
            "<td>" + esc(j.job_type) + "</td>" +
            "<td>" + esc(j.channel || "—") + "</td>" +
            "<td>" + esc(j.client_code || "—") + "</td>" +
            "<td>" + statusBadge(j.status) + "</td>" +
            "<td>" + esc(j.attempts) + "</td>" +
            "<td class=\"agency-notif-actions\">" +
            '<button type="button" class="btn btn-secondary btn-sm agency-job-detail" data-id="' + esc(j.id) + '">Chi tiết</button> ' +
            replay + "</td></tr>"
          );
        }).join("");
        tbody.querySelectorAll(".agency-replay").forEach(function (btn) {
          btn.addEventListener("click", function () {
            promptReplay(btn.getAttribute("data-id"), "");
          });
        });
        tbody.querySelectorAll(".agency-job-detail").forEach(function (btn) {
          btn.addEventListener("click", function () { showJobModal(btn.getAttribute("data-id")); });
        });
      }).catch(function (e) {
        if (tbody) tbody.innerHTML = "<tr><td colspan=\"7\" class=\"agency-error\">" + esc(e.message) + "</td></tr>";
      });
    }

    function scheduleRefresh() {
      if (refreshTimer) clearInterval(refreshTimer);
      refreshTimer = null;
      if (autoRefresh && autoRefresh.checked) refreshTimer = setInterval(load, 30000);
    }

    document.getElementById("agency-ingest-refresh").addEventListener("click", load);
    if (autoRefresh) {
      autoRefresh.addEventListener("change", scheduleRefresh);
      scheduleRefresh();
    }
    load();
  }

  if (page === "notifications") {
    var list = document.getElementById("agency-notif-list");
    var currentCat = "";

    document.getElementById("agency-notif-tabs").querySelectorAll(".agency-tab").forEach(function (btn) {
      btn.addEventListener("click", function () {
        currentCat = btn.getAttribute("data-category") || "";
        document.getElementById("agency-notif-tabs").querySelectorAll(".agency-tab").forEach(function (b) {
          b.classList.toggle("is-active", b === btn);
        });
        load();
      });
    });

    function load() {
      list.innerHTML = '<li class="agency-loading-inline">Đang tải…</li>';
      var url = "/api/v1/notifications";
      if (currentCat) url += "?category=" + encodeURIComponent(currentCat);
      api(url).then(function (data) {
        var rows = data.notifications || [];
        if (!rows.length) {
          list.innerHTML = emptyState("Không có thông báo", "Bạn đã xem hết hoặc chưa có cảnh báo mới.");
          return;
        }
        list.innerHTML = rows.map(function (n) {
          var unread = n.read_at ? "" : " agency-notif-item--unread";
          var cat = CATEGORY_LABELS[n.category] || n.category || "Hệ thống";
          var actions = "";
          if (n.link_url) actions += '<a class="btn btn-secondary btn-sm" href="' + esc(n.link_url) + '">Mở</a> ';
          if (!n.read_at) {
            actions += '<button type="button" class="btn btn-secondary btn-sm agency-notif-read" data-id="' + esc(n.id) + '">Đánh dấu đã đọc</button>';
          }
          return (
            '<li class="agency-notif-item' + unread + '">' +
            '<div class="agency-notif-head">' +
            '<span class="agency-notif-title">' + esc(n.title) + '</span>' +
            '<span class="agency-notif-meta">' + esc(cat) + " · " + esc(relTime(n.created_at)) + "</span></div>" +
            (n.body ? '<p class="agency-notif-body">' + esc(n.body) + "</p>" : "") +
            '<div class="agency-notif-actions">' + actions + "</div></li>"
          );
        }).join("");
        list.querySelectorAll(".agency-notif-read").forEach(function (btn) {
          btn.addEventListener("click", function () {
            api("/api/v1/notifications/" + btn.getAttribute("data-id"), { method: "PATCH", body: "{}" })
              .then(function () { toast("Đã đánh dấu đọc"); load(); })
              .catch(function (e) { toast(e.message, false); });
          });
        });
      }).catch(function (e) {
        list.innerHTML = '<li class="agency-error">' + esc(e.message) + "</li>";
      });
    }

    document.getElementById("agency-notif-read-all").addEventListener("click", function () {
      api("/api/v1/notifications/mark-all-read", { method: "POST", body: "{}" })
        .then(function () { toast("Đã đánh dấu tất cả đã đọc"); load(); })
        .catch(function (e) { toast(e.message, false); });
    });
    load();
  }

  if (page === "kpi") {
    var kpiBody = document.querySelector("#agency-kpi-table tbody");
    if (kpiBody) kpiBody.innerHTML = skeletonRows(4, 4);
    api("/api/v1/kpi-definitions").then(function (data) {
      var rows = data.definitions || [];
      if (!rows.length) {
        kpiBody.innerHTML = "<tr><td colspan=\"4\">" + emptyState("Chưa có định nghĩa KPI", "Chạy DDL seed hoặc thêm qua PostgreSQL.") + "</td></tr>";
        return;
      }
      kpiBody.innerHTML = rows.map(function (d) {
        return "<tr><td><code>" + esc(d.code) + "</code></td><td>" + esc(d.name) + "</td><td><code>" +
          esc(d.formula) + "</code></td><td>" + esc(d.granularity) + "</td></tr>";
      }).join("");
    }).catch(function (e) {
      if (kpiBody) kpiBody.innerHTML = "<tr><td colspan=\"4\" class=\"agency-error\">" + esc(e.message) + "</td></tr>";
    });
  }

  function debounce(fn, ms) {
    var t;
    return function () {
      clearTimeout(t);
      var args = arguments;
      var self = this;
      t = setTimeout(function () { fn.apply(self, args); }, ms);
    };
  }
})();
