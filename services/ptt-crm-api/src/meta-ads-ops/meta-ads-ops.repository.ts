import { Injectable, OnModuleDestroy } from '@nestjs/common';
import { Pool } from 'pg';
import { AppConfigService } from '../config/app-config.service';

@Injectable()
export class MetaAdsOpsRepository implements OnModuleDestroy {
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

  async clientExists(clientId: string): Promise<boolean> {
    const result = await this.db.query(`SELECT 1 FROM clients WHERE id = $1::uuid LIMIT 1`, [clientId]);
    return (result.rowCount ?? 0) > 0;
  }

  async isTenantLocked(clientId: string): Promise<boolean> {
    try {
      const result = await this.db.query(
        `SELECT COALESCE(tenant_locked, false) AS locked FROM clients WHERE id = $1::uuid LIMIT 1`,
        [clientId],
      );
      return Boolean(result.rows[0]?.locked);
    } catch {
      return false;
    }
  }

  async fetchMetaAccount(clientId: string): Promise<Record<string, unknown> | null> {
    const result = await this.db.query(
      `SELECT id::text, external_account_id, display_name, status, token_status, meta
       FROM client_channel_accounts
       WHERE client_id = $1::uuid AND channel = 'meta' AND status = 'active'
       ORDER BY updated_at DESC
       LIMIT 1`,
      [clientId],
    );
    return (result.rows[0] as Record<string, unknown> | undefined) ?? null;
  }

  async fetchApprovedCreative(
    clientId: string,
    creativeSubmissionId: string,
  ): Promise<Record<string, unknown> | null> {
    const result = await this.db.query(
      `SELECT id::text, client_id::text, status, title, asset_url, version
       FROM creative_submissions
       WHERE id = $1::uuid AND client_id = $2::uuid
       LIMIT 1`,
      [creativeSubmissionId, clientId],
    );
    const row = result.rows[0];
    if (!row) return null;
    if (String(row.status) !== 'approved') {
      return { ...row, not_approved: true };
    }
    return row as Record<string, unknown>;
  }

  async findWriteRequest(id: string): Promise<Record<string, unknown> | null> {
    const result = await this.db.query(
      `SELECT id::text, client_id::text, status, change_type, temporal_workflow_id,
              execution_error, created_at, updated_at
       FROM campaign_write_requests
       WHERE id = $1::uuid
       LIMIT 1`,
      [id],
    );
    return (result.rows[0] as Record<string, unknown> | undefined) ?? null;
  }
}
