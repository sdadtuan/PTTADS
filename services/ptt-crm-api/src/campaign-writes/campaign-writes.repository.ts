import { Injectable, OnModuleDestroy } from '@nestjs/common';
import { Pool } from 'pg';
import { AppConfigService } from '../config/app-config.service';
import { CampaignWriteRow, CampaignWriteStatus } from './campaign-writes.types';

@Injectable()
export class CampaignWritesRepository implements OnModuleDestroy {
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

  async tableReady(): Promise<boolean> {
    const result = await this.db.query(
      `SELECT 1 FROM information_schema.tables
       WHERE table_schema = 'public' AND table_name = 'campaign_write_requests' LIMIT 1`,
    );
    return (result.rowCount ?? 0) > 0;
  }

  async insertRequest(input: {
    clientId: string;
    channel: string;
    externalAccountId: string | null;
    externalCampaignId: string;
    externalCampaignName: string | null;
    changeType: string;
    oldValue: Record<string, unknown>;
    newValue: Record<string, unknown>;
    submittedBy: string;
    workflowId: string | null;
    runId: string | null;
  }): Promise<CampaignWriteRow> {
    const result = await this.db.query(
      `INSERT INTO campaign_write_requests (
         client_id, channel, external_account_id, external_campaign_id,
         external_campaign_name, change_type, old_value, new_value,
         submitted_by, temporal_workflow_id, temporal_run_id
       ) VALUES (
         $1::uuid, $2, $3, $4, $5, $6, $7::jsonb, $8::jsonb, $9, $10, $11
       )
       RETURNING id::text, client_id::text, channel, external_account_id,
                 external_campaign_id, external_campaign_name, change_type,
                 old_value, new_value, status, submitted_by,
                 approved_by, approved_at, executed_at, execution_error,
                 temporal_workflow_id, created_at`,
      [
        input.clientId,
        input.channel,
        input.externalAccountId,
        input.externalCampaignId,
        input.externalCampaignName,
        input.changeType,
        JSON.stringify(input.oldValue),
        JSON.stringify(input.newValue),
        input.submittedBy,
        input.workflowId,
        input.runId,
      ],
    );
    return this.mapRow(result.rows[0]);
  }

  async listPending(clientId?: string): Promise<CampaignWriteRow[]> {
    const params: string[] = [];
    let where = "status = 'pending_approval'";
    if (clientId) {
      params.push(clientId);
      where += ` AND client_id = $${params.length}::uuid`;
    }
    const result = await this.db.query(
      `SELECT id::text, client_id::text, channel, external_account_id,
              external_campaign_id, external_campaign_name, change_type,
              old_value, new_value, status, submitted_by,
              approved_by, approved_at, executed_at, execution_error,
              temporal_workflow_id, created_at
       FROM campaign_write_requests
       WHERE ${where}
       ORDER BY created_at DESC
       LIMIT 100`,
      params,
    );
    return result.rows.map((r) => this.mapRow(r));
  }

  async findById(id: string): Promise<CampaignWriteRow | null> {
    const result = await this.db.query(
      `SELECT id::text, client_id::text, channel, external_account_id,
              external_campaign_id, external_campaign_name, change_type,
              old_value, new_value, status, submitted_by,
              approved_by, approved_at, executed_at, execution_error,
              temporal_workflow_id, created_at
       FROM campaign_write_requests WHERE id = $1::uuid LIMIT 1`,
      [id],
    );
    const row = result.rows[0];
    return row ? this.mapRow(row) : null;
  }

  async markApproved(id: string, approvedBy: string, note: string | null): Promise<CampaignWriteRow | null> {
    const result = await this.db.query(
      `UPDATE campaign_write_requests
       SET status = 'approved', approved_by = $2, approved_at = NOW(),
           review_note = COALESCE($3, review_note), updated_at = NOW()
       WHERE id = $1::uuid AND status = 'pending_approval'
       RETURNING id::text, client_id::text, channel, external_account_id,
                 external_campaign_id, external_campaign_name, change_type,
                 old_value, new_value, status, submitted_by,
                 approved_by, approved_at, executed_at, execution_error,
                 temporal_workflow_id, created_at`,
      [id, approvedBy, note],
    );
    const row = result.rows[0];
    return row ? this.mapRow(row) : null;
  }

  async markRejected(id: string, approvedBy: string, note: string | null): Promise<CampaignWriteRow | null> {
    const result = await this.db.query(
      `UPDATE campaign_write_requests
       SET status = 'rejected', approved_by = $2, approved_at = NOW(),
           review_note = COALESCE($3, review_note), updated_at = NOW()
       WHERE id = $1::uuid AND status = 'pending_approval'
       RETURNING id::text, client_id::text, channel, external_account_id,
                 external_campaign_id, external_campaign_name, change_type,
                 old_value, new_value, status, submitted_by,
                 approved_by, approved_at, executed_at, execution_error,
                 temporal_workflow_id, created_at`,
      [id, approvedBy, note],
    );
    const row = result.rows[0];
    return row ? this.mapRow(row) : null;
  }

  async updateTemporalMeta(id: string, workflowId: string, runId: string | null): Promise<CampaignWriteRow | null> {
    const result = await this.db.query(
      `UPDATE campaign_write_requests
       SET temporal_workflow_id = $2, temporal_run_id = $3, updated_at = NOW()
       WHERE id = $1::uuid
       RETURNING id::text, client_id::text, channel, external_account_id,
                 external_campaign_id, external_campaign_name, change_type,
                 old_value, new_value, status, submitted_by,
                 approved_by, approved_at, executed_at, execution_error,
                 temporal_workflow_id, created_at`,
      [id, workflowId, runId],
    );
    const row = result.rows[0];
    return row ? this.mapRow(row) : null;
  }

  private mapRow(row: Record<string, unknown>): CampaignWriteRow {
    return {
      id: String(row.id),
      client_id: String(row.client_id),
      channel: String(row.channel ?? 'meta'),
      external_account_id: row.external_account_id ? String(row.external_account_id) : null,
      external_campaign_id: String(row.external_campaign_id),
      external_campaign_name: row.external_campaign_name ? String(row.external_campaign_name) : null,
      change_type: String(row.change_type) as CampaignWriteRow['change_type'],
      old_value: (row.old_value as Record<string, unknown>) ?? {},
      new_value: (row.new_value as Record<string, unknown>) ?? {},
      status: String(row.status) as CampaignWriteStatus,
      submitted_by: String(row.submitted_by),
      approved_by: row.approved_by ? String(row.approved_by) : null,
      approved_at: row.approved_at ? String(row.approved_at) : null,
      executed_at: row.executed_at ? String(row.executed_at) : null,
      execution_error: row.execution_error ? String(row.execution_error) : null,
      temporal_workflow_id: row.temporal_workflow_id ? String(row.temporal_workflow_id) : null,
      created_at: String(row.created_at),
    };
  }
}
