import { Injectable, OnModuleDestroy } from '@nestjs/common';
import { Pool } from 'pg';
import { AppConfigService } from '../config/app-config.service';
import { parseZaloAccountRow, type ZaloChannelAccountRow } from './launch-qa-zalo.util';

@Injectable()
export class ZaloLaunchQaRepository implements OnModuleDestroy {
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

  async fetchZaloChannelAccount(clientId: string): Promise<ZaloChannelAccountRow | null> {
    const result = await this.db.query(
      `SELECT BOOL_OR(TRUE) AS has_account,
              BOOL_OR(access_token_encrypted IS NOT NULL) AS has_token,
              (array_agg(meta_json ORDER BY updated_at DESC NULLS LAST))[1] AS meta_json
       FROM client_channel_accounts
       WHERE client_id = $1::uuid AND channel = 'zalo' AND status = 'active'`,
      [clientId.trim()],
    );
    const row = result.rows[0];
    if (!row?.has_account) {
      return null;
    }
    return parseZaloAccountRow({
      has_account: true,
      has_token: row.has_token,
      meta_json: row.meta_json,
    });
  }
}
