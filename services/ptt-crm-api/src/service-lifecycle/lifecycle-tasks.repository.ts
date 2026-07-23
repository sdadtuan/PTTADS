import { Injectable, OnModuleDestroy } from '@nestjs/common';
import { DatabaseSync } from 'node:sqlite';
import { catalogTs } from '../catalog/catalog-slug.util';
import { AppConfigService } from '../config/app-config.service';
import { ensureSvcTasksSchema } from '../leads-contract/lifecycle-tasks-seed.util';
import { VALID_STAGES } from './service-lifecycle.types';

export interface SvcTaskRow {
  id: number;
  lifecycle_id: number;
  stage: string;
  step_index: number;
  title: string;
  description: string;
  form_fields: unknown[];
  form_data: Record<string, unknown>;
  ai_prompt_key: string;
  ai_output: string;
  is_done: boolean;
  done_at: string;
  done_by: number | null;
  notes: string;
  is_custom: boolean;
  created_at: string;
  updated_at: string;
}

@Injectable()
export class LifecycleTasksRepository implements OnModuleDestroy {
  private db: DatabaseSync | null = null;

  constructor(private readonly config: AppConfigService) {}

  private get database(): DatabaseSync {
    if (!this.db) {
      this.db = new DatabaseSync(this.config.sqlitePath);
      this.db.exec('PRAGMA foreign_keys = ON');
      ensureSvcTasksSchema(this.db);
    }
    return this.db;
  }

  onModuleDestroy(): void {
    if (this.db) {
      this.db.close();
      this.db = null;
    }
  }

  private mapTask(row: Record<string, unknown>): SvcTaskRow {
    let formFields: unknown[] = [];
    let formData: Record<string, unknown> = {};
    try {
      formFields = JSON.parse(String(row.form_fields ?? '[]')) as unknown[];
    } catch {
      formFields = [];
    }
    try {
      formData = JSON.parse(String(row.form_data ?? '{}')) as Record<string, unknown>;
    } catch {
      formData = {};
    }
    return {
      id: Number(row.id),
      lifecycle_id: Number(row.lifecycle_id),
      stage: String(row.stage ?? ''),
      step_index: Number(row.step_index ?? 0),
      title: String(row.title ?? ''),
      description: String(row.description ?? ''),
      form_fields: formFields,
      form_data: formData,
      ai_prompt_key: String(row.ai_prompt_key ?? ''),
      ai_output: String(row.ai_output ?? ''),
      is_done: Number(row.is_done ?? 0) === 1,
      done_at: String(row.done_at ?? ''),
      done_by: row.done_by != null ? Number(row.done_by) : null,
      notes: String(row.notes ?? ''),
      is_custom: Number(row.is_custom ?? 0) === 1,
      created_at: String(row.created_at ?? ''),
      updated_at: String(row.updated_at ?? ''),
    };
  }

  listTasksGrouped(lifecycleId: number): Record<string, SvcTaskRow[]> {
    const rows = this.database
      .prepare(
        `SELECT * FROM crm_svc_tasks WHERE lifecycle_id = ?
         ORDER BY stage, step_index ASC, id ASC`,
      )
      .all(lifecycleId) as Array<Record<string, unknown>>;
    const out: Record<string, SvcTaskRow[]> = {};
    for (const stage of VALID_STAGES) out[stage] = [];
    for (const row of rows) {
      const task = this.mapTask(row);
      if (!out[task.stage]) out[task.stage] = [];
      out[task.stage].push(task);
    }
    return out;
  }

  getTask(taskId: number): SvcTaskRow | null {
    const row = this.database.prepare('SELECT * FROM crm_svc_tasks WHERE id = ?').get(taskId) as
      | Record<string, unknown>
      | undefined;
    return row ? this.mapTask(row) : null;
  }

  isStageComplete(lifecycleId: number, stage: string): boolean {
    const row = this.database
      .prepare(
        `SELECT COUNT(*) AS total, SUM(CASE WHEN is_done = 1 THEN 1 ELSE 0 END) AS done
         FROM crm_svc_tasks WHERE lifecycle_id = ? AND stage = ?`,
      )
      .get(lifecycleId, stage) as { total: number; done: number };
    const total = Number(row.total ?? 0);
    if (total === 0) return true;
    return Number(row.done ?? 0) >= total;
  }

  getProgress(lifecycleId: number): Record<string, { total: number; done: number; pct: number }> {
    const out: Record<string, { total: number; done: number; pct: number }> = {};
    for (const stage of VALID_STAGES) {
      const row = this.database
        .prepare(
          `SELECT COUNT(*) AS total, SUM(CASE WHEN is_done = 1 THEN 1 ELSE 0 END) AS done
           FROM crm_svc_tasks WHERE lifecycle_id = ? AND stage = ?`,
        )
        .get(lifecycleId, stage) as { total: number; done: number };
      const total = Number(row.total ?? 0);
      const done = Number(row.done ?? 0);
      out[stage] = { total, done, pct: total > 0 ? Math.round((done / total) * 100) : 100 };
    }
    return out;
  }

  updateTask(
    taskId: number,
    patch: { is_done?: boolean; notes?: string; form_data?: Record<string, unknown>; done_by?: number | null },
  ): SvcTaskRow | null {
    const existing = this.getTask(taskId);
    if (!existing) return null;
    const ts = catalogTs();
    let isDone = existing.is_done ? 1 : 0;
    let doneAt = existing.done_at;
    if (patch.is_done != null) {
      isDone = patch.is_done ? 1 : 0;
      doneAt = patch.is_done ? ts : '';
    }
    const notes = patch.notes != null ? String(patch.notes).slice(0, 2000) : existing.notes;
    const formData =
      patch.form_data != null ? JSON.stringify(patch.form_data) : JSON.stringify(existing.form_data);
    const doneBy = patch.done_by !== undefined ? patch.done_by : existing.done_by;
    this.database
      .prepare(
        `UPDATE crm_svc_tasks SET is_done = ?, done_at = ?, done_by = ?, notes = ?, form_data = ?, updated_at = ?
         WHERE id = ?`,
      )
      .run(isDone, doneAt, doneBy, notes, formData, ts, taskId);
    return this.getTask(taskId);
  }

  createCustomTask(lifecycleId: number, stage: string, title: string, description: string): SvcTaskRow {
    const ts = catalogTs();
    const id = Number(
      this.database
        .prepare(
          `INSERT INTO crm_svc_tasks
             (lifecycle_id, stage, step_index, title, description, form_fields, form_data,
              ai_prompt_key, ai_output, is_done, done_at, done_by, notes, is_custom, created_at, updated_at)
           VALUES (?, ?, 999, ?, ?, '[]', '{}', '', '', 0, '', NULL, '', 1, ?, ?)`,
        )
        .run(lifecycleId, stage, title.slice(0, 400), description.slice(0, 4000), ts, ts).lastInsertRowid,
    );
    return this.getTask(id)!;
  }
}
