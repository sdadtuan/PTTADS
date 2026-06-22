(function () {
  window.addEventListener("pageshow", (ev) => {
    if (ev.persisted) window.location.reload();
  });

  const metaEl = document.getElementById("crm-payroll-meta");
  /** @type {boolean} */
  let STAFF_PORTAL = false;
  /** @type {boolean} */
  let ATTENDANCE_READONLY = false;
  try {
    const raw = metaEl ? JSON.parse(metaEl.textContent || "{}") : {};
    STAFF_PORTAL = !!raw.staff_portal;
    ATTENDANCE_READONLY = !!raw.attendance_readonly;
  } catch {
    STAFF_PORTAL = false;
    ATTENDANCE_READONLY = false;
  }

  const yearEl = document.getElementById("crm-pr-year");
  const monthEl = document.getElementById("crm-pr-month");
  const hintEl = document.getElementById("crm-pr-period-hint");
  const attForm = document.getElementById("crm-att-form");
  const attErr = document.getElementById("crm-att-err");
  const attImportFile = document.getElementById("crm-att-import-file");
  const attImportBtn = document.getElementById("crm-att-import-btn");
  const attImportOk = document.getElementById("crm-att-import-ok");
  const attTbody = document.getElementById("crm-att-tbody");
  const attEmpty = document.getElementById("crm-att-empty");
  const attFilter = document.getElementById("crm-att-filter-staff");
  const attSearchEl = document.getElementById("crm-att-search");
  const attCountEl = document.getElementById("crm-att-count");
  const attMiniStatsEl = document.getElementById("crm-att-mini-stats");
  const attDate = document.getElementById("crm-att-date");
  const prSearchEl = document.getElementById("crm-pr-search");
  const prCountEl = document.getElementById("crm-pr-count");
  const prMiniStatsEl = document.getElementById("crm-pr-mini-stats");
  const btnPrevMonth = document.getElementById("crm-pr-prev-month");
  const btnNextMonth = document.getElementById("crm-pr-next-month");
  const prErr = document.getElementById("crm-pr-err");
  const prMeta = document.getElementById("crm-pr-payroll-meta");
  const prTable = document.getElementById("crm-pr-table");
  const prTbody = document.getElementById("crm-pr-tbody");
  const prEmpty = document.getElementById("crm-pr-empty");
  const btnRefresh = document.getElementById("crm-pr-refresh");
  const btnCompute = document.getElementById("crm-pr-compute");
  const btnLock = document.getElementById("crm-pr-lock");
  const btnUnlock = document.getElementById("crm-pr-unlock");
  const policyForm = document.getElementById("crm-pr-policy-form");
  const policyErr = document.getElementById("crm-pr-policy-err");
  const weekdayTbody = document.getElementById("crm-pr-weekday-tbody");
  const btnSavePolicy = document.getElementById("crm-pr-save-policy");
  const btnSavePositions = document.getElementById("crm-pr-save-positions");
  const posTbody = document.getElementById("crm-pr-pos-tbody");
  const dashWorkdays = document.getElementById("crm-dash-workdays");
  const dashHours = document.getElementById("crm-dash-hours");
  const dashLate = document.getElementById("crm-dash-late");
  const dashToday = document.getElementById("crm-dash-today");
  const exportPeriodEl = document.getElementById("crm-pr-export-period");
  const exportQuarterWrap = document.getElementById("crm-pr-export-quarter-wrap");
  const exportQuarterEl = document.getElementById("crm-pr-export-quarter");
  const exportFromWrap = document.getElementById("crm-pr-export-from-wrap");
  const exportToWrap = document.getElementById("crm-pr-export-to-wrap");
  const exportFromEl = document.getElementById("crm-pr-export-from");
  const exportToEl = document.getElementById("crm-pr-export-to");
  const exportStaffEl = document.getElementById("crm-pr-export-staff");
  const exportStaffSearchEl = document.getElementById("crm-pr-export-staff-search");
  const exportStaffHintEl = document.getElementById("crm-pr-export-staff-hint");
  const exportHintEl = document.getElementById("crm-pr-export-hint");
  const btnExportXlsx = document.getElementById("crm-pr-export-xlsx");
  const btnExportCsv = document.getElementById("crm-pr-export-csv");

  /** @type {Array<Record<string, unknown>>} */
  let staffList = [];
  /** @type {Array<Record<string, unknown>>} */
  let attendanceRows = [];
  /** @type {Record<string, unknown> | null} */
  let payrollHeader = null;
  /** @type {Array<Record<string, unknown>>} */
  let payrollLines = [];
  /** @type {Array<Record<string, unknown>>} */
  let positionRates = [];

  const moneyFmt = new Intl.NumberFormat("vi-VN");

  function pad2(n) {
    return String(n).padStart(2, "0");
  }

  function monthBounds(y, m) {
    const last = new Date(y, m, 0).getDate();
    return [`${y}-${pad2(m)}-01`, `${y}-${pad2(m)}-${pad2(last)}`];
  }

  function getPeriod() {
    let y = Number(yearEl?.value || 0);
    let m = Number(monthEl?.value || 0);
    if (!Number.isFinite(y) || y < 2000 || y > 2100) {
      const d = new Date();
      y = d.getFullYear();
    }
    if (!Number.isFinite(m) || m < 1 || m > 12) {
      m = new Date().getMonth() + 1;
    }
    if (yearEl) yearEl.value = String(y);
    if (monthEl) monthEl.value = String(m);
    const [from, to] = monthBounds(y, m);
    return { y, m, from, to };
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
      throw new Error(data.error || "Chưa đăng nhập");
    }
    if (!res.ok) throw new Error(data.error || res.statusText || "Lỗi");
    return data;
  }

  function esc(s) {
    const d = document.createElement("div");
    d.textContent = s ?? "";
    return d.innerHTML;
  }

  function escAttr(s) {
    return String(s ?? "")
      .replace(/&/g, "&amp;")
      .replace(/"/g, "&quot;")
      .replace(/</g, "&lt;");
  }

  function fmtHours(n) {
    const v = Number(n);
    if (!Number.isFinite(v)) return "—";
    return v.toFixed(1).replace(/\.0$/, "");
  }

  function applyWeekdayShiftsToForm(shifts) {
    if (!weekdayTbody || !Array.isArray(shifts)) return;
    const byWd = {};
    shifts.forEach((s) => {
      byWd[String(s.weekday)] = s;
    });
    weekdayTbody.querySelectorAll("tr[data-weekday]").forEach((tr) => {
      const wd = tr.getAttribute("data-weekday") || "0";
      const s = byWd[wd] || {};
      const workEl = tr.querySelector(".crm-wd-work");
      const inEl = tr.querySelector(".crm-wd-in");
      const outEl = tr.querySelector(".crm-wd-out");
      const breakEl = tr.querySelector(".crm-wd-break");
      const hoursEl = tr.querySelector(".crm-wd-hours");
      if (workEl instanceof HTMLInputElement) workEl.checked = !!s.work;
      if (inEl instanceof HTMLInputElement) inEl.value = String(s.shift_start || "08:30");
      if (outEl instanceof HTMLInputElement) outEl.value = String(s.shift_end || "17:30");
      if (breakEl instanceof HTMLInputElement) breakEl.value = String(s.break_minutes ?? 60);
      if (hoursEl instanceof HTMLInputElement) hoursEl.value = String(s.standard_hours ?? 8);
    });
  }

  function weekdayShiftsFromForm() {
    const rows = [];
    weekdayTbody?.querySelectorAll("tr[data-weekday]").forEach((tr) => {
      const wd = Number(tr.getAttribute("data-weekday") || 0);
      const workEl = tr.querySelector(".crm-wd-work");
      const inEl = tr.querySelector(".crm-wd-in");
      const outEl = tr.querySelector(".crm-wd-out");
      const breakEl = tr.querySelector(".crm-wd-break");
      const hoursEl = tr.querySelector(".crm-wd-hours");
      rows.push({
        weekday: wd,
        work: workEl instanceof HTMLInputElement ? workEl.checked : false,
        shift_start: (inEl?.value || "08:30").toString().trim(),
        shift_end: (outEl?.value || "17:30").toString().trim(),
        break_minutes: Number(breakEl?.value || 0),
        standard_hours: Number(hoursEl?.value || 8),
      });
    });
    return rows;
  }

  function applyPolicyToForm(policy) {
    if (!policyForm || !policy) return;
    if (Array.isArray(policy.weekday_shifts) && policy.weekday_shifts.length) {
      applyWeekdayShiftsToForm(policy.weekday_shifts);
    } else {
      const wdSet = new Set(String(policy.work_weekdays || "0,1,2,3,4").split(",").map((s) => s.trim()));
      applyWeekdayShiftsToForm(
        [0, 1, 2, 3, 4, 5, 6].map((wd) => ({
          weekday: wd,
          work: wdSet.has(String(wd)),
          shift_start: policy.shift_start || "08:30",
          shift_end: policy.shift_end || "17:30",
          break_minutes: policy.break_minutes_default ?? 60,
          standard_hours: policy.standard_hours_per_day ?? 8,
        })),
      );
    }
    const setVal = (id, val) => {
      const el = document.getElementById(id);
      if (el instanceof HTMLInputElement || el instanceof HTMLSelectElement) el.value = String(val ?? "");
    };
    setVal("crm-pol-grace", policy.late_grace_minutes ?? 5);
    setVal("crm-pol-pen-min", policy.late_penalty_vnd_per_min ?? 5000);
    setVal("crm-pol-pen-max", policy.late_penalty_max_vnd ?? 200000);
    setVal("crm-pol-bonus-mode", policy.bonus_mode || "attendance");
    setVal("crm-pol-bonus-pct", policy.bonus_pct ?? 5);
    setVal("crm-pol-bonus-days", policy.bonus_min_days ?? 20);
  }

  function policyFromForm() {
    const fd = policyForm ? new FormData(policyForm) : new FormData();
    const shifts = weekdayShiftsFromForm();
    const workDays = shifts.filter((s) => s.work).map((s) => String(s.weekday));
    return {
      work_weekdays: workDays.length ? workDays.join(",") : "0,1,2,3,4",
      weekday_shifts: shifts,
      late_grace_minutes: Number(fd.get("late_grace_minutes") || 0),
      late_penalty_vnd_per_min: Number(fd.get("late_penalty_vnd_per_min") || 0),
      late_penalty_max_vnd: Number(fd.get("late_penalty_max_vnd") || 0),
      bonus_mode: (fd.get("bonus_mode") || "attendance").toString(),
      bonus_pct: Number(fd.get("bonus_pct") || 0),
      bonus_min_days: Number(fd.get("bonus_min_days") || 0),
    };
  }

  function renderPositionRates() {
    if (!posTbody) return;
    posTbody.innerHTML = positionRates
      .map((p) => {
        const pid = p.position_id;
        const rank = Number(p.rank_level || 1);
        const allow = Number(p.allowance_vnd || 0);
        const bp = Number(p.bonus_pct || 0);
        return `<tr data-pos-id="${esc(String(pid))}">
          <td><input type="number" class="crm-pr-pos-rank" min="1" max="99" step="1" value="${rank}" aria-label="Cấp bậc" /></td>
          <td>${esc((p.position_code || "").toString())}</td>
          <td>${esc((p.position_name || "").toString())}</td>
          <td><input type="number" class="crm-pr-pos-allow" min="0" step="1000" value="${allow}" aria-label="Phụ cấp" /></td>
          <td><input type="number" class="crm-pr-pos-bonus" min="0" max="100" step="0.5" value="${bp}" aria-label="Thưởng phần trăm" /></td>
        </tr>`;
      })
      .join("");
  }

  function positionRatesFromTable() {
    const rows = [];
    posTbody?.querySelectorAll("tr[data-pos-id]").forEach((tr) => {
      const pid = tr.getAttribute("data-pos-id");
      if (!pid) return;
      const rankEl = tr.querySelector(".crm-pr-pos-rank");
      const allowEl = tr.querySelector(".crm-pr-pos-allow");
      const bonusEl = tr.querySelector(".crm-pr-pos-bonus");
      rows.push({
        position_id: Number(pid),
        rank_level: Number(rankEl?.value || 1),
        allowance_vnd: Number(allowEl?.value || 0),
        bonus_pct: Number(bonusEl?.value || 0),
      });
    });
    return rows;
  }

  function renderDashboard(dash) {
    if (!dash) return;
    if (dashWorkdays) dashWorkdays.textContent = String(dash.workdays_standard ?? "—");
    if (dashHours) dashHours.textContent = fmtHours(dash.total_hours_month);
    if (dashLate) dashLate.textContent = String(dash.late_incidents_month ?? 0);
    if (dashToday) dashToday.textContent = String(dash.checked_in_today ?? 0);
    if (dash.policy) applyPolicyToForm(dash.policy);
    if (Array.isArray(dash.position_rates)) {
      positionRates = dash.position_rates;
      renderPositionRates();
    }
  }

  async function loadDashboard() {
    if (STAFF_PORTAL) return;
    const { y, m } = getPeriod();
    const data = await reqJson(`/api/crm/payroll/dashboard?year=${y}&month=${m}`);
    renderDashboard(data);
  }

  async function savePolicy() {
    if (policyErr) policyErr.hidden = true;
    await reqJson("/api/crm/payroll/policy", {
      method: "PUT",
      body: JSON.stringify(policyFromForm()),
    });
    await loadDashboard();
    if (hintEl) {
      const prev = hintEl.textContent;
      hintEl.textContent = "Đã lưu chính sách lương.";
      setTimeout(() => {
        hintEl.textContent = prev;
      }, 2000);
    }
  }

  async function savePositionRates() {
    if (policyErr) policyErr.hidden = true;
    await reqJson("/api/crm/payroll/position-rates", {
      method: "PUT",
      body: JSON.stringify({ positions: positionRatesFromTable() }),
    });
    await loadDashboard();
  }

  function fmtMoney(n) {
    const v = Number(n);
    if (!Number.isFinite(v)) return "—";
    return moneyFmt.format(Math.round(v));
  }

  function fmtDate(s) {
    const t = (s || "").toString().trim();
    const m = t.match(/^(\d{4})-(\d{2})-(\d{2})/);
    if (m) return `${m[3]}/${m[2]}/${m[1]}`;
    return esc(t);
  }

  function attRowHaystack(r) {
    return `${r.staff_name || ""} ${r.staff_code || ""} ${r.work_date || ""} ${r.note || ""} ${r.check_in || ""} ${r.check_out || ""}`
      .toLowerCase();
  }

  function filterAttendanceRows() {
    const fid = STAFF_PORTAL ? "" : (attFilter?.value || "").trim();
    const q = (attSearchEl?.value || "").trim().toLowerCase();
    return attendanceRows.filter((r) => {
      if (fid && String(r.staff_id) !== fid) return false;
      if (q && !attRowHaystack(r).includes(q)) return false;
      return true;
    });
  }

  function updateAttendanceSummary(rows) {
    const total = attendanceRows.length;
    const shown = rows.length;
    if (attCountEl) {
      attCountEl.textContent =
        shown === total ? `${total} bản ghi` : `${shown} / ${total} bản ghi`;
    }
    if (attMiniStatsEl) {
      let hours = 0;
      let late = 0;
      rows.forEach((r) => {
        hours += Number(r.worked_hours || 0);
        if (Number(r.late_minutes || 0) > 0) late += 1;
      });
      attMiniStatsEl.innerHTML = [
        `<span class="crm-stat-pill">${fmtHours(hours)} giờ</span>`,
        late > 0 ? `<span class="crm-stat-pill crm-stat-pill--warn">${late} lượt trễ</span>` : "",
      ]
        .filter(Boolean)
        .join("");
    }
  }

  function prLineHaystack(line) {
    return `${line.staff_name || ""} ${line.staff_code || ""} ${line.note || ""}`.toLowerCase();
  }

  function filterPayrollLines() {
    const q = (prSearchEl?.value || "").trim().toLowerCase();
    if (!q) return payrollLines;
    return payrollLines.filter((line) => prLineHaystack(line).includes(q));
  }

  function updatePayrollSummary(rows) {
    const total = payrollLines.length;
    const shown = rows.length;
    if (prCountEl) {
      prCountEl.textContent = shown === total ? `${total} nhân viên` : `${shown} / ${total} nhân viên`;
    }
    if (prMiniStatsEl) {
      let net = 0;
      rows.forEach((line) => {
        net += Number(line.net_salary_vnd || 0);
      });
      prMiniStatsEl.innerHTML = net > 0 ? `<span class="crm-stat-pill crm-stat-pill--accent">Tổng thực lĩnh: ${fmtMoney(net)}</span>` : "";
    }
  }

  async function reloadPeriodData() {
    if (btnRefresh) {
      btnRefresh.classList.add("is-loading");
      btnRefresh.disabled = true;
    }
    try {
      await loadStaff();
      await loadAttendance();
      if (!STAFF_PORTAL) {
        await loadDashboard();
        await loadPayroll();
      }
    } finally {
      if (btnRefresh) {
        btnRefresh.classList.remove("is-loading");
        btnRefresh.disabled = false;
      }
    }
  }

  function shiftPeriod(deltaMonths) {
    const y = Number(yearEl?.value || new Date().getFullYear());
    const m = Number(monthEl?.value || 1);
    let nm = m + deltaMonths;
    let ny = y;
    while (nm < 1) {
      nm += 12;
      ny -= 1;
    }
    while (nm > 12) {
      nm -= 12;
      ny += 1;
    }
    if (yearEl) yearEl.value = String(ny);
    if (monthEl) monthEl.value = String(nm);
    setAttDateFromPeriod();
    syncExportPeriodUi();
    reloadPeriodData().catch((e) => {
      attErr.textContent = e instanceof Error ? e.message : "Lỗi tải dữ liệu";
      attErr.hidden = false;
    });
  }

  function initPayrollNavSpy() {
    const nav = document.querySelector(".crm-payroll-nav");
    if (!nav || STAFF_PORTAL) return;
    const links = [...nav.querySelectorAll(".crm-payroll-nav-link")];
    const sections = links
      .map((l) => {
        const id = l.getAttribute("href")?.slice(1);
        return id ? document.getElementById(id) : null;
      })
      .filter(Boolean);
    if (!sections.length) return;

    const setActive = (id) => {
      links.forEach((l) => {
        l.classList.toggle("is-active", l.getAttribute("href") === `#${id}`);
      });
    };

    const obs = new IntersectionObserver(
      (entries) => {
        const visible = entries
          .filter((e) => e.isIntersecting)
          .sort((a, b) => b.intersectionRatio - a.intersectionRatio);
        if (visible.length) setActive(visible[0].target.id);
      },
      { rootMargin: "-12% 0px -55% 0px", threshold: [0.05, 0.15, 0.35] },
    );
    sections.forEach((s) => obs.observe(s));
    setActive(sections[0].id);

    links.forEach((link) => {
      link.addEventListener("click", () => {
        const id = link.getAttribute("href")?.slice(1);
        if (id) setActive(id);
      });
    });
  }

  function fillStaffSelects() {
    const opts =
      '<option value="">— Chọn nhân viên —</option>' +
      staffList
        .map((s) => {
          const id = s.id;
          const name = esc((s.name || "").toString());
          const code = (s.internal_code || "").toString().trim();
          const label = code ? `${name} (${esc(code)})` : name;
          return `<option value="${esc(String(id))}">${label}</option>`;
        })
        .join("");
    const attStaff = document.getElementById("crm-att-staff");
    if (attStaff) {
      const cur = attStaff.value;
      attStaff.innerHTML = opts;
      if (cur && staffList.some((s) => String(s.id) === cur)) attStaff.value = cur;
    }
    if (attFilter) {
      const curF = attFilter.value;
      attFilter.innerHTML =
        '<option value="">Tất cả nhân viên</option>' +
        staffList
          .map((s) => {
            const id = s.id;
            const name = esc((s.name || "").toString());
            const code = (s.internal_code || "").toString().trim();
            const label = code ? `${name} (${esc(code)})` : name;
            return `<option value="${esc(String(id))}">${label}</option>`;
          })
          .join("");
      if (curF && staffList.some((s) => String(s.id) === curF)) attFilter.value = curF;
    }
    if (exportStaffEl) {
      renderExportStaffSelect();
    }
  }

  function normStaffSearch(text) {
    return (text || "")
      .normalize("NFD")
      .replace(/[\u0300-\u036f]/g, "")
      .toLowerCase()
      .replace(/[^\w\s]/g, " ")
      .replace(/\s+/g, " ")
      .trim();
  }

  function staffSearchHaystack(s) {
    const name = (s.name || "").toString();
    const code = (s.internal_code || "").toString();
    const pin = (s.attendance_pin || "").toString();
    return normStaffSearch(`${name} ${code} ${pin}`);
  }

  function exportStaffMatches(query) {
    const q = normStaffSearch(query);
    if (!q) return staffList;
    const direct = staffList.filter((s) => staffSearchHaystack(s).includes(q));
    if (direct.length) return direct;
    const parts = q.split(/\s+/).filter((t) => t.length >= 2);
    for (let i = parts.length - 1; i >= 0; i -= 1) {
      const hits = staffList.filter((s) => staffSearchHaystack(s).includes(parts[i]));
      if (hits.length) return hits;
    }
    return [];
  }

  function renderExportStaffSelect() {
    if (!exportStaffEl) return;
    const cur = exportStaffEl.value;
    const q = (exportStaffSearchEl?.value || "").trim();
    const matches = exportStaffMatches(q);
    exportStaffEl.innerHTML =
      '<option value="">Tất cả nhân viên</option>' +
      matches
        .map((s) => {
          const id = s.id;
          const name = esc((s.name || "").toString());
          const code = (s.internal_code || "").toString().trim();
          const label = code ? `${name} (${esc(code)})` : name;
          return `<option value="${esc(String(id))}">${label}</option>`;
        })
        .join("");
    if (cur && matches.some((s) => String(s.id) === cur)) {
      exportStaffEl.value = cur;
    } else if (q && matches.length === 1) {
      exportStaffEl.value = String(matches[0].id);
    } else if (cur && !matches.some((s) => String(s.id) === cur)) {
      exportStaffEl.value = "";
    }
    if (exportStaffHintEl) {
      if (q && matches.length === 0) {
        exportStaffHintEl.textContent = "Không có nhân viên khớp.";
        exportStaffHintEl.hidden = false;
      } else if (q) {
        exportStaffHintEl.textContent = `${matches.length} nhân viên khớp — chọn một hoặc để «Tất cả» để xuất mọi người khớp.`;
        exportStaffHintEl.hidden = false;
      } else {
        exportStaffHintEl.hidden = true;
      }
    }
  }

  function resolveExportStaffFilter() {
    const sid = (exportStaffEl?.value || "").trim();
    if (sid) return { staff_id: sid, q: "" };
    const q = (exportStaffSearchEl?.value || "").trim();
    if (q) return { staff_id: "", q };
    return { staff_id: "", q: "" };
  }

  function validateExportStaffFilter() {
    const { staff_id, q } = resolveExportStaffFilter();
    if (staff_id) return null;
    if (!q) return null;
    const matches = exportStaffMatches(q);
    if (!matches.length) {
      return "Không có nhân viên khớp từ khóa tìm kiếm — xóa ô tìm hoặc nhập lại.";
    }
    return null;
  }

  function syncExportPeriodUi() {
    const mode = (exportPeriodEl?.value || "month").toString();
    if (exportQuarterWrap) exportQuarterWrap.hidden = mode !== "quarter";
    if (exportFromWrap) exportFromWrap.hidden = mode !== "range";
    if (exportToWrap) exportToWrap.hidden = mode !== "range";
    const { y, m, from, to } = getPeriod();
    if (exportQuarterEl && mode === "quarter") {
      exportQuarterEl.value = String(Math.ceil(m / 3));
    }
    if (exportFromEl && mode === "range" && !exportFromEl.value) exportFromEl.value = from;
    if (exportToEl && mode === "range" && !exportToEl.value) exportToEl.value = to;
    if (exportHintEl) {
      if (mode === "month") {
        exportHintEl.textContent = `Xuất lương tháng ${m}/${y} (Năm / Tháng ở thanh công cụ trên).`;
      } else if (mode === "quarter") {
        const q = exportQuarterEl?.value || "1";
        exportHintEl.textContent = `Xuất lương quý Q${q}/${y} — gộp các tháng trong quý; file Excel có thêm sheet Tổng hợp.`;
      } else {
        exportHintEl.textContent =
          "Xuất mọi kỳ lương có tháng nằm trong khoảng đã chọn; file Excel có thêm sheet Tổng hợp theo nhân viên.";
      }
    }
  }

  function payrollExportUrl(format) {
    const { y } = getPeriod();
    const p = new URLSearchParams();
    p.set("format", format);
    const mode = (exportPeriodEl?.value || "month").toString();
    p.set("period", mode);
    p.set("year", String(y));
    if (mode === "month") {
      p.set("month", String(getPeriod().m));
    } else if (mode === "quarter") {
      p.set("quarter", String(exportQuarterEl?.value || "1"));
    } else {
      const df = (exportFromEl?.value || "").trim();
      const dt = (exportToEl?.value || "").trim();
      if (df) p.set("from", df);
      if (dt) p.set("to", dt);
    }
    const { staff_id: sid, q } = resolveExportStaffFilter();
    if (sid) p.set("staff_id", sid);
    else if (q) p.set("q", q);
    return `/api/crm/payroll/export?${p.toString()}`;
  }

  async function loadStaff() {
    if (STAFF_PORTAL) {
      const data = await reqJson("/api/crm/staff/me");
      const profile = data.staff && typeof data.staff === "object" ? data.staff : null;
      staffList = profile ? [profile] : [];
      return;
    }
    const data = await reqJson("/api/crm/staff");
    staffList = Array.isArray(data.staff) ? data.staff : [];
    fillStaffSelects();
  }

  async function loadAttendance() {
    const { y, m, from, to } = getPeriod();
    const qs = new URLSearchParams({ from, to });
    const data = await reqJson(`/api/crm/attendance?${qs.toString()}`);
    attendanceRows = Array.isArray(data.attendance) ? data.attendance : [];
    renderAttendance();
    hintEl.textContent = `Đang xem tháng ${m}/${y} (${from} → ${to}).`;
  }

  function renderAttendance() {
    const rows = filterAttendanceRows();
    updateAttendanceSummary(rows);
    attEmpty.hidden = rows.length > 0;
    if (!attTbody) return;
    attTbody.innerHTML = rows
      .map((r) => {
        const staffCell = STAFF_PORTAL
          ? ""
          : `<td>${esc((r.staff_name || "").toString())}</td>`;
        return `<tr>
          <td>${fmtDate(r.work_date)}</td>
          ${staffCell}
          <td>${esc((r.check_in || "").toString()) || "—"}</td>
          <td>${esc((r.check_out || "").toString()) || "—"}</td>
          <td>${fmtHours(r.worked_hours)}</td>
          <td>${Number(r.late_minutes || 0) > 0 ? esc(String(r.late_minutes)) : "—"}</td>
          <td>${Number(r.late_penalty_vnd || 0) > 0 ? fmtMoney(r.late_penalty_vnd) : "—"}</td>
          <td>${esc(String(r.break_minutes ?? 0))}</td>
          <td>${esc((r.note || "").toString()).slice(0, 80)}</td>
        </tr>`;
      })
      .join("");
  }

  async function loadPayroll() {
    const { y, m } = getPeriod();
    const data = await reqJson(`/api/crm/payroll?year=${y}&month=${m}`);
    payrollHeader = data.payroll || null;
    payrollLines = Array.isArray(data.lines) ? data.lines : [];
    renderPayroll();
  }

  function renderPayroll() {
    prErr.hidden = true;
    const { y, m } = getPeriod();
    if (!payrollHeader) {
      prMeta.innerHTML = `Chưa có kỳ lương cho <strong>${m}/${y}</strong>. Bấm <strong>Tính / cập nhật lương</strong> sau khi đã nhập chấm công và đặt lương cơ bản cho nhân viên.`;
      prTable.hidden = true;
      prEmpty.hidden = false;
      btnLock.hidden = true;
      btnUnlock.hidden = true;
      btnCompute.disabled = false;
      if (prCountEl) prCountEl.textContent = "";
      if (prMiniStatsEl) prMiniStatsEl.innerHTML = "";
      return;
    }
    const st = String(payrollHeader.status || "draft");
    const locked = st === "final";
    const std = payrollHeader.workdays_standard ?? "—";
    prMeta.innerHTML = `Kỳ <strong>${m}/${y}</strong> — trạng thái: <strong>${locked ? "Đã khóa" : "Nháp"}</strong>. Ngày làm chuẩn: <strong>${esc(
      String(std),
    )}</strong>. Lương tính theo <strong>giờ làm</strong> × đơn giá giờ.`;
    btnLock.hidden = locked;
    btnUnlock.hidden = !locked;
    btnCompute.disabled = locked;

    if (!payrollLines.length) {
      prTable.hidden = true;
      prEmpty.hidden = false;
      if (prCountEl) prCountEl.textContent = "";
      if (prMiniStatsEl) prMiniStatsEl.innerHTML = "";
    } else {
      prEmpty.hidden = true;
      prTable.hidden = false;
    }

    const visibleLines = filterPayrollLines();
    updatePayrollSummary(visibleLines);

    if (!prTbody) return;
    prTbody.innerHTML = visibleLines
      .map((line) => {
        const lid = line.id;
        const posAllow = Number(line.position_allowance_vnd || 0);
        const bonus = Number(line.bonus_vnd || 0);
        const lateDed = Number(line.late_deduction_vnd || 0);
        const autoAllow = posAllow + bonus;
        const allow = Number(line.allowances_vnd || 0);
        const ded = Number(line.deductions_vnd || 0);
        const manualAllow = Math.max(0, allow - autoAllow);
        const manualDed = Math.max(0, ded - lateDed);
        const note = (line.note || "").toString();
        const sid = esc(String(line.staff_name || ""));
        const code = esc((line.staff_code || "").toString());
        return `<tr data-line-id="${esc(String(lid))}">
          <td>${code || "—"}</td>
          <td>${sid}</td>
          <td>${esc(String(line.days_present ?? 0))}</td>
          <td>${fmtHours(line.hours_worked_total)}</td>
          <td>${Number(line.late_minutes_total || 0) > 0 ? esc(String(line.late_minutes_total)) : "—"}</td>
          <td>${fmtMoney(line.base_salary_vnd)}</td>
          <td>${fmtMoney(line.salary_from_attendance_vnd)}</td>
          <td>${fmtMoney(posAllow)}</td>
          <td>${fmtMoney(bonus)}</td>
          <td>${fmtMoney(lateDed)}</td>
          <td><input type="number" class="crm-pr-num" data-k="allow" min="0" max="9999999999" step="1" value="${manualAllow}" ${
            locked ? "disabled" : ""
          } aria-label="Phụ cấp thêm" title="Cộng thêm ngoài PC cấp bậc và thưởng" /></td>
          <td><input type="number" class="crm-pr-num" data-k="ded" min="0" max="9999999999" step="1" value="${manualDed}" ${
            locked ? "disabled" : ""
          } aria-label="Khấu trừ thêm" title="Trừ thêm ngoài phạt đi trễ" /></td>
          <td class="crm-pr-net" data-net>${fmtMoney(line.net_salary_vnd)}</td>
          <td><input type="text" class="crm-pr-note" data-k="note" maxlength="2000" value="${escAttr(
            note,
          )}" ${locked ? "disabled" : ""} /></td>
          <td>${
            locked
              ? "—"
              : `<button type="button" class="btn-secondary crm-pr-save-line" data-id="${esc(String(lid))}">Lưu dòng</button>`
          }</td>
        </tr>`;
      })
      .join("");
  }

  async function saveLine(lineId, tr) {
    const allowInp = tr.querySelector('input[data-k="allow"]');
    const dedInp = tr.querySelector('input[data-k="ded"]');
    const noteInp = tr.querySelector('input[data-k="note"]');
    prErr.hidden = true;
    const line = payrollLines.find((l) => Number(l.id) === lineId);
    const posAllow = Number(line?.position_allowance_vnd || 0);
    const bonus = Number(line?.bonus_vnd || 0);
    const lateDed = Number(line?.late_deduction_vnd || 0);
    const manualAllow = Number(allowInp?.value || 0);
    const manualDed = Number(dedInp?.value || 0);
    await reqJson(`/api/crm/payroll/line/${lineId}`, {
      method: "PATCH",
      body: JSON.stringify({
        allowances_vnd: posAllow + bonus + manualAllow,
        deductions_vnd: lateDed + manualDed,
        note: (noteInp?.value || "").toString(),
      }),
    });
    await loadPayroll();
  }

  async function onCompute() {
    prErr.hidden = true;
    const { y, m } = getPeriod();
    try {
      await reqJson("/api/crm/payroll/compute", {
        method: "POST",
        body: JSON.stringify({ year: y, month: m }),
      });
      await loadPayroll();
    } catch (e) {
      prErr.textContent = e instanceof Error ? e.message : "Lỗi";
      prErr.hidden = false;
    }
  }

  async function setPayrollStatus(finalized) {
    prErr.hidden = true;
    const { y, m } = getPeriod();
    if (!payrollHeader?.id) {
      const d = await reqJson(`/api/crm/payroll?year=${y}&month=${m}`);
      if (!d.payroll) return;
      payrollHeader = d.payroll;
    }
    const pid = Number(payrollHeader.id);
    if (!pid) return;
    await reqJson(`/api/crm/payroll/${pid}`, {
      method: "PATCH",
      body: JSON.stringify({ status: finalized ? "final" : "draft" }),
    });
    await loadPayroll();
  }

  attForm?.addEventListener("submit", async (ev) => {
    ev.preventDefault();
    attErr.hidden = true;
    if (attImportOk) attImportOk.hidden = true;
    const fd = new FormData(attForm);
    const staff_id = fd.get("staff_id");
    if (!staff_id) return;
    const work_date = (fd.get("work_date") || "").toString().trim();
    const today = todayYmdLocal();
    if (work_date > today) {
      attErr.textContent = "Ngày chấm công không được sau ngày hiện tại.";
      attErr.hidden = false;
      return;
    }
    try {
      await reqJson("/api/crm/attendance", {
        method: "POST",
        body: JSON.stringify({
          staff_id: Number(staff_id),
          work_date,
          check_in: (fd.get("check_in") || "").toString().trim(),
          check_out: (fd.get("check_out") || "").toString().trim(),
          break_minutes: Number(fd.get("break_minutes") || 0),
          note: (fd.get("note") || "").toString().trim(),
        }),
      });
      await loadAttendance();
    } catch (e) {
      attErr.textContent = e instanceof Error ? e.message : "Lỗi";
      attErr.hidden = false;
    }
  });

  attFilter?.addEventListener("change", () => {
    renderAttendance();
  });

  let attSearchTimer = 0;
  attSearchEl?.addEventListener("input", () => {
    window.clearTimeout(attSearchTimer);
    attSearchTimer = window.setTimeout(() => renderAttendance(), 150);
  });

  let prSearchTimer = 0;
  prSearchEl?.addEventListener("input", () => {
    window.clearTimeout(prSearchTimer);
    prSearchTimer = window.setTimeout(() => renderPayroll(), 150);
  });

  btnPrevMonth?.addEventListener("click", () => shiftPeriod(-1));
  btnNextMonth?.addEventListener("click", () => shiftPeriod(1));

  attImportBtn?.addEventListener("click", async () => {
    attErr.hidden = true;
    if (attImportOk) attImportOk.hidden = true;
    const fileInput = attImportFile;
    const file = fileInput?.files?.[0];
    if (!file) {
      attErr.textContent = "Chọn file Excel (.xlsx) trước khi nhập.";
      attErr.hidden = false;
      return;
    }
    const fd = new FormData();
    fd.append("file", file);
    attImportBtn.disabled = true;
    try {
      const res = await fetch("/api/crm/attendance/import", {
        method: "POST",
        credentials: "same-origin",
        body: fd,
      });
      const ct = res.headers.get("Content-Type") || "";
      let data = {};
      if (ct.includes("application/json")) {
        data = await res.json();
      }
      if (res.status === 401 && typeof data.login === "string") {
        window.location.href = data.login;
        return;
      }
      if (!res.ok) {
        throw new Error(data.error || res.statusText || "Lỗi nhập file");
      }
      const msg = String(data.message || `Đã nhập ${data.imported ?? 0} dòng.`);
      if (attImportOk) {
        attImportOk.textContent = msg;
        attImportOk.hidden = false;
      }
      if (Array.isArray(data.errors) && data.errors.length) {
        attErr.textContent = data.errors.slice(0, 5).join(" · ");
        attErr.hidden = false;
      }
      await loadAttendance();
      if (!STAFF_PORTAL) await loadPayroll();
    } catch (e) {
      attErr.textContent = e instanceof Error ? e.message : "Lỗi nhập file";
      attErr.hidden = false;
    } finally {
      attImportBtn.disabled = false;
    }
  });

  prTbody?.addEventListener("click", (ev) => {
    const t = ev.target;
    if (!(t instanceof HTMLElement)) return;
    const btn = t.closest(".crm-pr-save-line");
    if (!btn) return;
    const id = btn.getAttribute("data-id");
    if (!id) return;
    const tr = btn.closest("tr");
    if (!tr) return;
    saveLine(Number(id), tr).catch((e) => {
      prErr.textContent = e instanceof Error ? e.message : "Lỗi";
      prErr.hidden = false;
    });
  });

  btnRefresh?.addEventListener("click", () => {
    reloadPeriodData().catch((e) => {
      attErr.textContent = e instanceof Error ? e.message : "Lỗi";
      attErr.hidden = false;
    });
  });

  btnSavePolicy?.addEventListener("click", () => {
    savePolicy().catch((e) => {
      if (policyErr) {
        policyErr.textContent = e instanceof Error ? e.message : "Lỗi";
        policyErr.hidden = false;
      }
    });
  });

  btnSavePositions?.addEventListener("click", () => {
    savePositionRates().catch((e) => {
      if (policyErr) {
        policyErr.textContent = e instanceof Error ? e.message : "Lỗi";
        policyErr.hidden = false;
      }
    });
  });

  policyForm?.addEventListener("submit", (ev) => {
    ev.preventDefault();
    btnSavePolicy?.click();
  });

  btnCompute?.addEventListener("click", () => {
    onCompute();
  });

  btnLock?.addEventListener("click", () => {
    setPayrollStatus(true).catch((e) => {
      prErr.textContent = e instanceof Error ? e.message : "Lỗi";
      prErr.hidden = false;
    });
  });

  btnUnlock?.addEventListener("click", () => {
    setPayrollStatus(false).catch((e) => {
      prErr.textContent = e instanceof Error ? e.message : "Lỗi";
      prErr.hidden = false;
    });
  });

  function todayYmdLocal() {
    const d = new Date();
    const y = d.getFullYear();
    const m = String(d.getMonth() + 1).padStart(2, "0");
    const day = String(d.getDate()).padStart(2, "0");
    return `${y}-${m}-${day}`;
  }

  function syncAttDateMax() {
    if (attDate) attDate.max = todayYmdLocal();
  }

  function setAttDateFromPeriod() {
    syncAttDateMax();
    const { from } = getPeriod();
    const today = todayYmdLocal();
    if (attDate) attDate.value = from.slice(0, 10) > today ? today : from.slice(0, 10);
  }

  function initPeriodDefaults() {
    const d = new Date();
    if (yearEl) yearEl.value = String(d.getFullYear());
    if (monthEl) monthEl.value = String(d.getMonth() + 1);
    setAttDateFromPeriod();
  }

  function initSectionCollapsibles() {
    document.querySelectorAll(".crm-section-collapsible").forEach((section) => {
      const headToggle = section.querySelector(
        ":scope > .crm-staff-section-head .crm-section-toggle, :scope > .crm-payroll-panel-head .crm-section-toggle",
      );
      const toggle =
        headToggle instanceof HTMLButtonElement
          ? headToggle
          : section.querySelector(":scope > .crm-section-head-actions .crm-section-toggle");
      if (!(toggle instanceof HTMLButtonElement)) return;
      const setOpen = (open) => {
        section.classList.toggle("is-open", open);
        toggle.setAttribute("aria-expanded", open ? "true" : "false");
        toggle.textContent = open ? "Thu gọn" : "Mở rộng";
      };
      setOpen(section.classList.contains("is-open"));
      toggle.addEventListener("click", () => {
        setOpen(!section.classList.contains("is-open"));
      });
    });
  }

  exportPeriodEl?.addEventListener("change", () => syncExportPeriodUi());
  exportQuarterEl?.addEventListener("change", () => syncExportPeriodUi());
  let exportStaffSearchTimer = 0;
  exportStaffSearchEl?.addEventListener("input", () => {
    window.clearTimeout(exportStaffSearchTimer);
    exportStaffSearchTimer = window.setTimeout(() => renderExportStaffSelect(), 150);
  });

  async function readFetchError(res) {
    const fallback =
      res.status === 400
        ? "Yêu cầu xuất không hợp lệ — kiểm tra kỳ và thử lại."
        : res.status === 403
          ? "Bạn không có quyền xuất bảng lương."
          : res.status === 404
            ? "Không tìm thấy API xuất — tải lại trang (Ctrl+F5) hoặc liên hệ quản trị."
            : "Lỗi xuất file";
    try {
      const text = await res.text();
      if (text) {
        try {
          const data = JSON.parse(text);
          if (data?.error) return String(data.error);
          if (res.status === 401 && typeof data?.login === "string") {
            window.location.href = data.login;
            return "";
          }
        } catch {
          if (text.length < 300 && !text.includes("<html")) return text.trim();
        }
      }
    } catch {
      /* ignore */
    }
    return res.statusText && res.statusText !== "OK" ? res.statusText : fallback;
  }

  async function downloadPayrollExport(format) {
    prErr.hidden = true;
    const staffFilterErr = validateExportStaffFilter();
    if (staffFilterErr) {
      prErr.textContent = staffFilterErr;
      prErr.hidden = false;
      prErr.scrollIntoView({ behavior: "smooth", block: "nearest" });
      return;
    }
    const mode = (exportPeriodEl?.value || "month").toString();
    const { y, m } = getPeriod();
    if (mode === "month" && !STAFF_PORTAL && !payrollHeader) {
      prErr.textContent = `Chưa có kỳ lương tháng ${m}/${y}. Bấm «Tính / cập nhật lương» trước khi xuất.`;
      prErr.hidden = false;
      prErr.scrollIntoView({ behavior: "smooth", block: "nearest" });
      return;
    }
    try {
      const res = await fetch(payrollExportUrl(format), { credentials: "same-origin" });
      if (!res.ok) {
        const msg = await readFetchError(res);
        if (!msg) return;
        throw new Error(msg);
      }
      const blob = await res.blob();
      const cd = res.headers.get("Content-Disposition") || "";
      let fn = format === "csv" ? "crm-luong.csv" : "crm-luong.xlsx";
      const star = cd.match(/filename\*=UTF-8''([^;\s]+)/i);
      const plain = cd.match(/filename="([^"]+)"/i);
      if (star?.[1]) fn = decodeURIComponent(star[1]);
      else if (plain?.[1]) fn = plain[1];
      const url = URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      a.download = fn;
      a.rel = "noopener";
      document.body.appendChild(a);
      a.click();
      a.remove();
      URL.revokeObjectURL(url);
    } catch (e) {
      prErr.textContent = e instanceof Error ? e.message : "Lỗi xuất file";
      prErr.hidden = false;
      prErr.scrollIntoView({ behavior: "smooth", block: "nearest" });
    }
  }

  btnExportXlsx?.addEventListener("click", () => {
    downloadPayrollExport("xlsx");
  });
  btnExportCsv?.addEventListener("click", () => {
    downloadPayrollExport("csv");
  });

  (async function boot() {
    initSectionCollapsibles();
    initPayrollNavSpy();
    initPeriodDefaults();
    syncExportPeriodUi();
    try {
      await loadStaff();
      await loadAttendance();
      if (!STAFF_PORTAL) {
        await loadDashboard();
        await loadPayroll();
      }
    } catch (e) {
      attErr.textContent = e instanceof Error ? e.message : "Lỗi tải trang";
      attErr.hidden = false;
    }
  })();

  yearEl?.addEventListener("change", async () => {
    setAttDateFromPeriod();
    syncExportPeriodUi();
    if (!STAFF_PORTAL) {
      try {
        await loadDashboard();
        await loadPayroll();
      } catch {
        /* ignore */
      }
    }
  });

  monthEl?.addEventListener("change", async () => {
    setAttDateFromPeriod();
    syncExportPeriodUi();
    if (!STAFF_PORTAL) {
      try {
        await loadDashboard();
        await loadPayroll();
      } catch {
        /* ignore */
      }
    }
  });

  document.querySelectorAll(".crm-device-copy").forEach((el) => {
    el.addEventListener("click", async () => {
      const u = el.getAttribute("data-copy")?.trim() || "";
      if (!u) return;
      try {
        await navigator.clipboard.writeText(u);
        const prev = el.textContent;
        el.textContent = "Đã chép";
        setTimeout(() => {
          el.textContent = prev || "Sao chép";
        }, 1800);
      } catch {
        if (attErr) {
          attErr.textContent = "Không sao chép tự động — chọn URL và dùng Ctrl+C / Cmd+C.";
          attErr.hidden = false;
        }
      }
    });
  });
})();
