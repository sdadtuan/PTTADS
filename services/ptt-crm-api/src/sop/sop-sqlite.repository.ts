import { Injectable, OnModuleDestroy } from '@nestjs/common';
import { DatabaseSync } from 'node:sqlite';
import { catalogTs } from '../catalog/catalog-slug.util';
import { AppConfigService } from '../config/app-config.service';
import {
  addDaysIso,
  CreateSopRunBody,
  CRM_SOP_RUN_STATUSES,
  isValidDateYmd,
  normalizeSopRunStatus,
  SopRunRow,
  SopRunStats,
  SopRunTaskRow,
  SopStepRow,
  SopTemplateRow,
} from './sop.types';

const RUN_SELECT = `
SELECT r.*, t.name AS template_name, t.channel AS template_channel,
       c.name AS campaign_name, c.code AS campaign_code
FROM crm_sop_runs r
LEFT JOIN crm_sop_templates t ON t.id = r.template_id
LEFT JOIN crm_campaigns c ON c.id = r.campaign_id
`;

@Injectable()
export class SopSqliteRepository implements OnModuleDestroy {
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

  listTemplates(includeInactive: boolean): SopTemplateRow[] {
    const rows = includeInactive
      ? (this.database
          .prepare(
            'SELECT * FROM crm_sop_templates ORDER BY active DESC, name COLLATE NOCASE ASC',
          )
          .all() as unknown as Array<Record<string, unknown>>)
      : (this.database
          .prepare(
            'SELECT * FROM crm_sop_templates WHERE active = 1 ORDER BY name COLLATE NOCASE ASC',
          )
          .all() as unknown as Array<Record<string, unknown>>);
    return rows.map((r) => this.mapTemplateRow(r));
  }

  getTemplateById(id: number): SopTemplateRow | null {
    const row = this.database
      .prepare('SELECT * FROM crm_sop_templates WHERE id = ?')
      .get(id) as unknown as Record<string, unknown> | undefined;
    return row ? this.mapTemplateRow(row) : null;
  }

  getTemplateByCode(code: string): SopTemplateRow | null {
    const row = this.database
      .prepare('SELECT * FROM crm_sop_templates WHERE code = ? AND active = 1 ORDER BY id DESC LIMIT 1')
      .get(code) as unknown as Record<string, unknown> | undefined;
    return row ? this.mapTemplateRow(row) : null;
  }

  listSteps(templateId: number): SopStepRow[] {
    const rows = this.database
      .prepare(
        `SELECT * FROM crm_sop_steps
         WHERE template_id = ?
         ORDER BY position ASC, id ASC`,
      )
      .all(templateId) as unknown as Array<Record<string, unknown>>;
    return rows.map((r) => this.mapStepRow(r));
  }

  listRuns(statusFilter: string): SopRunRow[] {
    let rows: Array<Record<string, unknown>>;
    if (statusFilter === 'all') {
      rows = this.database
        .prepare(
          `${RUN_SELECT}
           ORDER BY datetime(r.updated_at) DESC, r.id DESC
           LIMIT 300`,
        )
        .all() as unknown as Array<Record<string, unknown>>;
    } else {
      rows = this.database
        .prepare(
          `${RUN_SELECT}
           WHERE r.status = ?
           ORDER BY r.start_date ASC, r.id ASC
           LIMIT 300`,
        )
        .all(statusFilter) as unknown as Array<Record<string, unknown>>;
    }
    return rows.map((r) => this.mapRunRow(r));
  }

  createRun(body: CreateSopRunBody, generateTasks = true): SopRunRow {
    const name = String(body.name ?? '').trim().slice(0, 400);
    const startDate = String(body.start_date ?? '').trim().slice(0, 32);
    const notes = String(body.notes ?? '').trim().slice(0, 8000);
    const status = normalizeSopRunStatus(body.status);

    let campaignId: number | null = null;
    if (body.campaign_id != null && body.campaign_id !== 0) {
      const cid = Number(body.campaign_id);
      if (Number.isFinite(cid) && cid > 0) campaignId = cid;
    }
    let templateId: number | null = null;
    if (body.template_id != null && body.template_id !== 0) {
      const tid = Number(body.template_id);
      if (Number.isFinite(tid) && tid > 0) templateId = tid;
    }

    const tsDate = new Date().toISOString().slice(0, 10);
    const ts = catalogTs();

    const result = this.database
      .prepare(
        `INSERT INTO crm_sop_runs
           (campaign_id, template_id, name, status, start_date, notes, created_at, updated_at)
         VALUES (?, ?, ?, ?, ?, ?, ?, ?)`,
      )
      .run(campaignId, templateId, name, status, startDate, notes, tsDate, ts);

    const runId = Number(result.lastInsertRowid);
    if (templateId && generateTasks) {
      this.generateTasks(runId, templateId, startDate);
    }

    const run = this.getRunById(runId);
    if (!run) throw new Error('Failed to create SOP run');
    return run;
  }

  getRunById(runId: number): SopRunRow | null {
    const row = this.database
      .prepare(`${RUN_SELECT} WHERE r.id = ?`)
      .get(runId) as unknown as Record<string, unknown> | undefined;
    return row ? this.mapRunRow(row) : null;
  }

  listRunTasks(runId: number): SopRunTaskRow[] {
    const rows = this.database
      .prepare(
        `SELECT id, run_id, step_id, position, title, description, role,
                due_date, status, notes, checklist_json, created_at, updated_at
         FROM crm_sop_run_tasks
         WHERE run_id = ?
         ORDER BY position ASC, id ASC`,
      )
      .all(runId) as unknown as Array<Record<string, unknown>>;
    return rows.map((row) => ({
      id: Number(row.id),
      run_id: Number(row.run_id),
      step_id: row.step_id != null ? Number(row.step_id) : null,
      position: Number(row.position ?? 0),
      title: String(row.title ?? ''),
      description: String(row.description ?? ''),
      role: String(row.role ?? ''),
      due_date: String(row.due_date ?? ''),
      status: String(row.status ?? 'todo'),
      notes: String(row.notes ?? ''),
      checklist_json: String(row.checklist_json ?? '[]'),
      created_at: String(row.created_at ?? ''),
      updated_at: String(row.updated_at ?? ''),
    }));
  }

  private generateTasks(runId: number, templateId: number, startDate: string): void {
    const steps = this.listSteps(templateId);
    const ts = catalogTs();
    const today = new Date().toISOString().slice(0, 10);

    for (const step of steps) {
      let due = '';
      if (startDate && isValidDateYmd(startDate)) {
        due = addDaysIso(startDate, step.offset_days);
      }
      this.database
        .prepare(
          `INSERT INTO crm_sop_run_tasks (
             run_id, step_id, position, title, description,
             role, due_date, status, checklist_json, notes, created_at, updated_at
           ) VALUES (?, ?, ?, ?, ?, ?, ?, 'todo', ?, '', ?, ?)`,
        )
        .run(
          runId,
          step.id,
          step.position,
          step.title,
          step.description,
          step.role,
          due,
          step.checklist_json,
          today,
          ts,
        );
    }
  }

  private runStats(runId: number): SopRunStats {
    const rows = this.database
      .prepare('SELECT status FROM crm_sop_run_tasks WHERE run_id = ?')
      .all(runId) as unknown as Array<{ status: string }>;
    const total = rows.length;
    let done = 0;
    let skipped = 0;
    let inProgress = 0;
    for (const r of rows) {
      if (r.status === 'done') done += 1;
      else if (r.status === 'skipped') skipped += 1;
      else if (r.status === 'in_progress') inProgress += 1;
    }
    const today = new Date().toISOString().slice(0, 10);
    const overdueRow = this.database
      .prepare(
        `SELECT count(*) AS cnt FROM crm_sop_run_tasks
         WHERE run_id = ? AND status NOT IN ('done','skipped')
           AND due_date != '' AND due_date < ?`,
      )
      .get(runId, today) as unknown as { cnt: number };
    return {
      total,
      done,
      skipped,
      in_progress: inProgress,
      todo: total - done - skipped - inProgress,
      overdue: Number(overdueRow?.cnt ?? 0),
    };
  }

  private mapTemplateRow(row: Record<string, unknown>): SopTemplateRow {
    return {
      id: Number(row.id),
      code: String(row.code ?? ''),
      name: String(row.name ?? ''),
      channel: String(row.channel ?? ''),
      description: String(row.description ?? ''),
      notes: String(row.notes ?? ''),
      active: Number(row.active ?? 0),
      created_at: String(row.created_at ?? ''),
      updated_at: String(row.updated_at ?? ''),
    };
  }

  private mapStepRow(row: Record<string, unknown>): SopStepRow {
    return {
      id: Number(row.id),
      template_id: Number(row.template_id),
      position: Number(row.position ?? 0),
      title: String(row.title ?? ''),
      description: String(row.description ?? ''),
      offset_days: Number(row.offset_days ?? 0),
      duration_days: Number(row.duration_days ?? 1),
      role: String(row.role ?? ''),
      required: Number(row.required ?? 0),
      checklist_json: String(row.checklist_json ?? '[]'),
      created_at: String(row.created_at ?? ''),
      updated_at: String(row.updated_at ?? ''),
    };
  }

  private mapRunRow(row: Record<string, unknown>): SopRunRow {
    const runId = Number(row.id);
    return {
      id: runId,
      campaign_id: row.campaign_id != null ? Number(row.campaign_id) : null,
      template_id: row.template_id != null ? Number(row.template_id) : null,
      name: String(row.name ?? ''),
      status: String(row.status ?? ''),
      start_date: String(row.start_date ?? ''),
      notes: String(row.notes ?? ''),
      created_at: String(row.created_at ?? ''),
      updated_at: String(row.updated_at ?? ''),
      template_name: row.template_name != null ? String(row.template_name) : undefined,
      template_channel:
        row.template_channel != null ? String(row.template_channel) : undefined,
      campaign_name: row.campaign_name != null ? String(row.campaign_name) : undefined,
      campaign_code: row.campaign_code != null ? String(row.campaign_code) : undefined,
      stats: this.runStats(runId),
    };
  }

  campaignExists(campaignId: number): boolean {
    const row = this.database
      .prepare('SELECT id FROM crm_campaigns WHERE id = ?')
      .get(campaignId) as unknown as { id: number } | undefined;
    return !!row;
  }

  isValidRunStatus(status: string): boolean {
    return (CRM_SOP_RUN_STATUSES as readonly string[]).includes(status);
  }
}
