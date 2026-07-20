/** Chính sách chấm công / lương theo giờ — ported from crm_payroll_engine.py */

import { DatabaseSync } from 'node:sqlite';
import { catalogTs } from '../catalog/catalog-slug.util';

export const DEFAULT_POLICY: Record<string, unknown> = {
  work_weekdays: '0,1,2,3,4',
  shift_start: '08:30',
  shift_end: '17:30',
  break_minutes_default: 60,
  late_grace_minutes: 5,
  late_penalty_vnd_per_min: 5000,
  late_penalty_max_vnd: 200_000,
  standard_hours_per_day: 8.0,
  bonus_mode: 'attendance',
  bonus_pct: 5.0,
  bonus_min_days: 20,
  overtime_multiplier: 1.5,
  weekday_shifts: '',
};

export const WEEKDAY_LABELS = ['T2', 'T3', 'T4', 'T5', 'T6', 'T7', 'CN'];

export type PolicyRecord = Record<string, unknown>;
export type WeekdayShift = Record<string, unknown>;
export type PositionPayrollRow = Record<string, unknown>;

function hhmmToMinutes(s: string): number | null {
  const m = /^(\d{1,2}):(\d{2})$/.exec((s || '').trim());
  if (!m) return null;
  const h = Number(m[1]);
  const mm = Number(m[2]);
  if (h > 23 || mm > 59) return null;
  return h * 60 + mm;
}

export function parseWorkWeekdays(raw: string | null | undefined): Set<number> {
  if (!raw || !String(raw).trim()) return new Set([0, 1, 2, 3, 4]);
  const out = new Set<number>();
  for (const part of String(raw).split(',')) {
    const p = part.trim();
    if (!p) continue;
    const d = Number(p);
    if (Number.isFinite(d) && d >= 0 && d <= 6) out.add(d);
  }
  return out.size > 0 ? out : new Set([0, 1, 2, 3, 4]);
}

export function pythonWeekday(year: number, month: number, day: number): number {
  return (new Date(year, month - 1, day).getDay() + 6) % 7;
}

export function monthLastDay(year: number, month: number): number {
  return new Date(year, month, 0).getDate();
}

export function defaultWeekdayShifts(opts?: {
  workWeekdays?: Set<number>;
  shiftStart?: string;
  shiftEnd?: string;
  breakMinutes?: number;
  standardHours?: number;
}): WeekdayShift[] {
  const work = opts?.workWeekdays ?? new Set([0, 1, 2, 3, 4]);
  const shiftStart = opts?.shiftStart ?? '08:30';
  const shiftEnd = opts?.shiftEnd ?? '17:30';
  const breakMinutes = opts?.breakMinutes ?? 60;
  const standardHours = opts?.standardHours ?? 8.0;
  return Array.from({ length: 7 }, (_, wd) => ({
    weekday: wd,
    label: WEEKDAY_LABELS[wd],
    work: work.has(wd),
    shift_start: shiftStart,
    shift_end: shiftEnd,
    break_minutes: breakMinutes,
    standard_hours: standardHours,
  }));
}

export function normalizeWeekdayShifts(items: unknown[]): WeekdayShift[] {
  const defaults = defaultWeekdayShifts();
  const defaultMap = Object.fromEntries(defaults.map((d) => [Number(d.weekday), d]));
  const byWd: Record<number, WeekdayShift> = {};
  for (const item of items) {
    if (!item || typeof item !== 'object') continue;
    const rec = item as Record<string, unknown>;
    const wd = Number(rec.weekday ?? -1);
    if (!Number.isFinite(wd) || wd < 0 || wd > 6) continue;
    const base = defaultMap[wd] as WeekdayShift;
    let brk = Number(rec.break_minutes ?? base.break_minutes);
    if (!Number.isFinite(brk)) brk = Number(base.break_minutes);
    let stdH = Number(rec.standard_hours ?? base.standard_hours);
    if (!Number.isFinite(stdH)) stdH = Number(base.standard_hours);
    byWd[wd] = {
      weekday: wd,
      label: WEEKDAY_LABELS[wd],
      work: Boolean(rec.work ?? base.work),
      shift_start: String(rec.shift_start ?? base.shift_start).trim().slice(0, 5),
      shift_end: String(rec.shift_end ?? base.shift_end).trim().slice(0, 5),
      break_minutes: Math.max(0, Math.min(brk, 24 * 60)),
      standard_hours: Math.max(0.5, Math.min(stdH, 24.0)),
    };
  }
  return Array.from({ length: 7 }, (_, wd) => byWd[wd] ?? defaultMap[wd]);
}

export function parseWeekdayShifts(policy: PolicyRecord): WeekdayShift[] {
  const raw = policy.weekday_shifts;
  let data: unknown[] | null = null;
  if (Array.isArray(raw)) {
    data = raw;
  } else if (typeof raw === 'string' && raw.trim()) {
    try {
      const parsed = JSON.parse(raw);
      if (Array.isArray(parsed)) data = parsed;
    } catch {
      data = null;
    }
  }
  if (data) return normalizeWeekdayShifts(data);
  const work = parseWorkWeekdays(String(policy.work_weekdays ?? ''));
  return defaultWeekdayShifts({
    workWeekdays: work,
    shiftStart: String(policy.shift_start ?? '08:30'),
    shiftEnd: String(policy.shift_end ?? '17:30'),
    breakMinutes: Number(policy.break_minutes_default ?? 60),
    standardHours: Number(policy.standard_hours_per_day ?? 8),
  });
}

export function weekdayShiftsJson(shifts: WeekdayShift[]): string {
  const compact = shifts.map((s) => ({
    weekday: s.weekday,
    work: Boolean(s.work),
    shift_start: String(s.shift_start ?? '08:30'),
    shift_end: String(s.shift_end ?? '17:30'),
    break_minutes: Number(s.break_minutes ?? 0),
    standard_hours: Number(s.standard_hours ?? 8),
  }));
  return JSON.stringify(compact);
}

export function workWeekdaysFromShifts(shifts: WeekdayShift[]): string {
  const days = shifts.filter((s) => s.work).map((s) => String(Number(s.weekday)));
  return days.length > 0 ? days.join(',') : '0,1,2,3,4';
}

export function shiftForWeekday(policy: PolicyRecord, weekday: number): WeekdayShift {
  for (const s of parseWeekdayShifts(policy)) {
    if (Number(s.weekday) === weekday) return s;
  }
  return defaultWeekdayShifts()[weekday % 7];
}

export function expectedStandardHoursInMonth(
  year: number,
  month: number,
  policy: PolicyRecord,
): number {
  const shiftMap = Object.fromEntries(
    parseWeekdayShifts(policy).map((s) => [Number(s.weekday), s]),
  );
  const last = monthLastDay(year, month);
  let total = 0;
  for (let d = 1; d <= last; d++) {
    const wd = pythonWeekday(year, month, d);
    const s = shiftMap[wd] as WeekdayShift | undefined;
    if (s?.work) total += Number(s.standard_hours ?? 8);
  }
  return Math.max(total, 0.5);
}

export function countWorkdaysInMonth(year: number, month: number, weekdays: Set<number>): number {
  const last = monthLastDay(year, month);
  let n = 0;
  for (let d = 1; d <= last; d++) {
    if (weekdays.has(pythonWeekday(year, month, d))) n++;
  }
  return Math.max(n, 1);
}

function tableColumns(db: DatabaseSync, table: string): Set<string> {
  const rows = db.prepare(`PRAGMA table_info(${table})`).all() as Array<{ name: string }>;
  return new Set(rows.map((r) => r.name));
}

function seedPositionPayrollDefaults(db: DatabaseSync): void {
  const rows = db
    .prepare('SELECT id, code, sort_order FROM crm_positions WHERE active = 1 ORDER BY sort_order')
    .all() as Array<{ id: number; code: string; sort_order: number }>;
  if (rows.length === 0) return;
  const ts = catalogTs();
  const defaultsByCode: Record<string, [number, number, number]> = {
    'CSKH-01': [1, 500_000, 0.0],
    'KD-01': [2, 1_000_000, 5.0],
    'VH-01': [3, 1_500_000, 8.0],
  };
  rows.forEach((r, i) => {
    const pid = Number(r.id);
    const exists = db.prepare('SELECT 1 FROM crm_position_payroll WHERE position_id = ?').get(pid);
    if (exists) return;
    const code = String(r.code ?? '');
    const [rank, allow, bp] =
      code in defaultsByCode ? defaultsByCode[code]! : [i + 1, Math.max(0, (4 - i) * 300_000), 0.0];
    db.prepare(
      `INSERT INTO crm_position_payroll (position_id, rank_level, allowance_vnd, bonus_pct, updated_at)
       VALUES (?, ?, ?, ?, ?)`,
    ).run(pid, rank, allow, bp, ts);
  });
}

function migrateWeekdayShiftsColumn(db: DatabaseSync): void {
  const cols = tableColumns(db, 'crm_payroll_policy');
  if (!cols.has('weekday_shifts')) {
    try {
      db.exec(
        "ALTER TABLE crm_payroll_policy ADD COLUMN weekday_shifts TEXT NOT NULL DEFAULT ''",
      );
    } catch {
      /* column may exist */
    }
  }
  const row = db
    .prepare(
      `SELECT work_weekdays, shift_start, shift_end, break_minutes_default,
              standard_hours_per_day, weekday_shifts FROM crm_payroll_policy WHERE id = 1`,
    )
    .get() as PolicyRecord | undefined;
  if (!row) return;
  if (String(row.weekday_shifts ?? '').trim()) return;
  const shifts = parseWeekdayShifts(row);
  const ts = catalogTs();
  db.prepare('UPDATE crm_payroll_policy SET weekday_shifts = ?, updated_at = ? WHERE id = 1').run(
    weekdayShiftsJson(shifts),
    ts,
  );
}

export function ensurePayrollPolicySchema(db: DatabaseSync): void {
  db.exec(`
    CREATE TABLE IF NOT EXISTS crm_payroll_policy (
      id INTEGER PRIMARY KEY CHECK (id = 1),
      work_weekdays TEXT NOT NULL DEFAULT '0,1,2,3,4',
      shift_start TEXT NOT NULL DEFAULT '08:30',
      shift_end TEXT NOT NULL DEFAULT '17:30',
      break_minutes_default INTEGER NOT NULL DEFAULT 60,
      late_grace_minutes INTEGER NOT NULL DEFAULT 5,
      late_penalty_vnd_per_min INTEGER NOT NULL DEFAULT 5000,
      late_penalty_max_vnd INTEGER NOT NULL DEFAULT 200000,
      standard_hours_per_day REAL NOT NULL DEFAULT 8,
      bonus_mode TEXT NOT NULL DEFAULT 'attendance',
      bonus_pct REAL NOT NULL DEFAULT 5,
      bonus_min_days INTEGER NOT NULL DEFAULT 20,
      overtime_multiplier REAL NOT NULL DEFAULT 1.5,
      updated_at TEXT NOT NULL DEFAULT ''
    )
  `);
  const exists = db.prepare('SELECT id FROM crm_payroll_policy WHERE id = 1').get();
  if (!exists) {
    const ts = catalogTs();
    const p = DEFAULT_POLICY;
    db.prepare(
      `INSERT INTO crm_payroll_policy (
         id, work_weekdays, shift_start, shift_end, break_minutes_default,
         late_grace_minutes, late_penalty_vnd_per_min, late_penalty_max_vnd,
         standard_hours_per_day, bonus_mode, bonus_pct, bonus_min_days,
         overtime_multiplier, updated_at
       ) VALUES (1, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)`,
    ).run(
      String(p.work_weekdays),
      String(p.shift_start),
      String(p.shift_end),
      Number(p.break_minutes_default),
      Number(p.late_grace_minutes),
      Number(p.late_penalty_vnd_per_min),
      Number(p.late_penalty_max_vnd),
      Number(p.standard_hours_per_day),
      String(p.bonus_mode),
      Number(p.bonus_pct),
      Number(p.bonus_min_days),
      Number(p.overtime_multiplier),
      ts,
    );
  }
  db.exec(`
    CREATE TABLE IF NOT EXISTS crm_position_payroll (
      position_id INTEGER PRIMARY KEY REFERENCES crm_positions(id) ON DELETE CASCADE,
      rank_level INTEGER NOT NULL DEFAULT 1,
      allowance_vnd INTEGER NOT NULL DEFAULT 0,
      bonus_pct REAL NOT NULL DEFAULT 0,
      updated_at TEXT NOT NULL DEFAULT ''
    )
  `);
  const plCols = tableColumns(db, 'crm_payroll_line');
  for (const [col, ddl] of [
    ['hours_worked_total', 'REAL NOT NULL DEFAULT 0'],
    ['late_minutes_total', 'INTEGER NOT NULL DEFAULT 0'],
    ['late_deduction_vnd', 'INTEGER NOT NULL DEFAULT 0'],
    ['position_allowance_vnd', 'INTEGER NOT NULL DEFAULT 0'],
    ['bonus_vnd', 'INTEGER NOT NULL DEFAULT 0'],
  ] as const) {
    if (!plCols.has(col)) {
      try {
        db.exec(`ALTER TABLE crm_payroll_line ADD COLUMN ${col} ${ddl}`);
      } catch {
        /* ignore */
      }
    }
  }
  seedPositionPayrollDefaults(db);
  migrateWeekdayShiftsColumn(db);
}

export function loadPolicy(db: DatabaseSync): PolicyRecord {
  ensurePayrollPolicySchema(db);
  const row = db.prepare('SELECT * FROM crm_payroll_policy WHERE id = 1').get() as
    | PolicyRecord
    | undefined;
  return row ? { ...row } : { ...DEFAULT_POLICY };
}

export function loadPositionPayrollMap(db: DatabaseSync): Record<number, PositionPayrollRow> {
  ensurePayrollPolicySchema(db);
  const rows = db
    .prepare(
      `SELECT pp.*, p.code AS position_code, p.name AS position_name
       FROM crm_position_payroll pp
       JOIN crm_positions p ON p.id = pp.position_id
       WHERE p.active = 1
       ORDER BY pp.rank_level ASC, p.sort_order ASC`,
    )
    .all() as PositionPayrollRow[];
  const out: Record<number, PositionPayrollRow> = {};
  for (const r of rows) out[Number(r.position_id)] = { ...r };
  return out;
}

export function policyForApi(policy: PolicyRecord): PolicyRecord {
  const shifts = parseWeekdayShifts(policy);
  const weekdays = new Set(
    shifts.filter((s) => s.work).map((s) => Number(s.weekday)),
  );
  const labels = WEEKDAY_LABELS;
  return {
    ...policy,
    weekday_shifts: shifts,
    work_weekdays: workWeekdaysFromShifts(shifts),
    work_weekday_labels: [...weekdays].sort((a, b) => a - b).map((d) => labels[d]),
  };
}

export function analyzeAttendanceDay(opts: {
  workDate: string;
  checkIn: string;
  checkOut: string;
  breakMinutes: number;
  policy: PolicyRecord;
}): Record<string, unknown> {
  let wd = 0;
  try {
    const parts = opts.workDate.split('-').map(Number);
    wd = pythonWeekday(parts[0]!, parts[1]!, parts[2]!);
  } catch {
    wd = 0;
  }
  const shiftCfg = shiftForWeekday(opts.policy, wd);
  const isScheduled = Boolean(shiftCfg.work);
  const shiftStart = String(shiftCfg.shift_start ?? opts.policy.shift_start ?? '08:30');
  const shiftEnd = String(shiftCfg.shift_end ?? opts.policy.shift_end ?? '17:30');
  const grace = Math.max(0, Number(opts.policy.late_grace_minutes ?? 0));
  const penPer = Math.max(0, Number(opts.policy.late_penalty_vnd_per_min ?? 0));
  const penMax = Math.max(0, Number(opts.policy.late_penalty_max_vnd ?? 0));
  const stdHours = Math.max(
    0.5,
    Number(shiftCfg.standard_hours ?? opts.policy.standard_hours_per_day ?? 8),
  );
  const breakDefault = Math.max(
    0,
    Number(shiftCfg.break_minutes ?? opts.policy.break_minutes_default ?? 0),
  );
  const ci = hhmmToMinutes(String(opts.checkIn ?? '').trim());
  const co = hhmmToMinutes(String(opts.checkOut ?? '').trim());
  const ss = hhmmToMinutes(shiftStart);
  const se = hhmmToMinutes(shiftEnd);
  let workedMinutes = 0;
  let lateMinutes = 0;
  if (ci != null && co != null && co > ci) {
    const brk = Math.max(0, Math.min(Number(opts.breakMinutes ?? 0), co - ci));
    workedMinutes = Math.max(0, co - ci - brk);
  }
  if (isScheduled && ci != null && ss != null && ci > ss + grace) {
    lateMinutes = ci - ss - grace;
  }
  const latePenalty = lateMinutes > 0 ? Math.min(lateMinutes * penPer, penMax) : 0;
  const workedHours = Math.round((workedMinutes / 60.0) * 100) / 100;
  let shiftSpan = 0;
  if (ss != null && se != null && se > ss) shiftSpan = se - ss - breakDefault;
  const expectedHours = Math.round((Math.max(shiftSpan, stdHours * 60) / 60.0) * 100) / 100;
  return {
    is_scheduled_workday: isScheduled,
    worked_minutes: workedMinutes,
    worked_hours: workedHours,
    expected_hours: expectedHours,
    late_minutes: lateMinutes,
    late_penalty_vnd: latePenalty,
    has_full_punch: ci != null && co != null,
    shift_start: shiftStart,
    shift_end: shiftEnd,
    weekday_label: wd >= 0 && wd <= 6 ? WEEKDAY_LABELS[wd] : '',
  };
}

export function hourlyRateVnd(
  baseSalaryVnd: number,
  year: number,
  month: number,
  policy: PolicyRecord,
): number {
  const denom = expectedStandardHoursInMonth(year, month, policy);
  if (baseSalaryVnd <= 0 || denom <= 0) return 0;
  return baseSalaryVnd / denom;
}

export function computeStaffPayroll(
  db: DatabaseSync,
  opts: {
    staffId: number;
    baseSalaryVnd: number;
    positionId: number | null;
    year: number;
    month: number;
    policy: PolicyRecord;
    positionMap: Record<number, PositionPayrollRow>;
  },
): Record<string, unknown> {
  const d0 = `${opts.year.toString().padStart(4, '0')}-${String(opts.month).padStart(2, '0')}-01`;
  const last = monthLastDay(opts.year, opts.month);
  const d1 = `${opts.year.toString().padStart(4, '0')}-${String(opts.month).padStart(2, '0')}-${String(last).padStart(2, '0')}`;
  const rows = db
    .prepare(
      `SELECT work_date, check_in, check_out, break_minutes
       FROM crm_attendance
       WHERE staff_id = ? AND work_date >= ? AND work_date <= ?
       ORDER BY work_date ASC`,
    )
    .all(opts.staffId, d0, d1) as Array<Record<string, unknown>>;
  const rate = hourlyRateVnd(opts.baseSalaryVnd, opts.year, opts.month, opts.policy);
  let totalHours = 0;
  let lateMinutesTotal = 0;
  let lateDeduction = 0;
  let daysPresent = 0;
  for (const r of rows) {
    const day = analyzeAttendanceDay({
      workDate: String(r.work_date),
      checkIn: String(r.check_in ?? ''),
      checkOut: String(r.check_out ?? ''),
      breakMinutes: Number(r.break_minutes ?? 0),
      policy: opts.policy,
    });
    if (!day.has_full_punch) continue;
    daysPresent++;
    totalHours += Number(day.worked_hours);
    lateMinutesTotal += Number(day.late_minutes);
    lateDeduction += Number(day.late_penalty_vnd);
  }
  const salaryFromHours = Math.round(totalHours * rate);
  const pos = opts.positionId != null ? opts.positionMap[opts.positionId] : undefined;
  const positionAllowance = pos ? Number(pos.allowance_vnd ?? 0) : 0;
  const posBonusPct = pos ? Number(pos.bonus_pct ?? 0) : 0;
  let bonusVnd = 0;
  const bonusMode = String(opts.policy.bonus_mode ?? 'none')
    .trim()
    .toLowerCase();
  const policyBonusPct = Number(opts.policy.bonus_pct ?? 0);
  const bonusMinDays = Number(opts.policy.bonus_min_days ?? 0);
  if (bonusMode !== 'none' && daysPresent >= bonusMinDays && opts.baseSalaryVnd > 0) {
    bonusVnd = Math.round(opts.baseSalaryVnd * (policyBonusPct + posBonusPct) / 100.0);
  }
  const manualAllow = 0;
  const manualDed = 0;
  return {
    days_present: daysPresent,
    hours_worked_total: Math.round(totalHours * 100) / 100,
    late_minutes_total: lateMinutesTotal,
    late_deduction_vnd: lateDeduction,
    hourly_rate_vnd: Math.round(rate),
    salary_from_attendance_vnd: salaryFromHours,
    position_allowance_vnd: positionAllowance,
    bonus_vnd: bonusVnd,
    allowances_vnd: positionAllowance + bonusVnd + manualAllow,
    deductions_vnd: lateDeduction + manualDed,
    net_salary_vnd: salaryFromHours + positionAllowance + bonusVnd - lateDeduction,
  };
}

export function enrichAttendanceRow(row: Record<string, unknown>, policy: PolicyRecord): Record<string, unknown> {
  const day = analyzeAttendanceDay({
    workDate: String(row.work_date ?? ''),
    checkIn: String(row.check_in ?? ''),
    checkOut: String(row.check_out ?? ''),
    breakMinutes: Number(row.break_minutes ?? 0),
    policy,
  });
  return { ...row, ...day };
}

export function dashboardSummary(
  db: DatabaseSync,
  opts: { year: number; month: number; policy: PolicyRecord },
): Record<string, unknown> {
  const d0 = `${opts.year.toString().padStart(4, '0')}-${String(opts.month).padStart(2, '0')}-01`;
  const last = monthLastDay(opts.year, opts.month);
  const d1 = `${opts.year.toString().padStart(4, '0')}-${String(opts.month).padStart(2, '0')}-${String(last).padStart(2, '0')}`;
  const today = new Date().toISOString().slice(0, 10);
  const staffN = db.prepare('SELECT COUNT(*) AS n FROM crm_staff WHERE active = 1').get() as
    | { n: number }
    | undefined;
  const attMonth = db
    .prepare(
      `SELECT COUNT(*) AS n FROM crm_attendance
       WHERE work_date >= ? AND work_date <= ?
         AND trim(check_in) != '' AND trim(check_out) != ''`,
    )
    .get(d0, d1) as { n: number } | undefined;
  const attToday = db
    .prepare(
      `SELECT COUNT(*) AS n FROM crm_attendance
       WHERE work_date = ? AND trim(check_in) != ''`,
    )
    .get(today) as { n: number } | undefined;
  let lateCount = 0;
  let totalHours = 0;
  const attRows = db
    .prepare(
      `SELECT work_date, check_in, check_out, break_minutes
       FROM crm_attendance WHERE work_date >= ? AND work_date <= ?`,
    )
    .all(d0, d1) as Array<Record<string, unknown>>;
  for (const r of attRows) {
    const day = analyzeAttendanceDay({
      workDate: String(r.work_date),
      checkIn: String(r.check_in ?? ''),
      checkOut: String(r.check_out ?? ''),
      breakMinutes: Number(r.break_minutes ?? 0),
      policy: opts.policy,
    });
    if (Number(day.late_minutes) > 0) lateCount++;
    totalHours += Number(day.worked_hours);
  }
  const weekdays = parseWorkWeekdays(
    workWeekdaysFromShifts(parseWeekdayShifts(opts.policy)),
  );
  const stdDays = countWorkdaysInMonth(opts.year, opts.month, weekdays);
  const stdHoursMonth = expectedStandardHoursInMonth(opts.year, opts.month, opts.policy);
  return {
    year: opts.year,
    month: opts.month,
    staff_active: Number(staffN?.n ?? 0),
    attendance_records_month: Number(attMonth?.n ?? 0),
    checked_in_today: Number(attToday?.n ?? 0),
    late_incidents_month: lateCount,
    total_hours_month: Math.round(totalHours * 10) / 10,
    workdays_standard: stdDays,
    standard_hours_month: Math.round(stdHoursMonth * 10) / 10,
    policy: policyForApi(opts.policy),
  };
}

export function weekdaysInMonth(db: DatabaseSync, year: number, month: number): number {
  const policy = loadPolicy(db);
  const weekdays = parseWorkWeekdays(String(policy.work_weekdays ?? ''));
  return countWorkdaysInMonth(year, month, weekdays);
}

export function payrollStatusLabel(raw: string | null | undefined): string {
  const s = String(raw ?? 'draft').trim().toLowerCase();
  return s === 'final' ? 'Đã khóa' : 'Nháp';
}

export function quarterLabel(year: number, month: number): string {
  const q = Math.floor((month - 1) / 3) + 1;
  return `Q${q}/${year}`;
}

export const PAYROLL_EXPORT_HEADERS = [
  'Kỳ',
  'Quý',
  'Mã NV',
  'Họ tên',
  'Ngày công',
  'Giờ làm',
  'Trễ (phút)',
  'Lương CB',
  'Lương theo giờ',
  'PC cấp bậc',
  'Thưởng',
  'Phạt trễ',
  'Tổng phụ cấp',
  'Tổng khấu trừ',
  'Thực lĩnh',
  'Trạng thái kỳ',
  'Ghi chú',
];

export const PAYROLL_EXPORT_SUMMARY_HEADERS = [
  'Mã NV',
  'Họ tên',
  'Số tháng',
  'Tổng ngày công',
  'Tổng giờ làm',
  'Tổng trễ (phút)',
  'Tổng lương theo giờ',
  'Tổng PC cấp bậc',
  'Tổng thưởng',
  'Tổng phạt trễ',
  'Tổng phụ cấp',
  'Tổng khấu trừ',
  'Tổng thực lĩnh',
];

export function payrollExportRowValues(row: Record<string, unknown>): unknown[] {
  const py = Number(row.payroll_year ?? 0);
  const pm = Number(row.payroll_month ?? 0);
  const periodLabel = py && pm ? `${String(pm).padStart(2, '0')}/${py}` : '—';
  const posAllow = Number(row.position_allowance_vnd ?? 0);
  const bonus = Number(row.bonus_vnd ?? 0);
  const lateDed = Number(row.late_deduction_vnd ?? 0);
  return [
    periodLabel,
    py && pm ? quarterLabel(py, pm) : '—',
    String(row.staff_code ?? '').trim(),
    String(row.staff_name ?? '').trim(),
    Number(row.days_present ?? 0),
    Number(row.hours_worked_total ?? 0),
    Number(row.late_minutes_total ?? 0),
    Number(row.base_salary_vnd ?? 0),
    Number(row.salary_from_attendance_vnd ?? 0),
    posAllow,
    bonus,
    lateDed,
    Number(row.allowances_vnd ?? 0),
    Number(row.deductions_vnd ?? 0),
    Number(row.net_salary_vnd ?? 0),
    payrollStatusLabel(String(row.payroll_status ?? '')),
    String(row.note ?? '').trim(),
  ];
}

export function payrollExportSummaryRows(rows: Array<Record<string, unknown>>): unknown[][] {
  const agg: Record<
    number,
    {
      staff_code: string;
      staff_name: string;
      months: Set<string>;
      days_present: number;
      hours_worked_total: number;
      late_minutes_total: number;
      salary_from_attendance_vnd: number;
      position_allowance_vnd: number;
      bonus_vnd: number;
      late_deduction_vnd: number;
      allowances_vnd: number;
      deductions_vnd: number;
      net_salary_vnd: number;
    }
  > = {};
  for (const d of rows) {
    const sid = Number(d.staff_id ?? 0);
    if (sid <= 0) continue;
    if (!agg[sid]) {
      agg[sid] = {
        staff_code: String(d.staff_code ?? '').trim(),
        staff_name: String(d.staff_name ?? '').trim(),
        months: new Set(),
        days_present: 0,
        hours_worked_total: 0,
        late_minutes_total: 0,
        salary_from_attendance_vnd: 0,
        position_allowance_vnd: 0,
        bonus_vnd: 0,
        late_deduction_vnd: 0,
        allowances_vnd: 0,
        deductions_vnd: 0,
        net_salary_vnd: 0,
      };
    }
    const a = agg[sid]!;
    const py = Number(d.payroll_year ?? 0);
    const pm = Number(d.payroll_month ?? 0);
    if (py && pm) a.months.add(`${py}-${String(pm).padStart(2, '0')}`);
    a.days_present += Number(d.days_present ?? 0);
    a.hours_worked_total += Number(d.hours_worked_total ?? 0);
    a.late_minutes_total += Number(d.late_minutes_total ?? 0);
    a.salary_from_attendance_vnd += Number(d.salary_from_attendance_vnd ?? 0);
    a.position_allowance_vnd += Number(d.position_allowance_vnd ?? 0);
    a.bonus_vnd += Number(d.bonus_vnd ?? 0);
    a.late_deduction_vnd += Number(d.late_deduction_vnd ?? 0);
    a.allowances_vnd += Number(d.allowances_vnd ?? 0);
    a.deductions_vnd += Number(d.deductions_vnd ?? 0);
    a.net_salary_vnd += Number(d.net_salary_vnd ?? 0);
  }
  return Object.keys(agg)
    .map(Number)
    .sort((a, b) => agg[a]!.staff_name.localeCompare(agg[b]!.staff_name, 'vi'))
    .map((sid) => {
      const a = agg[sid]!;
      return [
        a.staff_code,
        a.staff_name,
        a.months.size,
        a.days_present,
        Math.round(a.hours_worked_total * 100) / 100,
        a.late_minutes_total,
        a.salary_from_attendance_vnd,
        a.position_allowance_vnd,
        a.bonus_vnd,
        a.late_deduction_vnd,
        a.allowances_vnd,
        a.deductions_vnd,
        a.net_salary_vnd,
      ];
    });
}

export function payrollExportFilename(
  period: string,
  y0: number,
  m0: number,
  y1: number,
  m1: number,
): string {
  if (period === 'month') return `crm-luong-${y0}-${String(m0).padStart(2, '0')}`;
  if (period === 'quarter') {
    const q = Math.floor((m0 - 1) / 3) + 1;
    return `crm-luong-Q${q}-${y0}`;
  }
  return `crm-luong-${y0}-${String(m0).padStart(2, '0')}_${y1}-${String(m1).padStart(2, '0')}`;
}
