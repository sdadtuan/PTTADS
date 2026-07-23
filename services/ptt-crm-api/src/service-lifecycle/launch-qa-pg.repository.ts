import { Injectable, OnModuleDestroy } from '@nestjs/common';
import { Pool } from 'pg';
import { AppConfigService } from '../config/app-config.service';
import { launchQaProgress } from './lifecycle-launch-gate.util';

export const DEFAULT_LAUNCH_QA_CHECKLIST: Record<
  string,
  { label: string; completed: boolean; completed_by?: string; note?: string }
> = {
  pixel_verified: { label: 'Pixel / dataset verified', completed: false },
  naming_convention: { label: 'Naming convention OK', completed: false },
  budget_confirmed: { label: 'Budget confirmed with client', completed: false },
  creative_approved: { label: 'Creative client-approved', completed: false },
  utm_tracking: { label: 'UTM tracking template', completed: false },
  qa_signoff: { label: 'PM / QA sign-off', completed: false },
};

export interface LaunchQaRunRow {
  id: string;
  client_id: string;
  external_campaign_id: string;
  campaign_name: string | null;
  status: string;
  checklist: Record<string, { label?: string; completed?: boolean; completed_by?: string; note?: string }>;
  launch_ready: boolean;
  temporal_workflow_id: string | null;
  temporal_run_id: string | null;
  started_by: string | null;
  started_at: string;
  completed_at: string | null;
}

@Injectable()
export class LaunchQaPgRepository implements OnModuleDestroy {
  private pool: Pool | null = null;

  constructor(private readonly config: AppConfigService) {}

  private get db(): Pool {
    if (!this.pool) {
      this.pool = new Pool({ connectionString: this.config.databaseUrl });
    }
    return this.pool;
  }

  onModuleDestroy(): void {
    void this.pool?.end();
    this.pool = null;
  }

  async pgReady(): Promise<boolean> {
    const result = await this.db.query(
      `SELECT COUNT(*)::int AS c FROM information_schema.tables
       WHERE table_schema = 'public' AND table_name = 'launch_qa_runs'`,
    );
    return Number(result.rows[0]?.c ?? 0) > 0;
  }

  async clientExists(clientId: string): Promise<boolean> {
    const result = await this.db.query(`SELECT 1 FROM clients WHERE id = $1::uuid LIMIT 1`, [clientId]);
    return (result.rowCount ?? 0) > 0;
  }

  async findLatestRun(clientId: string, externalCampaignId: string): Promise<LaunchQaRunRow | null> {
    const result = await this.db.query(
      `SELECT id::text, client_id::text, external_campaign_id, campaign_name,
              status, checklist, launch_ready, temporal_workflow_id, temporal_run_id,
              started_by, started_at, completed_at
       FROM launch_qa_runs
       WHERE client_id = $1::uuid AND external_campaign_id = $2
       ORDER BY started_at DESC
       LIMIT 1`,
      [clientId, externalCampaignId],
    );
    const row = result.rows[0];
    return row ? this.mapRow(row) : null;
  }

  async createRun(input: {
    clientId: string;
    externalCampaignId: string;
    campaignName?: string;
    startedBy?: string;
    temporalWorkflowId?: string | null;
    temporalRunId?: string | null;
  }): Promise<LaunchQaRunRow> {
    const checklist = JSON.parse(JSON.stringify(DEFAULT_LAUNCH_QA_CHECKLIST));
    const result = await this.db.query(
      `INSERT INTO launch_qa_runs (
         client_id, external_campaign_id, campaign_name, checklist, started_by,
         temporal_workflow_id, temporal_run_id
       ) VALUES ($1::uuid, $2, $3, $4::jsonb, $5, $6, $7)
       RETURNING id::text, client_id::text, external_campaign_id, campaign_name,
                 status, checklist, launch_ready, temporal_workflow_id, temporal_run_id,
                 started_by, started_at, completed_at`,
      [
        input.clientId,
        input.externalCampaignId,
        input.campaignName?.trim() || null,
        JSON.stringify(checklist),
        input.startedBy?.trim() || null,
        input.temporalWorkflowId ?? null,
        input.temporalRunId ?? null,
      ],
    );
    return this.mapRow(result.rows[0]);
  }

  async updateTemporalMeta(
    runId: string,
    workflowId: string,
    runIdTemporal: string | null,
  ): Promise<void> {
    await this.db.query(
      `UPDATE launch_qa_runs SET temporal_workflow_id = $2, temporal_run_id = $3, updated_at = NOW()
       WHERE id = $1::uuid`,
      [runId, workflowId, runIdTemporal],
    );
  }

  async updateChecklistItem(
    runId: string,
    itemKey: string,
    input: { completed: boolean; completedBy?: string; note?: string },
  ): Promise<LaunchQaRunRow> {
    const existing = await this.findById(runId);
    if (!existing) {
      throw new Error('run_not_found');
    }
    if (existing.status !== 'in_progress') {
      throw new Error('run_not_in_progress');
    }
    const checklist = { ...(existing.checklist ?? {}) };
    if (!(itemKey in checklist)) {
      throw new Error('invalid_item');
    }
    const entry = { ...checklist[itemKey] };
    entry.completed = Boolean(input.completed);
    if (input.completedBy) entry.completed_by = input.completedBy;
    if (input.note) entry.note = input.note;
    checklist[itemKey] = entry;

    const progress = launchQaProgress(checklist);
    const allDone = progress.total > 0 && progress.completed === progress.total;

    const result = await this.db.query(
      allDone
        ? `UPDATE launch_qa_runs
           SET checklist = $2::jsonb,
               status = 'passed',
               launch_ready = TRUE,
               completed_at = NOW(),
               updated_at = NOW()
           WHERE id = $1::uuid AND status = 'in_progress'
           RETURNING id::text, client_id::text, external_campaign_id, campaign_name,
                     status, checklist, launch_ready, temporal_workflow_id, temporal_run_id,
                     started_by, started_at, completed_at`
        : `UPDATE launch_qa_runs
           SET checklist = $2::jsonb, updated_at = NOW()
           WHERE id = $1::uuid AND status = 'in_progress'
           RETURNING id::text, client_id::text, external_campaign_id, campaign_name,
                     status, checklist, launch_ready, temporal_workflow_id, temporal_run_id,
                     started_by, started_at, completed_at`,
      [runId, JSON.stringify(checklist)],
    );
    if (!result.rows[0]) {
      throw new Error('update_failed');
    }
    return this.mapRow(result.rows[0]);
  }

  async findById(runId: string): Promise<LaunchQaRunRow | null> {
    const result = await this.db.query(
      `SELECT id::text, client_id::text, external_campaign_id, campaign_name,
              status, checklist, launch_ready, temporal_workflow_id, temporal_run_id,
              started_by, started_at, completed_at
       FROM launch_qa_runs WHERE id = $1::uuid LIMIT 1`,
      [runId],
    );
    const row = result.rows[0];
    return row ? this.mapRow(row) : null;
  }

  async listRuns(statusFilter: string, limit = 100): Promise<LaunchQaRunRow[]> {
    const filter = statusFilter.trim().toLowerCase();
    const params: unknown[] = [Math.min(200, Math.max(1, limit))];
    let where = '';
    if (filter && filter !== 'all') {
      where = `WHERE status = $2`;
      params.push(filter);
    }
    const result = await this.db.query(
      `SELECT id::text, client_id::text, external_campaign_id, campaign_name,
              status, checklist, launch_ready, temporal_workflow_id, temporal_run_id,
              started_by, started_at, completed_at
       FROM launch_qa_runs
       ${where}
       ORDER BY started_at DESC
       LIMIT $1`,
      params,
    );
    return result.rows.map((row) => this.mapRow(row));
  }

  async countByStatus(): Promise<Record<string, number>> {
    const result = await this.db.query(
      `SELECT status, COUNT(*)::int AS c FROM launch_qa_runs GROUP BY status`,
    );
    const out: Record<string, number> = {
      all: 0,
      in_progress: 0,
      passed: 0,
      failed: 0,
      blocked: 0,
      timeout: 0,
    };
    for (const row of result.rows) {
      const status = String(row.status ?? '');
      const count = Number(row.c ?? 0);
      out[status] = count;
      out.all += count;
    }
    return out;
  }

  private mapRow(row: Record<string, unknown>): LaunchQaRunRow {
    return {
      id: String(row.id),
      client_id: String(row.client_id),
      external_campaign_id: String(row.external_campaign_id),
      campaign_name: row.campaign_name != null ? String(row.campaign_name) : null,
      status: String(row.status ?? 'in_progress'),
      checklist: (row.checklist as LaunchQaRunRow['checklist']) ?? {},
      launch_ready: Boolean(row.launch_ready),
      temporal_workflow_id: row.temporal_workflow_id != null ? String(row.temporal_workflow_id) : null,
      temporal_run_id: row.temporal_run_id != null ? String(row.temporal_run_id) : null,
      started_by: row.started_by != null ? String(row.started_by) : null,
      started_at: this.toIso(row.started_at) ?? new Date().toISOString(),
      completed_at: row.completed_at ? this.toIso(row.completed_at) : null,
    };
  }

  private toIso(value: unknown): string | null {
    if (value instanceof Date) return value.toISOString();
    return value ? String(value) : null;
  }
}
