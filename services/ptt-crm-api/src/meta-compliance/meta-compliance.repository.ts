import { Injectable, OnModuleDestroy } from '@nestjs/common';
import { Pool } from 'pg';
import { AppConfigService } from '../config/app-config.service';
import { COMPLIANCE_EXPORT_VERSION } from './meta-compliance.types';

@Injectable()
export class MetaComplianceRepository implements OnModuleDestroy {
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

  async fetchClient(clientId: string): Promise<Record<string, unknown> | null> {
    const result = await this.db.query(
      `SELECT id::text, code, name, status, created_at, updated_at
       FROM clients WHERE id = $1::uuid LIMIT 1`,
      [clientId],
    );
    return (result.rows[0] as Record<string, unknown> | undefined) ?? null;
  }

  async fetchChannelAccounts(clientId: string): Promise<Array<Record<string, unknown>>> {
    const result = await this.db.query(
      `SELECT id::text, channel, external_account_id, display_name, status,
              token_status, credential_ref,
              CASE WHEN access_token_encrypted IS NOT NULL THEN '[REDACTED]' ELSE NULL END AS access_token,
              meta, created_at, updated_at
       FROM client_channel_accounts
       WHERE client_id = $1::uuid AND channel = 'meta'
       ORDER BY updated_at DESC`,
      [clientId],
    );
    return result.rows as Array<Record<string, unknown>>;
  }

  async fetchPerformanceSummary(clientId: string, days: number): Promise<Record<string, unknown>> {
    const result = await this.db.query(
      `SELECT COALESCE(SUM(spend), 0) AS spend,
              COALESCE(SUM(leads_crm), 0) AS leads_crm,
              COALESCE(SUM(leads_platform), 0) AS leads_platform,
              COUNT(*) FILTER (WHERE hub_campaign_map_id IS NULL)::int AS unmapped_rows,
              COUNT(*)::int AS row_count,
              MIN(performance_date)::text AS date_from,
              MAX(performance_date)::text AS date_to
       FROM daily_performance
       WHERE client_id = $1::uuid
         AND channel = 'meta'
         AND performance_date >= CURRENT_DATE - ($2::int - 1)`,
      [clientId, days],
    );
    const row = result.rows[0] ?? {};
    const spend = Number(row.spend ?? 0);
    const leads = Number(row.leads_crm ?? 0);
    return {
      window_days: days,
      spend,
      leads_crm: leads,
      leads_platform: Number(row.leads_platform ?? 0),
      cpl: leads > 0 ? Math.round(spend / leads) : null,
      unmapped_rows: Number(row.unmapped_rows ?? 0),
      row_count: Number(row.row_count ?? 0),
      date_from: row.date_from,
      date_to: row.date_to,
    };
  }

  async fetchOpenAlerts(clientId: string, limit = 50): Promise<Array<Record<string, unknown>>> {
    try {
      const result = await this.db.query(
        `SELECT id::text, alert_type, severity, message, external_campaign_id,
                performance_date::text, created_at, dedupe_key
         FROM meta_alerts
         WHERE client_id = $1::uuid
           AND channel = 'meta'
           AND acknowledged_at IS NULL
         ORDER BY created_at DESC
         LIMIT $2`,
        [clientId, limit],
      );
      return result.rows as Array<Record<string, unknown>>;
    } catch {
      return [];
    }
  }

  async fetchRecentCampaignWrites(clientId: string, limit = 20): Promise<Array<Record<string, unknown>>> {
    try {
      const result = await this.db.query(
        `SELECT id::text, request_type, status, external_campaign_id, payload,
                created_at, updated_at, approved_at, executed_at, error_message
         FROM campaign_write_requests
         WHERE client_id = $1::uuid
           AND channel = 'meta'
         ORDER BY created_at DESC
         LIMIT $2`,
        [clientId, limit],
      );
      return (result.rows as Array<Record<string, unknown>>).map((row) => ({
        ...row,
        payload: this.redactPayload(row.payload),
      }));
    } catch {
      return [];
    }
  }

  async fetchTrackingSummary(clientId: string, days: number): Promise<Record<string, unknown>> {
    try {
      const result = await this.db.query(
        `SELECT COUNT(*)::int AS total,
                COUNT(*) FILTER (WHERE status = 'sent')::int AS sent,
                COUNT(*) FILTER (WHERE status = 'failed')::int AS failed,
                COUNT(*) FILTER (WHERE status = 'skipped')::int AS skipped
         FROM capi_event_log
         WHERE client_id = $1::uuid
           AND created_at >= NOW() - ($2::int || ' days')::interval`,
        [clientId, days],
      );
      const row = result.rows[0] ?? {};
      return {
        window_days: days,
        capi_events_total: Number(row.total ?? 0),
        capi_sent: Number(row.sent ?? 0),
        capi_failed: Number(row.failed ?? 0),
        capi_skipped: Number(row.skipped ?? 0),
      };
    } catch {
      return { window_days: days, capi_events_total: 0, capi_sent: 0, capi_failed: 0, capi_skipped: 0 };
    }
  }

  exportMeta(): Record<string, unknown> {
    return { export_version: COMPLIANCE_EXPORT_VERSION };
  }

  private redactPayload(payload: unknown): unknown {
    if (!payload || typeof payload !== 'object') return payload;
    const copy = { ...(payload as Record<string, unknown>) };
    for (const key of ['access_token', 'page_access_token', 'token', 'secret']) {
      if (key in copy) copy[key] = '[REDACTED]';
    }
    return copy;
  }
}
