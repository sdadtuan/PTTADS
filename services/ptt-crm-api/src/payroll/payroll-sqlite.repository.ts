import { Injectable, OnModuleDestroy } from '@nestjs/common';
import { DatabaseSync } from 'node:sqlite';
import { catalogTs } from '../catalog/catalog-slug.util';
import { AppConfigService } from '../config/app-config.service';
import {
  computeStaffPayroll,
  dashboardSummary,
  defaultWeekdayShifts,
  enrichAttendanceRow,
  loadPolicy,
  loadPositionPayrollMap,
  normalizeWeekdayShifts,
  parseWorkWeekdays,
  payrollExportFilename,
  payrollExportRowValues,
  payrollExportSummaryRows,
  PAYROLL_EXPORT_HEADERS,
  PAYROLL_EXPORT_SUMMARY_HEADERS,
  policyForApi,
  weekdaysInMonth,
  weekdayShiftsJson,
  workWeekdaysFromShifts,
  type PolicyRecord,
  type PositionPayrollRow,
} from './payroll-engine';

function rowDict(row: Record<string, unknown>): Record<string, unknown> {
  const out: Record<string, unknown> = {};
  for (const [k, v] of Object.entries(row)) out[k] = v;
  return out;
}

function sortPositionRows(posMap: Record<number, PositionPayrollRow>): PositionPayrollRow[] {
  return Object.values(posMap).sort((a, b) => {
    const ra = Number(a.rank_level ?? 0);
    const rb = Number(b.rank_level ?? 0);
    if (ra !== rb) return ra - rb;
    return String(a.position_code ?? '').localeCompare(String(b.position_code ?? ''), 'vi');
  });
}

@Injectable()
export class PayrollSqliteRepository implements OnModuleDestroy {
  private db: DatabaseSync | null = null;

  constructor(private readonly config: AppConfigService) {}

  private get database(): DatabaseSync {
    if (!this.db) {
      this.db = new DatabaseSync(this.config.sqlitePath);
      this.db.exec('PRAGMA foreign_keys = ON');
    }
    return this.db;
  }

  onModuleDestroy(): void {
    if (this.db) {
      this.db.close();
      this.db = null;
    }
  }

  private tableExists(name: string): boolean {
    const row = this.database
      .prepare("SELECT 1 FROM sqlite_master WHERE type = 'table' AND name = ?")
      .get(name);
    return row != null;
  }

  getPolicy(): Record<string, unknown> {
    const policy = loadPolicy(this.database);
    return { policy: policyForApi(policy) };
  }

  updatePolicy(payload: Record<string, unknown>): Record<string, unknown> {
    const intField = (key: string, def: number, lo: number, hi: number): number => {
      const v = Number(payload[key] ?? def);
      if (!Number.isFinite(v)) return def;
      return Math.max(lo, Math.min(v, hi));
    };
    const floatField = (key: string, def: number, lo: number, hi: number): number => {
      const v = Number(payload[key] ?? def);
      if (!Number.isFinite(v)) return def;
      return Math.max(lo, Math.min(v, hi));
    };
    const rawShifts = payload.weekday_shifts;
    let shifts;
    if (Array.isArray(rawShifts) && rawShifts.length > 0) {
      shifts = normalizeWeekdayShifts(rawShifts);
    } else {
      const workSet = parseWorkWeekdays(String(payload.work_weekdays ?? '0,1,2,3,4'));
      shifts = defaultWeekdayShifts({
        workWeekdays: workSet,
        shiftStart: String(payload.shift_start ?? '08:30').trim().slice(0, 5),
        shiftEnd: String(payload.shift_end ?? '17:30').trim().slice(0, 5),
        breakMinutes: intField('break_minutes_default', 60, 0, 24 * 60),
        standardHours: floatField('standard_hours_per_day', 8.0, 0.5, 24.0),
      });
    }
    const weekdaysRaw = workWeekdaysFromShifts(shifts);
    const shiftsJson = weekdayShiftsJson(shifts);
    const firstWork = shifts.find((s) => s.work) ?? shifts[0]!;
    const shiftStart = String(firstWork.shift_start ?? '08:30').trim().slice(0, 5);
    const shiftEnd = String(firstWork.shift_end ?? '17:30').trim().slice(0, 5);
    const breakDefault = Math.max(0, Math.min(Number(firstWork.break_minutes ?? 60), 24 * 60));
    const stdHoursDay = Math.max(0.5, Math.min(Number(firstWork.standard_hours ?? 8), 24.0));
    let bonusMode = String(payload.bonus_mode ?? 'attendance').trim().toLowerCase();
    if (bonusMode !== 'attendance' && bonusMode !== 'none') bonusMode = 'attendance';
    const ts = catalogTs();
    loadPolicy(this.database);
    this.database
      .prepare(
        `UPDATE crm_payroll_policy SET
           work_weekdays = ?,
           shift_start = ?,
           shift_end = ?,
           break_minutes_default = ?,
           late_grace_minutes = ?,
           late_penalty_vnd_per_min = ?,
           late_penalty_max_vnd = ?,
           standard_hours_per_day = ?,
           bonus_mode = ?,
           bonus_pct = ?,
           bonus_min_days = ?,
           overtime_multiplier = ?,
           weekday_shifts = ?,
           updated_at = ?
         WHERE id = 1`,
      )
      .run(
        weekdaysRaw,
        shiftStart,
        shiftEnd,
        breakDefault,
        intField('late_grace_minutes', 5, 0, 120),
        intField('late_penalty_vnd_per_min', 5000, 0, 50_000_000),
        intField('late_penalty_max_vnd', 200_000, 0, 500_000_000),
        stdHoursDay,
        bonusMode,
        floatField('bonus_pct', 5.0, 0.0, 100.0),
        intField('bonus_min_days', 20, 0, 31),
        floatField('overtime_multiplier', 1.5, 1.0, 3.0),
        shiftsJson,
        ts,
      );
    return this.getPolicy();
  }

  getPositionRates(): { positions: PositionPayrollRow[] } {
    const posMap = loadPositionPayrollMap(this.database);
    return { positions: sortPositionRows(posMap) };
  }

  updatePositionRates(items: unknown[]): { positions: PositionPayrollRow[] } {
    loadPolicy(this.database);
    const ts = catalogTs();
    for (const item of items) {
      if (!item || typeof item !== 'object') continue;
      const rec = item as Record<string, unknown>;
      const pid = Number(rec.position_id ?? 0);
      if (!Number.isFinite(pid) || pid <= 0) continue;
      const posExists = this.database.prepare('SELECT id FROM crm_positions WHERE id = ?').get(pid);
      if (!posExists) continue;
      let rank = Number(rec.rank_level ?? 1);
      if (!Number.isFinite(rank)) rank = 1;
      rank = Math.max(1, Math.min(rank, 99));
      let allow = Number(rec.allowance_vnd ?? 0);
      if (!Number.isFinite(allow)) allow = 0;
      allow = Math.max(0, Math.min(allow, 999_999_999));
      let bp = Number(rec.bonus_pct ?? 0);
      if (!Number.isFinite(bp)) bp = 0;
      bp = Math.max(0, Math.min(bp, 100.0));
      this.database
        .prepare(
          `INSERT INTO crm_position_payroll (position_id, rank_level, allowance_vnd, bonus_pct, updated_at)
           VALUES (?, ?, ?, ?, ?)
           ON CONFLICT(position_id) DO UPDATE SET
             rank_level = excluded.rank_level,
             allowance_vnd = excluded.allowance_vnd,
             bonus_pct = excluded.bonus_pct,
             updated_at = excluded.updated_at`,
        )
        .run(pid, rank, allow, bp, ts);
    }
    return this.getPositionRates();
  }

  fetchDashboard(year: number, month: number): Record<string, unknown> {
    if (!this.tableExists('crm_staff')) {
      const policy = loadPolicy(this.database);
      return {
        ...dashboardSummary(this.database, { year, month, policy }),
        position_rates: [],
      };
    }
    const policy = loadPolicy(this.database);
    const summary = dashboardSummary(this.database, { year, month, policy });
    const posMap = loadPositionPayrollMap(this.database);
    return { ...summary, position_rates: sortPositionRows(posMap) };
  }

  getPayroll(year: number, month: number): { payroll: Record<string, unknown> | null; lines: Record<string, unknown>[] } {
    if (!this.tableExists('crm_payroll')) {
      return { payroll: null, lines: [] };
    }
    const pr = this.database
      .prepare('SELECT * FROM crm_payroll WHERE year = ? AND month = ?')
      .get(year, month) as Record<string, unknown> | undefined;
    if (!pr) return { payroll: null, lines: [] };
    const lines = this.database
      .prepare(
        `SELECT pl.*, s.name AS staff_name, s.internal_code AS staff_code
         FROM crm_payroll_line pl
         JOIN crm_staff s ON s.id = pl.staff_id
         WHERE pl.payroll_id = ?
         ORDER BY s.name COLLATE NOCASE ASC`,
      )
      .all(Number(pr.id)) as Array<Record<string, unknown>>;
    return { payroll: rowDict(pr), lines: lines.map(rowDict) };
  }

  computePayroll(year: number, month: number): { payroll: Record<string, unknown>; lines: Record<string, unknown>[] } {
    const standard = weekdaysInMonth(this.database, year, month);
    const ts = catalogTs();
    const prev = this.database
      .prepare('SELECT * FROM crm_payroll WHERE year = ? AND month = ?')
      .get(year, month) as Record<string, unknown> | undefined;
    if (prev != null && String(prev.status ?? '').trim() === 'final') {
      throw new Error('PAYROLL_LOCKED');
    }
    let prRow: Record<string, unknown>;
    if (prev == null) {
      this.database
        .prepare(
          `INSERT INTO crm_payroll (year, month, workdays_standard, status, created_at, updated_at)
           VALUES (?, ?, ?, 'draft', ?, ?)`,
        )
        .run(year, month, standard, ts, ts);
      prRow = this.database
        .prepare('SELECT * FROM crm_payroll WHERE year = ? AND month = ?')
        .get(year, month) as Record<string, unknown>;
    } else {
      this.database
        .prepare('UPDATE crm_payroll SET workdays_standard = ?, updated_at = ? WHERE id = ?')
        .run(standard, ts, Number(prev.id));
      prRow = this.database
        .prepare('SELECT * FROM crm_payroll WHERE id = ?')
        .get(Number(prev.id)) as Record<string, unknown>;
    }
    const pid = Number(prRow.id);
    const policy = loadPolicy(this.database);
    const positionMap = loadPositionPayrollMap(this.database);
    const staffRows = this.database
      .prepare(
        `SELECT id, name, base_salary_vnd, position_id
         FROM crm_staff WHERE active = 1 ORDER BY name COLLATE NOCASE`,
      )
      .all() as Array<Record<string, unknown>>;
    for (const sr of staffRows) {
      const stId = Number(sr.id);
      const base = Number(sr.base_salary_vnd ?? 0);
      const posId = sr.position_id != null ? Number(sr.position_id) : null;
      const computed = computeStaffPayroll(this.database, {
        staffId: stId,
        baseSalaryVnd: base,
        positionId: posId,
        year,
        month,
        policy,
        positionMap,
      });
      const existing = this.database
        .prepare(
          `SELECT id, allowances_vnd, deductions_vnd, note,
                  position_allowance_vnd, bonus_vnd, late_deduction_vnd
           FROM crm_payroll_line WHERE payroll_id = ? AND staff_id = ?`,
        )
        .get(pid, stId) as Record<string, unknown> | undefined;
      const autoAllow =
        Number(computed.position_allowance_vnd) + Number(computed.bonus_vnd);
      const autoDed = Number(computed.late_deduction_vnd);
      let manualAllow = 0;
      let manualDed = 0;
      let note = '';
      if (existing) {
        note = String(existing.note ?? '');
        const prevAutoAllow =
          Number(existing.position_allowance_vnd ?? 0) + Number(existing.bonus_vnd ?? 0);
        const prevAutoDed = Number(existing.late_deduction_vnd ?? 0);
        manualAllow = Math.max(0, Number(existing.allowances_vnd ?? 0) - prevAutoAllow);
        manualDed = Math.max(0, Number(existing.deductions_vnd ?? 0) - prevAutoDed);
      }
      const allow = autoAllow + manualAllow;
      const ded = autoDed + manualDed;
      const salaryAtt = Number(computed.salary_from_attendance_vnd);
      const net = salaryAtt + allow - ded;
      const days = Number(computed.days_present);
      if (existing) {
        this.database
          .prepare(
            `UPDATE crm_payroll_line SET
               days_present = ?, base_salary_vnd = ?, salary_from_attendance_vnd = ?,
               hours_worked_total = ?, late_minutes_total = ?, late_deduction_vnd = ?,
               position_allowance_vnd = ?, bonus_vnd = ?,
               allowances_vnd = ?, deductions_vnd = ?, net_salary_vnd = ?, updated_at = ?
             WHERE id = ?`,
          )
          .run(
            days,
            base,
            salaryAtt,
            Number(computed.hours_worked_total),
            Number(computed.late_minutes_total),
            Number(computed.late_deduction_vnd),
            Number(computed.position_allowance_vnd),
            Number(computed.bonus_vnd),
            allow,
            ded,
            net,
            ts,
            Number(existing.id),
          );
      } else {
        this.database
          .prepare(
            `INSERT INTO crm_payroll_line (
               payroll_id, staff_id, days_present, base_salary_vnd,
               salary_from_attendance_vnd, hours_worked_total, late_minutes_total,
               late_deduction_vnd, position_allowance_vnd, bonus_vnd,
               allowances_vnd, deductions_vnd, net_salary_vnd,
               note, created_at, updated_at
             ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)`,
          )
          .run(
            pid,
            stId,
            days,
            base,
            salaryAtt,
            Number(computed.hours_worked_total),
            Number(computed.late_minutes_total),
            Number(computed.late_deduction_vnd),
            Number(computed.position_allowance_vnd),
            Number(computed.bonus_vnd),
            allow,
            ded,
            net,
            note,
            ts,
            ts,
          );
      }
    }
    return this.getPayroll(year, month) as {
      payroll: Record<string, unknown>;
      lines: Record<string, unknown>[];
    };
  }

  patchPayroll(payrollId: number, payload: Record<string, unknown>): Record<string, unknown> | null {
    const row = this.database
      .prepare('SELECT * FROM crm_payroll WHERE id = ?')
      .get(payrollId) as Record<string, unknown> | undefined;
    if (!row) return null;
    let status = String(row.status ?? 'draft');
    if ('status' in payload) {
      const s = String(payload.status ?? '').trim().toLowerCase();
      if (s === 'draft' || s === 'final') status = s;
    }
    const ts = catalogTs();
    this.database
      .prepare('UPDATE crm_payroll SET status = ?, updated_at = ? WHERE id = ?')
      .run(status, ts, payrollId);
    const row2 = this.database
      .prepare('SELECT * FROM crm_payroll WHERE id = ?')
      .get(payrollId) as Record<string, unknown> | undefined;
    return row2 ? rowDict(row2) : null;
  }

  patchPayrollLine(
    lineId: number,
    payload: Record<string, unknown>,
  ): Record<string, unknown> | null {
    const line = this.database
      .prepare('SELECT * FROM crm_payroll_line WHERE id = ?')
      .get(lineId) as Record<string, unknown> | undefined;
    if (!line) return null;
    const pr = this.database
      .prepare('SELECT * FROM crm_payroll WHERE id = ?')
      .get(Number(line.payroll_id)) as Record<string, unknown> | undefined;
    if (pr != null && String(pr.status ?? '').trim() === 'final') {
      throw new Error('PAYROLL_LOCKED');
    }
    let allow = Number(line.allowances_vnd ?? 0);
    let ded = Number(line.deductions_vnd ?? 0);
    let note = String(line.note ?? '');
    if ('allowances_vnd' in payload) {
      const v = Number(payload.allowances_vnd);
      if (Number.isFinite(v)) allow = Math.max(0, Math.min(v, 9_999_999_999));
    }
    if ('deductions_vnd' in payload) {
      const v = Number(payload.deductions_vnd);
      if (Number.isFinite(v)) ded = Math.max(0, Math.min(v, 9_999_999_999));
    }
    if ('note' in payload && typeof payload.note === 'string') {
      note = payload.note.trim().slice(0, 2000);
    }
    const sat = Number(line.salary_from_attendance_vnd ?? 0);
    const net = sat + allow - ded;
    const ts = catalogTs();
    this.database
      .prepare(
        `UPDATE crm_payroll_line
         SET allowances_vnd = ?, deductions_vnd = ?, net_salary_vnd = ?, note = ?, updated_at = ?
         WHERE id = ?`,
      )
      .run(allow, ded, net, note, ts, lineId);
    const row2 = this.database
      .prepare(
        `SELECT pl.*, s.name AS staff_name, s.internal_code AS staff_code
         FROM crm_payroll_line pl
         JOIN crm_staff s ON s.id = pl.staff_id
         WHERE pl.id = ?`,
      )
      .get(lineId) as Record<string, unknown> | undefined;
    return row2 ? rowDict(row2) : null;
  }

  private findStaffIdsByQuery(query: string): number[] {
    const q = String(query ?? '').trim();
    if (!q) {
      const rows = this.database
        .prepare('SELECT id FROM crm_staff WHERE active = 1')
        .all() as Array<{ id: number }>;
      return rows.map((r) => Number(r.id));
    }
    const like = `%${q}%`;
    const rows = this.database
      .prepare(
        `SELECT id FROM crm_staff WHERE active = 1 AND (
           name LIKE ? COLLATE NOCASE OR
           internal_code LIKE ? COLLATE NOCASE OR
           attendance_pin LIKE ?
         )`,
      )
      .all(like, like, like) as Array<{ id: number }>;
    return rows.map((r) => Number(r.id));
  }

  fetchExportRows(opts: {
    y0: number;
    m0: number;
    y1: number;
    m1: number;
    staffId?: number;
    staffQ?: string;
  }): Record<string, unknown>[] {
    if (!this.tableExists('crm_payroll') || !this.tableExists('crm_payroll_line')) {
      return [];
    }
    const clauses = [
      '(p.year > ? OR (p.year = ? AND p.month >= ?))',
      '(p.year < ? OR (p.year = ? AND p.month <= ?))',
    ];
    const params: (string | number)[] = [opts.y0, opts.y0, opts.m0, opts.y1, opts.y1, opts.m1];
    if (opts.staffId != null) {
      clauses.push('pl.staff_id = ?');
      params.push(opts.staffId);
    } else if (opts.staffQ) {
      const staffIds = this.findStaffIdsByQuery(opts.staffQ);
      if (staffIds.length === 0) return [];
      clauses.push(`pl.staff_id IN (${staffIds.map(() => '?').join(',')})`);
      params.push(...staffIds);
    }
    const whereSql = clauses.join(' AND ');
    const rows = this.database
      .prepare(
        `SELECT pl.*,
                s.name AS staff_name, s.internal_code AS staff_code,
                p.year AS payroll_year, p.month AS payroll_month,
                p.status AS payroll_status, p.workdays_standard
         FROM crm_payroll_line pl
         JOIN crm_payroll p ON p.id = pl.payroll_id
         JOIN crm_staff s ON s.id = pl.staff_id
         WHERE ${whereSql}
         ORDER BY p.year ASC, p.month ASC, s.name COLLATE NOCASE ASC`,
      )
      .all(...params) as Array<Record<string, unknown>>;
    return rows.map(rowDict);
  }

  exportPayrollBundle(opts: {
    period: string;
    y0: number;
    m0: number;
    y1: number;
    m1: number;
    staffId?: number;
    staffQ?: string;
  }): Record<string, unknown> {
    const rows = this.fetchExportRows(opts);
    const includeSummary =
      opts.period === 'quarter' ||
      opts.period === 'range' ||
      opts.y0 !== opts.y1 ||
      opts.m0 !== opts.m1;
    const filename = payrollExportFilename(opts.period, opts.y0, opts.m0, opts.y1, opts.m1);
    return {
      period: opts.period,
      from: { year: opts.y0, month: opts.m0 },
      to: { year: opts.y1, month: opts.m1 },
      filename,
      headers: PAYROLL_EXPORT_HEADERS,
      rows: rows.map(payrollExportRowValues),
      include_summary: includeSummary,
      summary_headers: PAYROLL_EXPORT_SUMMARY_HEADERS,
      summary_rows: includeSummary && rows.length > 0 ? payrollExportSummaryRows(rows) : [],
      row_count: rows.length,
    };
  }

  listAttendance(opts: {
    staffId?: number;
    dateFrom?: string;
    dateTo?: string;
  }): { attendance: Record<string, unknown>[] } {
    if (!this.tableExists('crm_attendance')) {
      return { attendance: [] };
    }
    const clauses: string[] = [];
    const params: (string | number)[] = [];
    if (opts.staffId != null) {
      clauses.push('a.staff_id = ?');
      params.push(opts.staffId);
    }
    if (opts.dateFrom) {
      clauses.push('a.work_date >= ?');
      params.push(opts.dateFrom);
    }
    if (opts.dateTo) {
      clauses.push('a.work_date <= ?');
      params.push(opts.dateTo);
    }
    const whereSql = clauses.length > 0 ? ` WHERE ${clauses.join(' AND ')}` : '';
    const rows = this.database
      .prepare(
        `SELECT a.*, s.name AS staff_name, s.internal_code AS staff_code
         FROM crm_attendance a
         JOIN crm_staff s ON s.id = a.staff_id
         ${whereSql}
         ORDER BY a.work_date DESC, s.name COLLATE NOCASE ASC`,
      )
      .all(...params) as Array<Record<string, unknown>>;
    const policy = loadPolicy(this.database);
    return {
      attendance: rows.map((r) => enrichAttendanceRow(rowDict(r), policy)),
    };
  }
}
