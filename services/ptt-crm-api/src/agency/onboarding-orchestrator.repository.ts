import { Injectable, OnModuleDestroy } from '@nestjs/common';
import { Pool } from 'pg';
import { AppConfigService } from '../config/app-config.service';

const SEO_SCHEMA = 'seo_aeo';
const EMAIL_SCHEMA = 'email_mkt';

function parseJsonObject(raw: unknown): Record<string, unknown> {
  if (raw == null) return {};
  if (typeof raw === 'object' && !Array.isArray(raw)) return raw as Record<string, unknown>;
  try {
    return JSON.parse(String(raw)) as Record<string, unknown>;
  } catch {
    return {};
  }
}

function gscConnected(integrations: Record<string, unknown>): boolean {
  const gsc = parseJsonObject(integrations.gsc);
  return Boolean(gsc.refresh_token_encrypted || gsc.refresh_token || gsc.status === 'connected');
}

@Injectable()
export class OnboardingOrchestratorRepository implements OnModuleDestroy {
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

  async detectSeo(clientId: string): Promise<{
    mapped: boolean;
    customer_id: number | null;
    gsc_connected: boolean;
    has_settings: boolean;
  }> {
    try {
      const mapResult = await this.db.query<{ customer_id: number }>(
        `SELECT customer_id FROM ${SEO_SCHEMA}.seo_portal_client_map
         WHERE client_id = $1::uuid AND active IS NOT FALSE
         LIMIT 1`,
        [clientId],
      );
      const customerId = mapResult.rows[0] ? Number(mapResult.rows[0].customer_id) : null;
      if (customerId == null) {
        return { mapped: false, customer_id: null, gsc_connected: false, has_settings: false };
      }
      const settingsResult = await this.db.query<{ integrations_json: unknown; domains_json: unknown }>(
        `SELECT integrations_json, domains_json
         FROM ${SEO_SCHEMA}.seo_client_settings
         WHERE customer_id = $1
         LIMIT 1`,
        [customerId],
      );
      const row = settingsResult.rows[0];
      if (!row) {
        return { mapped: true, customer_id: customerId, gsc_connected: false, has_settings: false };
      }
      const integrations = parseJsonObject(row.integrations_json);
      const domains = Array.isArray(row.domains_json) ? row.domains_json : [];
      return {
        mapped: true,
        customer_id: customerId,
        gsc_connected: gscConnected(integrations),
        has_settings: domains.length > 0,
      };
    } catch {
      return { mapped: false, customer_id: null, gsc_connected: false, has_settings: false };
    }
  }

  async detectEmail(clientId: string): Promise<{ workspace: boolean; verified_domain: boolean }> {
    try {
      const workspaceResult = await this.db.query(
        `SELECT 1 FROM ${EMAIL_SCHEMA}.workspaces WHERE client_id = $1::uuid LIMIT 1`,
        [clientId],
      );
      const domainResult = await this.db.query(
        `SELECT 1 FROM ${EMAIL_SCHEMA}.domains
         WHERE client_id = $1::uuid
           AND status = 'active'
           AND spf_status = 'pass'
         LIMIT 1`,
        [clientId],
      );
      return {
        workspace: (workspaceResult.rowCount ?? 0) > 0,
        verified_domain: (domainResult.rowCount ?? 0) > 0,
      };
    } catch {
      return { workspace: false, verified_domain: false };
    }
  }

  async countLeads(clientId: string): Promise<number> {
    try {
      const result = await this.db.query<{ c: number }>(
        `SELECT COUNT(*)::int AS c FROM crm_leads WHERE agency_client_id = $1::uuid`,
        [clientId],
      );
      return Number(result.rows[0]?.c ?? 0);
    } catch {
      return 0;
    }
  }

  async countZaloLeads(clientId: string): Promise<number> {
    try {
      const result = await this.db.query<{ c: number }>(
        `SELECT COUNT(*)::int AS c FROM crm_leads
         WHERE agency_client_id = $1::uuid AND lower(COALESCE(channel, '')) = 'zalo'`,
        [clientId],
      );
      return Number(result.rows[0]?.c ?? 0);
    } catch {
      return 0;
    }
  }

  async zaloInsightsSynced(clientId: string): Promise<boolean> {
    try {
      const result = await this.db.query(
        `SELECT 1 FROM daily_performance
         WHERE client_id = $1::uuid AND channel = 'zalo'
         LIMIT 1`,
        [clientId],
      );
      return (result.rowCount ?? 0) > 0;
    } catch {
      return false;
    }
  }
}
