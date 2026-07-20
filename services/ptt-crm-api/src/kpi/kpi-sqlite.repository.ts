import { Injectable, OnModuleDestroy } from '@nestjs/common';
import { DatabaseSync } from 'node:sqlite';
import { catalogTs } from '../catalog/catalog-slug.util';
import { AppConfigService } from '../config/app-config.service';
import {
  CreateKpiMetricBody,
  KpiMetricRow,
  PatchKpiMetricBody,
  PatchStaffKpiProgressBody,
  StaffKpiEntryRow,
  StaffKpiMetricItem,
  StaffKpiMetricsResponse,
  deriveKpiAlert,
  kpiAchievementPct,
  kpiAlertLabelVi,
  truthyFlag,
} from './kpi.types';

@Injectable()
export class KpiSqliteRepository implements OnModuleDestroy {
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

  listMetrics(includeInactive: boolean): KpiMetricRow[] {
    const sql = includeInactive
      ? `SELECT * FROM crm_kpi_metrics
         ORDER BY active DESC, sort_order ASC, name COLLATE NOCASE ASC`
      : `SELECT * FROM crm_kpi_metrics
         WHERE active = 1
         ORDER BY sort_order ASC, name COLLATE NOCASE ASC`;
    const rows = this.database.prepare(sql).all() as unknown as Array<Record<string, unknown>>;
    return rows.map((r) => this.mapMetricRow(r));
  }

  getMetricById(metricId: number): KpiMetricRow | null {
    const row = this.database
      .prepare('SELECT * FROM crm_kpi_metrics WHERE id = ?')
      .get(metricId) as unknown as Record<string, unknown> | undefined;
    return row ? this.mapMetricRow(row) : null;
  }

  createMetric(body: CreateKpiMetricBody): KpiMetricRow {
    const code = String(body.code ?? '').trim().slice(0, 64);
    const name = String(body.name ?? '').trim().slice(0, 240);
    const unit = String(body.unit ?? '').trim().slice(0, 64);
    const desc = String(body.description ?? '').trim().slice(0, 2000);
    let sortOrder = Number(body.sort_order ?? 0);
    if (!Number.isFinite(sortOrder)) sortOrder = 0;
    const hi = truthyFlag(body.higher_is_better) ? 1 : 0;
    let warnRatio: number | null = null;
    if (body.warn_ratio != null) {
      const wr = Number(body.warn_ratio);
      if (Number.isFinite(wr)) warnRatio = wr;
    }

    if (code) {
      const dup = this.database
        .prepare(
          `SELECT 1 FROM crm_kpi_metrics
           WHERE lower(trim(code)) = lower(?) AND trim(code) != ''`,
        )
        .get(code);
      if (dup) throw new Error('DUPLICATE_CODE');
    }

    const tsDate = new Date().toISOString().slice(0, 10);
    const ts = catalogTs();
    const result = this.database
      .prepare(
        `INSERT INTO crm_kpi_metrics (
           code, name, unit, description, sort_order, active,
           created_at, updated_at, higher_is_better, warn_ratio
         ) VALUES (?, ?, ?, ?, ?, 1, ?, ?, ?, ?)`,
      )
      .run(code, name, unit, desc, sortOrder, tsDate, ts, hi, warnRatio);

    const metric = this.getMetricById(Number(result.lastInsertRowid));
    if (!metric) throw new Error('Failed to create KPI metric');
    return metric;
  }

  patchMetric(metricId: number, body: PatchKpiMetricBody): KpiMetricRow | null {
    const existing = this.database
      .prepare('SELECT * FROM crm_kpi_metrics WHERE id = ?')
      .get(metricId) as unknown as Record<string, unknown> | undefined;
    if (!existing) return null;

    const merged: Record<string, unknown> = { ...existing };
    if ('code' in body && typeof body.code === 'string') {
      merged.code = body.code.trim().slice(0, 64);
    }
    if ('name' in body && typeof body.name === 'string') {
      merged.name = body.name.trim().slice(0, 240);
    }
    if ('unit' in body && typeof body.unit === 'string') {
      merged.unit = body.unit.trim().slice(0, 64);
    }
    if ('description' in body && typeof body.description === 'string') {
      merged.description = body.description.trim().slice(0, 2000);
    }
    if ('sort_order' in body && body.sort_order != null) {
      const so = Number(body.sort_order);
      if (Number.isFinite(so)) merged.sort_order = so;
    }
    if ('active' in body) {
      merged.active = truthyFlag(body.active) ? 1 : 0;
    }
    if ('higher_is_better' in body) {
      merged.higher_is_better = truthyFlag(body.higher_is_better) ? 1 : 0;
    }
    if ('warn_ratio' in body) {
      const wrv = body.warn_ratio;
      if (wrv == null) {
        merged.warn_ratio = null;
      } else {
        const wr = Number(wrv);
        merged.warn_ratio = Number.isFinite(wr) ? wr : merged.warn_ratio;
      }
    }

    const code = String(merged.code ?? '').trim();
    if (code) {
      const dup = this.database
        .prepare(
          `SELECT 1 FROM crm_kpi_metrics
           WHERE lower(trim(code)) = lower(?) AND trim(code) != '' AND id != ?`,
        )
        .get(code, metricId);
      if (dup) throw new Error('DUPLICATE_CODE');
    }

    const ts = catalogTs();
    this.database
      .prepare(
        `UPDATE crm_kpi_metrics
         SET code = ?, name = ?, unit = ?, description = ?, sort_order = ?, active = ?,
             higher_is_better = ?, warn_ratio = ?, updated_at = ?
         WHERE id = ?`,
      )
      .run(
        String(merged.code ?? ''),
        String(merged.name ?? ''),
        String(merged.unit ?? ''),
        String(merged.description ?? ''),
        Number(merged.sort_order ?? 0),
        Number(merged.active ?? 1),
        Number(merged.higher_is_better ?? 1),
        merged.warn_ratio != null ? Number(merged.warn_ratio) : null,
        ts,
        metricId,
      );

    return this.getMetricById(metricId);
  }

  listStaffKpi(year: number, month: number, staffId?: number): StaffKpiEntryRow[] {
    const clauses = ['k.year = ?', 'k.month = ?'];
    const params: (string | number)[] = [year, month];
    if (staffId != null) {
      clauses.push('k.staff_id = ?');
      params.push(staffId);
    }
    const whereSql = clauses.join(' AND ');
    const rows = this.database
      .prepare(
        `SELECT k.*,
                m.name AS metric_name, m.code AS metric_code, m.unit AS metric_unit,
                m.higher_is_better AS metric_higher_is_better,
                m.warn_ratio AS metric_warn_ratio,
                s.name AS staff_name, s.internal_code AS staff_code
         FROM crm_staff_kpi k
         JOIN crm_kpi_metrics m ON m.id = k.metric_id
         JOIN crm_staff s ON s.id = k.staff_id
         WHERE ${whereSql}
         ORDER BY s.name COLLATE NOCASE ASC, m.sort_order ASC, m.name COLLATE NOCASE ASC`,
      )
      .all(...params) as unknown as Array<Record<string, unknown>>;
    return rows.map((r) => this.mapStaffKpiRow(r));
  }

  staffExists(staffId: number): boolean {
    const row = this.database
      .prepare('SELECT id FROM crm_staff WHERE id = ?')
      .get(staffId) as unknown as { id: number } | undefined;
    return row != null;
  }

  computeStaffRoleMetrics(
    staffId: number,
    role: string,
    year: number,
    month: number,
  ): StaffKpiMetricsResponse {
    const monthPrefix = `${year}-${String(month).padStart(2, '0')}`;
    const metrics: StaffKpiMetricItem[] = [];

    if (role === 'am') {
      const leadsRow = this.database
        .prepare(
          `SELECT COUNT(*) AS n FROM crm_leads
           WHERE owner_id = ? AND created_at LIKE ?`,
        )
        .get(staffId, `${monthPrefix}%`) as unknown as { n: number };
      const lcRow = this.database
        .prepare(
          `SELECT COUNT(*) AS n FROM crm_service_lifecycle
           WHERE assigned_am = ? AND created_at LIKE ?`,
        )
        .get(staffId, `${monthPrefix}%`) as unknown as { n: number };
      const casesRow = this.database
        .prepare(
          `SELECT COUNT(*) AS n FROM crm_cases
           WHERE assigned_staff_id = ? AND created_at LIKE ?`,
        )
        .get(staffId, `${monthPrefix}%`) as unknown as { n: number };

      metrics.push(
        { key: 'leads_owned', label: 'Lead phụ trách', value: Number(leadsRow?.n ?? 0), target: null },
        { key: 'lifecycles', label: 'Lifecycle AM', value: Number(lcRow?.n ?? 0), target: null },
        { key: 'cases', label: 'Hồ sơ phụ trách', value: Number(casesRow?.n ?? 0), target: null },
      );
    } else {
      const lcRow = this.database
        .prepare(
          `SELECT COUNT(*) AS n FROM crm_service_lifecycle
           WHERE assigned_sp = ? AND created_at LIKE ?`,
        )
        .get(staffId, `${monthPrefix}%`) as unknown as { n: number };
      const tasksRow = this.database
        .prepare(
          `SELECT COUNT(*) AS n FROM crm_svc_tasks
           WHERE done_by = ? AND is_done = 1 AND updated_at LIKE ?`,
        )
        .get(staffId, `${monthPrefix}%`) as unknown as { n: number };
      const casesRow = this.database
        .prepare(
          `SELECT COUNT(*) AS n FROM crm_cases
           WHERE assigned_staff_id = ? AND created_at LIKE ?`,
        )
        .get(staffId, `${monthPrefix}%`) as unknown as { n: number };

      metrics.push(
        { key: 'lifecycles', label: 'Lifecycle SP', value: Number(lcRow?.n ?? 0), target: null },
        { key: 'tasks_done', label: 'Task hoàn thành', value: Number(tasksRow?.n ?? 0), target: null },
        { key: 'cases', label: 'Hồ sơ liên quan', value: Number(casesRow?.n ?? 0), target: null },
      );
    }

    return { staff_id: staffId, role, year, month, metrics };
  }

  listKpiAlerts(year: number, month: number, staffId?: number) {
    const rows = this.listStaffKpi(year, month, staffId);
    const alerts: Array<Record<string, unknown>> = [];
    let crit = 0;
    let wrn = 0;
    for (const row of rows) {
      const { level, reason } = deriveKpiAlert(
        row.status,
        row.metric_higher_is_better,
        row.metric_warn_ratio,
        row.target_value,
        row.actual_value,
      );
      if (!level) continue;
      if (level === 'critical') crit += 1;
      else if (level === 'warn') wrn += 1;
      alerts.push({
        level,
        reason,
        message: kpiAlertLabelVi(level, reason),
        kpi_id: row.id,
        staff_id: row.staff_id,
        staff_name: row.staff_name,
        staff_code: row.staff_code,
        metric_id: row.metric_id,
        metric_name: row.metric_name,
        metric_code: row.metric_code,
        target_value: row.target_value,
        actual_value: row.actual_value,
        status: row.status,
      });
    }
    return { alerts, summary: { critical: crit, warn: wrn }, year, month };
  }

  fetchKpiChart(metricId: number, year: number, month: number, staffId?: number) {
    const metric = this.getMetricById(metricId);
    if (!metric) return null;
    const clauses = ['k.year = ?', 'k.month = ?', 'k.metric_id = ?'];
    const params: (string | number)[] = [year, month, metricId];
    if (staffId != null) {
      clauses.push('k.staff_id = ?');
      params.push(staffId);
    }
    const rows = this.database
      .prepare(
        `SELECT k.*, s.name AS staff_name, s.internal_code AS staff_code
         FROM crm_staff_kpi k
         JOIN crm_staff s ON s.id = k.staff_id
         WHERE ${clauses.join(' AND ')}
         ORDER BY s.name COLLATE NOCASE ASC`,
      )
      .all(...params) as unknown as Array<Record<string, unknown>>;

    const labels: string[] = [];
    const achievementPct: Array<number | null> = [];
    const staffIds: number[] = [];
    const hi = metric.higher_is_better;
    for (const r of rows) {
      const sid = Number(r.staff_id);
      const sn = String(r.staff_name ?? '').trim();
      const sc = String(r.staff_code ?? '').trim();
      labels.push(sc ? `${sn} (${sc})` : sn);
      staffIds.push(sid);
      achievementPct.push(kpiAchievementPct(hi, r.target_value, r.actual_value));
    }

    return {
      metric: metric as unknown as Record<string, unknown>,
      higher_is_better: hi,
      year,
      month,
      labels,
      achievement_pct: achievementPct,
      staff_ids: staffIds,
    };
  }

  getStaffKpiById(kpiId: number): StaffKpiEntryRow | null {
    const row = this.database
      .prepare(
        `SELECT k.*,
                m.name AS metric_name, m.code AS metric_code, m.unit AS metric_unit,
                m.higher_is_better AS metric_higher_is_better,
                m.warn_ratio AS metric_warn_ratio,
                s.name AS staff_name, s.internal_code AS staff_code
         FROM crm_staff_kpi k
         JOIN crm_kpi_metrics m ON m.id = k.metric_id
         JOIN crm_staff s ON s.id = k.staff_id
         WHERE k.id = ?`,
      )
      .get(kpiId) as unknown as Record<string, unknown> | undefined;
    return row ? this.mapStaffKpiRow(row) : null;
  }

  patchStaffKpiProgress(
    kpiId: number,
    body: PatchStaffKpiProgressBody,
  ): StaffKpiEntryRow | null {
    const existing = this.database
      .prepare('SELECT * FROM crm_staff_kpi WHERE id = ?')
      .get(kpiId) as unknown as Record<string, unknown> | undefined;
    if (!existing) return null;

    const merged: Record<string, unknown> = { ...existing };
    if ('actual_value' in body) {
      const av = body.actual_value;
      merged.actual_value =
        av == null || av === ('' as unknown)
          ? null
          : Number.isFinite(Number(av))
            ? Number(av)
            : merged.actual_value;
    }
    if ('status' in body && body.status != null) {
      merged.status = String(body.status).trim().slice(0, 32);
    }
    if ('note' in body && typeof body.note === 'string') {
      merged.note = body.note.trim().slice(0, 2000);
    }

    const ts = catalogTs();
    this.database
      .prepare(
        `UPDATE crm_staff_kpi
         SET actual_value = ?, status = ?, note = ?, updated_at = ?
         WHERE id = ?`,
      )
      .run(
        merged.actual_value != null ? Number(merged.actual_value) : null,
        String(merged.status ?? 'draft'),
        String(merged.note ?? ''),
        ts,
        kpiId,
      );

    return this.getStaffKpiById(kpiId);
  }

  exportStaffKpi(year: number, month: number, staffId?: number) {
    return {
      staff_kpi: this.listStaffKpi(year, month, staffId),
      year,
      month,
    };
  }

  private mapMetricRow(row: Record<string, unknown>): KpiMetricRow {
    return {
      id: Number(row.id),
      code: String(row.code ?? ''),
      name: String(row.name ?? ''),
      unit: String(row.unit ?? ''),
      description: String(row.description ?? ''),
      sort_order: Number(row.sort_order ?? 0),
      active: Number(row.active ?? 1),
      higher_is_better: Number(row.higher_is_better ?? 1),
      warn_ratio: row.warn_ratio != null ? Number(row.warn_ratio) : null,
      created_at: String(row.created_at ?? ''),
      updated_at: String(row.updated_at ?? ''),
    };
  }

  private mapStaffKpiRow(row: Record<string, unknown>): StaffKpiEntryRow {
    return {
      id: Number(row.id),
      staff_id: Number(row.staff_id),
      metric_id: Number(row.metric_id),
      year: Number(row.year),
      month: Number(row.month),
      target_value: row.target_value != null ? Number(row.target_value) : null,
      actual_value: row.actual_value != null ? Number(row.actual_value) : null,
      status: String(row.status ?? ''),
      note: String(row.note ?? ''),
      created_at: String(row.created_at ?? ''),
      updated_at: String(row.updated_at ?? ''),
      metric_name: String(row.metric_name ?? ''),
      metric_code: String(row.metric_code ?? ''),
      metric_unit: String(row.metric_unit ?? ''),
      metric_higher_is_better: Number(row.metric_higher_is_better ?? 1),
      metric_warn_ratio: row.metric_warn_ratio != null ? Number(row.metric_warn_ratio) : null,
      staff_name: String(row.staff_name ?? ''),
      staff_code: String(row.staff_code ?? ''),
    };
  }
}
