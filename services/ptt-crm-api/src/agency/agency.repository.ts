import { Injectable, OnModuleDestroy } from '@nestjs/common';
import { Pool } from 'pg';
import { AppConfigService } from '../config/app-config.service';
import {
  AgencyChannelAccount,
  AgencyClientDetail,
  AgencyClientRow,
  FacebookHubClientRow,
  HubCampaignGlobalRow,
  HubCampaignMapRow,
  JobRow,
  NotificationRow,
} from './agency.types';

function iso(value: unknown): string | null {
  if (value == null) return null;
  if (value instanceof Date) return value.toISOString();
  return String(value);
}

function computeCpl(spend: number, leads: number): number | null {
  if (spend <= 0 || leads <= 0) return null;
  return Math.round((spend / leads) * 100) / 100;
}

@Injectable()
export class AgencyRepository implements OnModuleDestroy {
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
    try {
      const result = await this.db.query(`SELECT 1 FROM clients LIMIT 1`);
      return (result.rowCount ?? 0) >= 0;
    } catch {
      return false;
    }
  }

  async listClients(params: {
    status?: string;
    q?: string;
    ownerAmId?: string;
    industrySlug?: string;
    limit: number;
    offset: number;
  }): Promise<AgencyClientRow[]> {
    const clauses = ['1=1'];
    const values: unknown[] = [];
    let idx = 1;

    if (params.status) {
      clauses.push(`c.status = $${idx++}`);
      values.push(params.status);
    }
    if (params.ownerAmId) {
      clauses.push(`c.owner_am_id ILIKE $${idx++}`);
      values.push(`%${params.ownerAmId.trim()}%`);
    }
    if (params.industrySlug) {
      clauses.push(`c.industry_slug ILIKE $${idx++}`);
      values.push(`%${params.industrySlug.trim()}%`);
    }
    if (params.q) {
      clauses.push(`(c.code ILIKE $${idx} OR c.name ILIKE $${idx + 1})`);
      values.push(`%${params.q}%`, `%${params.q}%`);
      idx += 2;
    }
    values.push(params.limit, params.offset);

    const result = await this.db.query(
      `SELECT c.id::text, c.code, c.name, c.industry_slug, c.status, c.owner_am_id,
              c.notes, c.created_at, c.updated_at,
              COALESCE(ch.channels, '') AS channels
       FROM clients c
       LEFT JOIN LATERAL (
         SELECT string_agg(DISTINCT channel, ', ' ORDER BY channel) AS channels
         FROM client_channel_accounts cca
         WHERE cca.client_id = c.id
       ) ch ON TRUE
       WHERE ${clauses.join(' AND ')}
       ORDER BY c.updated_at DESC
       LIMIT $${idx++} OFFSET $${idx}`,
      values,
    );

    return result.rows.map((row) => ({
      id: String(row.id),
      code: row.code ?? '',
      name: row.name ?? '',
      industry_slug: row.industry_slug ?? null,
      status: row.status ?? '',
      owner_am_id: row.owner_am_id ?? null,
      notes: row.notes ?? null,
      created_at: iso(row.created_at),
      updated_at: iso(row.updated_at),
      channels: row.channels ?? '',
    }));
  }

  async createClient(body: {
    code: string;
    name: string;
    industry_slug?: string;
    owner_am_id?: string;
    notes?: string;
  }): Promise<AgencyClientRow> {
    const code = body.code.trim().toUpperCase();
    const name = body.name.trim();
    const result = await this.db.query(
      `INSERT INTO clients (code, name, industry_slug, status, owner_am_id, notes)
       VALUES ($1, $2, $3, 'onboarding', $4, $5)
       RETURNING id::text, code, name, industry_slug, status, owner_am_id, notes, created_at, updated_at`,
      [
        code,
        name,
        body.industry_slug?.trim() || null,
        body.owner_am_id?.trim() || null,
        body.notes?.trim() || null,
      ],
    );
    const row = result.rows[0];
    try {
      await this.db.query(`SELECT seed_client_onboarding($1::uuid)`, [row.id]);
    } catch {
      // seed function optional on minimal DDL
    }
    return {
      id: String(row.id),
      code: row.code ?? '',
      name: row.name ?? '',
      industry_slug: row.industry_slug ?? null,
      status: row.status ?? 'onboarding',
      owner_am_id: row.owner_am_id ?? null,
      notes: row.notes ?? null,
      created_at: iso(row.created_at),
      updated_at: iso(row.updated_at),
      channels: '',
    };
  }

  async fetchClient(clientId: string): Promise<AgencyClientDetail | null> {
    const result = await this.db.query(
      `SELECT id::text, code, name, industry_slug, status, owner_am_id, notes, created_at, updated_at
       FROM clients WHERE id = $1::uuid`,
      [clientId],
    );
    const row = result.rows[0];
    if (!row) return null;

    const accounts = await this.listChannelAccounts(clientId);
    return {
      id: String(row.id),
      code: row.code ?? '',
      name: row.name ?? '',
      industry_slug: row.industry_slug ?? null,
      status: row.status ?? '',
      owner_am_id: row.owner_am_id ?? null,
      notes: row.notes ?? null,
      created_at: iso(row.created_at),
      updated_at: iso(row.updated_at),
      channel_accounts: accounts,
    };
  }

  async listChannelAccounts(clientId: string): Promise<AgencyChannelAccount[]> {
    const result = await this.db.query(
      `SELECT id::text, channel, external_account_id, display_name, status
       FROM client_channel_accounts
       WHERE client_id = $1::uuid
       ORDER BY channel, display_name NULLS LAST`,
      [clientId],
    );
    return result.rows.map((row) => ({
      id: String(row.id),
      channel: row.channel ?? '',
      external_account_id: row.external_account_id ?? null,
      display_name: row.display_name ?? null,
      status: row.status ?? null,
    }));
  }

  async clientCounts(): Promise<Record<string, number>> {
    const result = await this.db.query(`SELECT status, COUNT(*)::int FROM clients GROUP BY status`);
    const out: Record<string, number> = {};
    for (const row of result.rows) {
      out[String(row.status)] = Number(row.c);
    }
    return out;
  }

  async jobStats(): Promise<Record<string, number>> {
    const result = await this.db.query(`SELECT status, COUNT(*)::int AS c FROM job_queue GROUP BY status`);
    const out: Record<string, number> = {};
    for (const row of result.rows) {
      out[String(row.status)] = Number(row.c);
    }
    for (const key of ['pending', 'running', 'done', 'failed', 'dead']) {
      out[key] ??= 0;
    }
    return out;
  }

  async listJobs(params: {
    status?: string;
    limit: number;
    offset: number;
  }): Promise<JobRow[]> {
    const clauses = ['1=1'];
    const values: unknown[] = [];
    let idx = 1;
    if (params.status) {
      clauses.push(`j.status = $${idx++}`);
      values.push(params.status);
    }
    values.push(params.limit, params.offset);

    const result = await this.db.query(
      `SELECT j.id::text, j.job_type, j.status, j.idempotency_key, j.correlation_id,
              j.attempts, j.max_attempts, j.last_error, j.scheduled_at, j.finished_at,
              j.created_at, j.client_id::text, c.code AS client_code,
              COALESCE(j.payload->>'channel', j.payload->'lead'->>'channel', '') AS channel
       FROM job_queue j
       LEFT JOIN clients c ON c.id = j.client_id
       WHERE ${clauses.join(' AND ')}
       ORDER BY j.created_at DESC
       LIMIT $${idx++} OFFSET $${idx}`,
      values,
    );

    return result.rows.map((row) => ({
      id: String(row.id),
      job_type: row.job_type ?? '',
      status: row.status ?? '',
      idempotency_key: row.idempotency_key ?? null,
      correlation_id: row.correlation_id ?? null,
      attempts: Number(row.attempts ?? 0),
      max_attempts: Number(row.max_attempts ?? 0),
      last_error: row.last_error ?? null,
      scheduled_at: iso(row.scheduled_at),
      finished_at: iso(row.finished_at),
      created_at: iso(row.created_at),
      client_id: row.client_id ?? null,
      client_code: row.client_code ?? null,
      channel: row.channel ?? null,
    }));
  }

  async listNotifications(params: {
    recipientId: string;
    unreadOnly: boolean;
    limit: number;
  }): Promise<{ rows: NotificationRow[]; unread: number }> {
    const clauses = ['recipient_id = $1'];
    const values: unknown[] = [params.recipientId];
    if (params.unreadOnly) {
      clauses.push('read_at IS NULL');
    }
    const result = await this.db.query(
      `SELECT id::text, category, title, body, link_url, read_at, created_at
       FROM notification_inbox
       WHERE ${clauses.join(' AND ')}
       ORDER BY created_at DESC
       LIMIT $2`,
      [...values, params.limit],
    );
    const unreadResult = await this.db.query(
      `SELECT COUNT(*)::int AS c FROM notification_inbox
       WHERE recipient_id = $1 AND read_at IS NULL`,
      [params.recipientId],
    );
    const rows: NotificationRow[] = result.rows.map((row) => ({
      id: String(row.id),
      category: row.category ?? '',
      title: row.title ?? '',
      body: row.body ?? null,
      client_id: null,
      read: row.read_at != null,
      created_at: iso(row.created_at),
    }));
    return { rows, unread: Number(unreadResult.rows[0]?.c ?? 0) };
  }

  async listHubCampaignMaps(
    clientId: string,
    params: { channel?: string; activeOnly: boolean; limit: number },
  ): Promise<HubCampaignMapRow[]> {
    const clauses = ['client_id = $1::uuid'];
    const values: unknown[] = [clientId];
    let idx = 2;
    if (params.channel) {
      clauses.push(`channel = $${idx++}`);
      values.push(params.channel);
    }
    if (params.activeOnly) {
      clauses.push('active IS TRUE');
    }
    values.push(params.limit);

    const result = await this.db.query(
      `SELECT hub_campaign_id, channel, external_campaign_id, external_campaign_name,
              target_cpl_vnd, active, updated_at
       FROM hub_campaign_map
       WHERE ${clauses.join(' AND ')}
       ORDER BY external_campaign_name NULLS LAST, external_campaign_id
       LIMIT $${idx}`,
      values,
    );

    return result.rows.map((row) => {
      const hubId =
        row.hub_campaign_id != null ? Math.trunc(Number(row.hub_campaign_id)) : null;
      return {
        hub_campaign_id: hubId,
        channel: row.channel ?? 'meta',
        external_campaign_id: row.external_campaign_id ?? null,
        external_campaign_name: row.external_campaign_name ?? null,
        target_cpl_vnd:
          row.target_cpl_vnd != null ? Math.round(Number(row.target_cpl_vnd) * 100) / 100 : null,
        active: Boolean(row.active),
        updated_at: iso(row.updated_at),
        hub_url: hubId != null ? `/crm/hub?campaign_id=${hubId}` : '/crm/hub',
      };
    });
  }

  async listHubCampaignMapsGlobal(params: {
    clientId?: string;
    campaignId?: number;
    limit: number;
  }): Promise<HubCampaignGlobalRow[]> {
    const clauses = ['1=1'];
    const values: unknown[] = [];
    let idx = 1;
    if (params.clientId) {
      clauses.push(`hcm.client_id = $${idx++}::uuid`);
      values.push(params.clientId);
    }
    if (params.campaignId != null) {
      clauses.push(`hcm.hub_campaign_id = $${idx++}`);
      values.push(params.campaignId);
    }
    values.push(params.limit);

    const result = await this.db.query(
      `SELECT hcm.hub_campaign_id, hcm.channel, hcm.external_campaign_id, hcm.external_campaign_name,
              hcm.target_cpl_vnd, hcm.active, hcm.updated_at,
              hcm.client_id::text, c.code AS client_code, c.name AS client_name
       FROM hub_campaign_map hcm
       JOIN clients c ON c.id = hcm.client_id
       WHERE ${clauses.join(' AND ')}
       ORDER BY c.code, hcm.external_campaign_name NULLS LAST
       LIMIT $${idx}`,
      values,
    );

    return result.rows.map((row) => {
      const hubId =
        row.hub_campaign_id != null ? Math.trunc(Number(row.hub_campaign_id)) : null;
      return {
        hub_campaign_id: hubId,
        channel: row.channel ?? 'meta',
        external_campaign_id: row.external_campaign_id ?? null,
        external_campaign_name: row.external_campaign_name ?? null,
        target_cpl_vnd:
          row.target_cpl_vnd != null ? Math.round(Number(row.target_cpl_vnd) * 100) / 100 : null,
        active: Boolean(row.active),
        updated_at: iso(row.updated_at),
        hub_url: hubId != null ? `/crm/hub?campaign_id=${hubId}` : '/crm/hub',
        client_id: String(row.client_id),
        client_code: row.client_code ?? null,
        client_name: row.client_name ?? null,
      };
    });
  }

  async facebookHubSummary(params: {
    windowDays: number;
    dateTo?: string;
    status?: string;
  }): Promise<{ clients: FacebookHubClientRow[]; summary: Record<string, unknown>; dateFrom: string; dateTo: string }> {
    const days = Math.max(1, Math.min(params.windowDays, 90));
    const end = params.dateTo ? new Date(params.dateTo) : new Date(Date.now() - 86400000);
    const start = new Date(end);
    start.setUTCDate(start.getUTCDate() - (days - 1));
    const dateFrom = start.toISOString().slice(0, 10);
    const dateTo = end.toISOString().slice(0, 10);

    const clientClauses = ['1=1'];
    const sqlParams: unknown[] = [dateFrom, dateTo];
    let idx = 3;
    if (params.status) {
      clientClauses.push(`c.status = $${idx++}`);
      sqlParams.push(params.status);
    }

    const result = await this.db.query(
      `WITH perf AS (
         SELECT dp.client_id,
                SUM(dp.spend) AS spend,
                SUM(dp.leads_crm) AS leads_crm,
                COUNT(DISTINCT dp.external_campaign_id) AS campaigns,
                COUNT(DISTINCT dp.external_campaign_id)
                  FILTER (WHERE dp.hub_campaign_map_id IS NULL) AS unmapped_campaigns,
                COUNT(*) FILTER (
                  WHERE hcm.target_cpl_vnd IS NOT NULL
                    AND dp.leads_crm > 0
                    AND (dp.spend / dp.leads_crm) > hcm.target_cpl_vnd
                ) AS over_target_rows
         FROM daily_performance dp
         LEFT JOIN hub_campaign_map hcm ON hcm.id = dp.hub_campaign_map_id
         WHERE dp.channel = 'meta'
           AND dp.performance_date BETWEEN $1::date AND $2::date
         GROUP BY dp.client_id
       ),
       meta_acct AS (
         SELECT cca.client_id,
                COUNT(*) FILTER (WHERE cca.channel = 'meta') AS meta_account_count,
                BOOL_OR(cca.channel = 'meta' AND cca.access_token_encrypted IS NOT NULL) AS meta_has_token
         FROM client_channel_accounts cca
         GROUP BY cca.client_id
       )
       SELECT c.id::text, c.code, c.name, c.status, c.owner_am_id,
              COALESCE(ma.meta_account_count, 0) AS meta_account_count,
              COALESCE(ma.meta_has_token, FALSE) AS meta_has_token,
              COALESCE(p.spend, 0) AS spend,
              COALESCE(p.leads_crm, 0) AS leads_crm,
              COALESCE(p.campaigns, 0) AS campaigns,
              COALESCE(p.unmapped_campaigns, 0) AS unmapped_campaigns,
              COALESCE(p.over_target_rows, 0) AS over_target_rows
       FROM clients c
       LEFT JOIN meta_acct ma ON ma.client_id = c.id
       LEFT JOIN perf p ON p.client_id = c.id
       WHERE ${clientClauses.join(' AND ')}
         AND (
           COALESCE(ma.meta_account_count, 0) > 0
           OR COALESCE(p.spend, 0) > 0
           OR COALESCE(p.leads_crm, 0) > 0
           OR c.status IN ('active', 'onboarding')
         )
       ORDER BY COALESCE(p.spend, 0) DESC, c.code ASC
       LIMIT 200`,
      sqlParams,
    );

    const clients: FacebookHubClientRow[] = [];
    let totalSpend = 0;
    let totalLeads = 0;
    let overTarget = 0;
    let unmapped = 0;

    for (const row of result.rows) {
      const spend = Number(row.spend ?? 0);
      const leads = Math.trunc(Number(row.leads_crm ?? 0));
      totalSpend += spend;
      totalLeads += leads;
      overTarget += Math.trunc(Number(row.over_target_rows ?? 0));
      unmapped += Math.trunc(Number(row.unmapped_campaigns ?? 0));
      clients.push({
        id: String(row.id),
        code: row.code ?? null,
        name: row.name ?? null,
        status: row.status ?? null,
        owner_am_id: row.owner_am_id ?? null,
        meta_account_count: Math.trunc(Number(row.meta_account_count ?? 0)),
        spend: Math.round(spend * 100) / 100,
        leads_crm: leads,
        cpl: computeCpl(spend, leads),
        campaigns: Math.trunc(Number(row.campaigns ?? 0)),
        unmapped_campaigns: Math.trunc(Number(row.unmapped_campaigns ?? 0)),
        over_target_rows: Math.trunc(Number(row.over_target_rows ?? 0)),
        meta_has_token: Boolean(row.meta_has_token),
        token_status: Boolean(row.meta_has_token) ? 'ok' : 'missing',
      });
    }

    const summary = {
      meta_clients: clients.length,
      total_spend: Math.round(totalSpend * 100) / 100,
      total_leads: totalLeads,
      avg_cpl: computeCpl(totalSpend, totalLeads),
      over_target_rows: overTarget,
      unmapped_campaigns: unmapped,
    };

    return { clients, summary, dateFrom, dateTo };
  }
}
