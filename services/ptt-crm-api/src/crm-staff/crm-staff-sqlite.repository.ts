import { Injectable, OnModuleDestroy } from '@nestjs/common';
import { DatabaseSync } from 'node:sqlite';
import { catalogTs } from '../catalog/catalog-slug.util';
import { AppConfigService } from '../config/app-config.service';
import { TERMINAL_STAGES, normalizePipelineStage } from '../sales/sales-pipeline.util';
import {
  COMPETENCY_METRIC_OPTIONS,
  DEFAULT_COMPETENCY_CONFIG,
  DEFAULT_STAFF_LEVELS,
} from './crm-staff-config.defaults';
import {
  CrmStaffRow,
  CrmStaffSummaryMeta,
  CrmStaffWorkspaceCase,
  CrmStaffWorkspaceResponse,
  PatchCrmStaffBody,
  StaffImportRow,
  staffRowForApi,
} from './crm-staff.types';

const STAFF_PIPELINE_SUB =
  "(SELECT COUNT(*) FROM crm_cases c WHERE c.assigned_staff_id = s.id AND c.status != 'dong') AS pipeline_case_count";

const STAFF_FROM = `
FROM crm_staff s
LEFT JOIN crm_departments d ON d.id = s.department_id
LEFT JOIN crm_staff mgr ON mgr.id = s.reports_to_id
LEFT JOIN crm_positions pos ON pos.id = s.position_id
`;

@Injectable()
export class CrmStaffSqliteRepository implements OnModuleDestroy {
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

  listStaff(limit = 500): { staff: CrmStaffRow[]; summary: CrmStaffSummaryMeta; meta: Record<string, number> } {
    const rows = this.database
      .prepare(
        `SELECT s.*, ${STAFF_PIPELINE_SUB},
                d.code AS dept_code, d.name AS dept_name,
                mgr.name AS reports_to_name,
                pos.name AS position_catalog_name,
                pos.code AS position_catalog_code
         ${STAFF_FROM}
         WHERE s.active = 1
         ORDER BY s.sort_order ASC, s.name COLLATE NOCASE ASC
         LIMIT ?`,
      )
      .all(limit) as unknown as Array<Record<string, unknown>>;

    const sumRow = this.database
      .prepare(
        `SELECT
           (SELECT COUNT(*) FROM crm_staff) AS staff_total,
           (SELECT COUNT(*) FROM crm_staff WHERE active = 1) AS staff_active,
           (SELECT COUNT(*) FROM crm_staff WHERE active = 0) AS staff_inactive,
           (SELECT COUNT(*) FROM crm_cases
            WHERE assigned_staff_id IS NOT NULL AND status != 'dong') AS open_assigned_cases`,
      )
      .get() as unknown as Record<string, number>;

    const staff = rows.map((r) => staffRowForApi(r));
    const total = staff.length;
    return {
      staff,
      summary: {
        staff_total: Number(sumRow.staff_total ?? 0),
        staff_active: Number(sumRow.staff_active ?? 0),
        staff_inactive: Number(sumRow.staff_inactive ?? 0),
        open_assigned_cases: Number(sumRow.open_assigned_cases ?? 0),
      },
      meta: {
        page: 1,
        per_page: Math.max(total, 1),
        total,
        total_pages: 1,
      },
    };
  }

  getStaffById(staffId: number): CrmStaffRow | null {
    const row = this.database
      .prepare(
        `SELECT s.*, ${STAFF_PIPELINE_SUB},
                d.code AS dept_code, d.name AS dept_name,
                mgr.name AS reports_to_name,
                pos.name AS position_catalog_name,
                pos.code AS position_catalog_code
         ${STAFF_FROM}
         WHERE s.id = ?`,
      )
      .get(staffId) as unknown as Record<string, unknown> | undefined;
    return row ? staffRowForApi(row) : null;
  }

  patchStaff(staffId: number, body: PatchCrmStaffBody): CrmStaffRow | null {
    const existing = this.database
      .prepare('SELECT * FROM crm_staff WHERE id = ?')
      .get(staffId) as unknown as Record<string, unknown> | undefined;
    if (!existing) return null;

    const merged: Record<string, unknown> = { ...existing };
    if ('name' in body && typeof body.name === 'string') {
      merged.name = body.name.trim().slice(0, 240);
    }
    if ('phone' in body && typeof body.phone === 'string') {
      merged.phone = body.phone.trim().slice(0, 80);
    }
    if ('email' in body && typeof body.email === 'string') {
      merged.email = body.email.trim().slice(0, 240);
    }
    if ('job_title' in body && typeof body.job_title === 'string') {
      merged.job_title = body.job_title.trim().slice(0, 200);
    }

    const ts = catalogTs();
    this.database
      .prepare(
        `UPDATE crm_staff
         SET name = ?, phone = ?, email = ?, job_title = ?, updated_at = ?
         WHERE id = ?`,
      )
      .run(
        String(merged.name ?? ''),
        String(merged.phone ?? ''),
        String(merged.email ?? ''),
        String(merged.job_title ?? ''),
        ts,
        staffId,
      );

    return this.getStaffById(staffId);
  }

  getWorkspace(staffId: number): CrmStaffWorkspaceResponse | null {
    const staffRow = this.database
      .prepare(
        'SELECT id, name, phone, email, job_title, department, active FROM crm_staff WHERE id = ?',
      )
      .get(staffId) as unknown as Record<string, unknown> | undefined;
    if (!staffRow) return null;

    const caseRows = this.database
      .prepare(
        `SELECT c.id, c.title, c.pipeline_stage, c.deal_value_vnd, c.status,
                c.assigned_staff_id, c.customer_id, c.created_at, c.updated_at,
                c.priority, c.assigned_at,
                cu.name AS customer_name, st.name AS staff_name
         FROM crm_cases c
         LEFT JOIN crm_customers cu ON cu.id = c.customer_id
         LEFT JOIN crm_staff st ON st.id = c.assigned_staff_id
         WHERE c.assigned_staff_id = ?
         ORDER BY datetime(c.updated_at) DESC
         LIMIT 200`,
      )
      .all(staffId) as unknown as Array<Record<string, unknown>>;

    const cases: CrmStaffWorkspaceCase[] = caseRows.map((r) => ({
      id: Number(r.id),
      title: String(r.title ?? ''),
      pipeline_stage: normalizePipelineStage(String(r.pipeline_stage ?? r.status ?? '')),
      deal_value_vnd: Number(r.deal_value_vnd ?? 0),
      status: String(r.status ?? ''),
      assigned_staff_id: r.assigned_staff_id != null ? Number(r.assigned_staff_id) : null,
      customer_id: r.customer_id != null ? Number(r.customer_id) : null,
      customer_name: String(r.customer_name ?? ''),
      staff_name: String(r.staff_name ?? ''),
      created_at: String(r.created_at ?? ''),
      updated_at: String(r.updated_at ?? ''),
      priority: String(r.priority ?? ''),
    }));

    const openCases = cases.filter(
      (c) => !TERMINAL_STAGES.has(normalizePipelineStage(c.pipeline_stage)),
    );
    const todayPrefix = new Date().toISOString().slice(0, 10);

    return {
      staff: {
        id: Number(staffRow.id),
        name: String(staffRow.name ?? ''),
        phone: String(staffRow.phone ?? ''),
        email: String(staffRow.email ?? ''),
        job_title: String(staffRow.job_title ?? ''),
        department: String(staffRow.department ?? ''),
        active: Number(staffRow.active ?? 0),
      },
      stats: {
        total_assigned: openCases.length,
        open: openCases.length,
        high_priority: openCases.filter((c) => c.priority === 'cao').length,
        sla_overdue: 0,
        new_today: openCases.filter((c) =>
          String(caseRows.find((r) => Number(r.id) === c.id)?.assigned_at ?? '').startsWith(
            todayPrefix,
          ),
        ).length,
        no_care_report: 0,
      },
      cases: openCases,
    };
  }

  private ensureStaffConfigSchema(): void {
    this.database.exec(`
      CREATE TABLE IF NOT EXISTS crm_staff_settings (
        config_key TEXT PRIMARY KEY,
        config_json TEXT NOT NULL DEFAULT '{}',
        updated_at TEXT NOT NULL DEFAULT '',
        updated_by TEXT NOT NULL DEFAULT ''
      )
    `);
  }

  private loadStaffConfigRaw(): Record<string, unknown> {
    this.ensureStaffConfigSchema();
    const row = this.database
      .prepare("SELECT config_json FROM crm_staff_settings WHERE config_key = 'global'")
      .get() as unknown as { config_json: string } | undefined;
    const cfg: Record<string, unknown> = {
      staff_levels: DEFAULT_STAFF_LEVELS.map((d) => ({ ...d })),
      competency: { ...DEFAULT_COMPETENCY_CONFIG },
    };
    if (row) {
      try {
        const raw = JSON.parse(String(row.config_json || '{}'));
        if (raw && typeof raw === 'object') {
          if (Array.isArray(raw.staff_levels) && raw.staff_levels.length) {
            cfg.staff_levels = raw.staff_levels;
          }
          if (raw.competency && typeof raw.competency === 'object') {
            cfg.competency = raw.competency;
          }
        }
      } catch {
        /* keep defaults */
      }
    }
    return cfg;
  }

  private saveStaffConfigPartial(partial: Record<string, unknown>): Record<string, unknown> {
    this.ensureStaffConfigSchema();
    const merged = this.loadStaffConfigRaw();
    if ('staff_levels' in partial) merged.staff_levels = partial.staff_levels;
    if ('competency' in partial) merged.competency = partial.competency;
    const ts = catalogTs();
    this.database
      .prepare(
        `INSERT INTO crm_staff_settings (config_key, config_json, updated_at, updated_by)
         VALUES ('global', ?, ?, ?)
         ON CONFLICT(config_key) DO UPDATE SET
           config_json = excluded.config_json,
           updated_at = excluded.updated_at,
           updated_by = excluded.updated_by`,
      )
      .run(JSON.stringify(merged), ts, 'nest-api');
    return merged;
  }

  getStaffLevels() {
    const cfg = this.loadStaffConfigRaw();
    return {
      staff_levels: cfg.staff_levels ?? DEFAULT_STAFF_LEVELS,
      defaults: DEFAULT_STAFF_LEVELS,
    };
  }

  saveStaffLevels(levels: Array<Record<string, unknown>>) {
    if (!Array.isArray(levels)) {
      throw new Error('INVALID_LEVELS');
    }
    const cfg = this.saveStaffConfigPartial({ staff_levels: levels });
    return { staff_levels: cfg.staff_levels ?? levels };
  }

  getCompetencyConfig() {
    const cfg = this.loadStaffConfigRaw();
    return {
      competency: cfg.competency ?? DEFAULT_COMPETENCY_CONFIG,
      defaults: DEFAULT_COMPETENCY_CONFIG,
      metric_options: COMPETENCY_METRIC_OPTIONS,
    };
  }

  saveCompetencyConfig(competency: Record<string, unknown>) {
    const cfg = this.saveStaffConfigPartial({ competency });
    return { competency: cfg.competency ?? competency };
  }

  importStaffRows(rows: StaffImportRow[]): { created: number; updated: number; skipped: number } {
    let created = 0;
    let updated = 0;
    let skipped = 0;
    const ts = catalogTs();
    const shortDate = new Date().toISOString().slice(0, 10);

    for (const row of rows) {
      const name = String(row.name ?? '').trim().slice(0, 240);
      if (!name) {
        skipped += 1;
        continue;
      }
      const internalCode = String(row.internal_code ?? '').trim().slice(0, 80);
      const email = String(row.email ?? '').trim().slice(0, 240);
      const phone = String(row.phone ?? '').trim().slice(0, 80);
      const jobTitle = String(row.job_title ?? '').trim().slice(0, 200);

      let existingId: number | null = null;
      if (internalCode) {
        const hit = this.database
          .prepare('SELECT id FROM crm_staff WHERE trim(internal_code) = ? LIMIT 1')
          .get(internalCode) as unknown as { id: number } | undefined;
        if (hit) existingId = Number(hit.id);
      }
      if (existingId == null && email) {
        const hit = this.database
          .prepare('SELECT id FROM crm_staff WHERE lower(trim(email)) = lower(?) LIMIT 1')
          .get(email) as unknown as { id: number } | undefined;
        if (hit) existingId = Number(hit.id);
      }

      if (existingId != null) {
        this.database
          .prepare(
            `UPDATE crm_staff
             SET name = ?, phone = ?, email = ?, job_title = ?, internal_code = ?, updated_at = ?
             WHERE id = ?`,
          )
          .run(name, phone, email, jobTitle, internalCode, ts, existingId);
        updated += 1;
      } else {
        this.database
          .prepare(
            `INSERT INTO crm_staff (
               name, phone, email, job_title, internal_code, active, created, updated_at, started_on
             ) VALUES (?, ?, ?, ?, ?, 1, ?, ?, ?)`,
          )
          .run(name, phone, email, jobTitle, internalCode, ts, ts, shortDate);
        created += 1;
      }
    }

    return { created, updated, skipped };
  }
}
