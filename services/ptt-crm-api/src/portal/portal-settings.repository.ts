import { Injectable, OnModuleDestroy } from '@nestjs/common';
import { Pool } from 'pg';
import { AppConfigService } from '../config/app-config.service';

export interface PortalClientSettingsRow {
  client_id: string;
  display_name: string | null;
  logo_url: string | null;
  am_contact_name: string | null;
  am_contact_email: string | null;
  accent_color: string | null;
  updated_at: string | null;
  updated_by: string | null;
}

@Injectable()
export class PortalSettingsRepository implements OnModuleDestroy {
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
      `SELECT COUNT(*)::int AS c FROM information_schema.tables
       WHERE table_schema = 'public' AND table_name = 'portal_client_settings'`,
    );
    return Number(result.rows[0]?.c ?? 0) > 0;
  }

  async getClientName(clientId: string): Promise<string | null> {
    const result = await this.db.query(`SELECT name FROM clients WHERE id = $1::uuid LIMIT 1`, [
      clientId,
    ]);
    return (result.rows[0]?.name as string | undefined) ?? null;
  }

  async findByClientId(clientId: string): Promise<PortalClientSettingsRow | null> {
    if (!(await this.tableReady())) {
      return null;
    }
    const result = await this.db.query(
      `SELECT client_id::text, display_name, logo_url, am_contact_name, am_contact_email,
              accent_color, updated_at, updated_by
       FROM portal_client_settings
       WHERE client_id = $1::uuid
       LIMIT 1`,
      [clientId],
    );
    const row = result.rows[0];
    if (!row) {
      return null;
    }
    return {
      client_id: String(row.client_id),
      display_name: row.display_name ?? null,
      logo_url: row.logo_url ?? null,
      am_contact_name: row.am_contact_name ?? null,
      am_contact_email: row.am_contact_email ?? null,
      accent_color: row.accent_color ?? null,
      updated_at: row.updated_at ? new Date(row.updated_at).toISOString() : null,
      updated_by: row.updated_by ?? null,
    };
  }

  async upsert(
    clientId: string,
    input: {
      display_name?: string | null;
      logo_url?: string | null;
      am_contact_name?: string | null;
      am_contact_email?: string | null;
      accent_color?: string | null;
      updated_by: string;
    },
  ): Promise<PortalClientSettingsRow> {
    const result = await this.db.query(
      `INSERT INTO portal_client_settings (
         client_id, display_name, logo_url, am_contact_name, am_contact_email, accent_color, updated_by
       ) VALUES ($1::uuid, $2, $3, $4, $5, $6, $7)
       ON CONFLICT (client_id) DO UPDATE SET
         display_name = COALESCE(EXCLUDED.display_name, portal_client_settings.display_name),
         logo_url = COALESCE(EXCLUDED.logo_url, portal_client_settings.logo_url),
         am_contact_name = COALESCE(EXCLUDED.am_contact_name, portal_client_settings.am_contact_name),
         am_contact_email = COALESCE(EXCLUDED.am_contact_email, portal_client_settings.am_contact_email),
         accent_color = COALESCE(EXCLUDED.accent_color, portal_client_settings.accent_color),
         updated_by = EXCLUDED.updated_by,
         updated_at = NOW()
       RETURNING client_id::text, display_name, logo_url, am_contact_name, am_contact_email,
                 accent_color, updated_at, updated_by`,
      [
        clientId,
        input.display_name ?? null,
        input.logo_url ?? null,
        input.am_contact_name ?? null,
        input.am_contact_email ?? null,
        input.accent_color ?? null,
        input.updated_by,
      ],
    );
    const row = result.rows[0];
    return {
      client_id: String(row.client_id),
      display_name: row.display_name ?? null,
      logo_url: row.logo_url ?? null,
      am_contact_name: row.am_contact_name ?? null,
      am_contact_email: row.am_contact_email ?? null,
      accent_color: row.accent_color ?? null,
      updated_at: row.updated_at ? new Date(row.updated_at).toISOString() : null,
      updated_by: row.updated_by ?? null,
    };
  }
}
