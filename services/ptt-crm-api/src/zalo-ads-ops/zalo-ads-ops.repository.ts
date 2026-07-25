import { Injectable, OnModuleDestroy } from '@nestjs/common';
import { Pool } from 'pg';
import { AppConfigService } from '../config/app-config.service';

@Injectable()
export class ZaloAdsOpsRepository implements OnModuleDestroy {
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
    const result = await this.db.query(`SELECT 1 FROM clients WHERE id = $1::uuid LIMIT 1`, [
      clientId.trim(),
    ]);
    return (result.rowCount ?? 0) > 0;
  }

  async isTenantLocked(clientId: string): Promise<boolean> {
    const result = await this.db.query(
      `SELECT offboard_status FROM clients WHERE id = $1::uuid LIMIT 1`,
      [clientId.trim()],
    );
    const status = String(result.rows[0]?.offboard_status ?? '').trim().toLowerCase();
    return status === 'offboarded' || status === 'offboarding';
  }

  async fetchZaloAccountId(clientId: string): Promise<string | null> {
    const result = await this.db.query(
      `SELECT external_account_id
       FROM client_channel_accounts
       WHERE client_id = $1::uuid AND channel = 'zalo' AND status = 'active'
       ORDER BY updated_at DESC NULLS LAST
       LIMIT 1`,
      [clientId.trim()],
    );
    const id = result.rows[0]?.external_account_id;
    return id != null ? String(id).trim() || null : null;
  }
}
