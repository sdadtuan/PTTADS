import { Injectable, OnModuleDestroy } from '@nestjs/common';
import { Pool } from 'pg';
import { AppConfigService } from '../config/app-config.service';
import {
  computeTokenStatus,
  encryptAccessToken,
  TokenVaultError,
  vaultConfigured,
} from './token-vault.util';
import {
  AgencyChannelAccount,
  AgencyClientDetail,
  AgencyClientRow,
  FacebookHubClientRow,
  GoogleHubClientRow,
  HubCampaignGlobalRow,
  HubCampaignMapRow,
  JobRow,
  NotificationRow,
} from './agency.types';
import {
  FacebookHubCampaignExportRow,
  resolveFacebookHubDateWindow,
} from './facebook-hub.util';

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
    const vaultReady = await this.vaultColumnsReady();
    const result = await this.db.query(
      vaultReady
        ? `SELECT id::text, channel, external_account_id, display_name, status,
                  credential_ref, access_token_encrypted, token_expires_at, token_status, meta
           FROM client_channel_accounts
           WHERE client_id = $1::uuid
           ORDER BY channel, display_name NULLS LAST`
        : `SELECT id::text, channel, external_account_id, display_name, status
           FROM client_channel_accounts
           WHERE client_id = $1::uuid
           ORDER BY channel, display_name NULLS LAST`,
      [clientId],
    );
    return result.rows.map((row) => this.mapChannelAccountRow(row, vaultReady));
  }

  private mapChannelAccountRow(row: Record<string, unknown>, vaultReady: boolean): AgencyChannelAccount {
    const base: AgencyChannelAccount = {
      id: String(row.id),
      channel: String(row.channel ?? ''),
      external_account_id: (row.external_account_id as string | null) ?? null,
      display_name: (row.display_name as string | null) ?? null,
      status: (row.status as string | null) ?? null,
    };
    if (!vaultReady) {
      return base;
    }
    const cred = String(row.credential_ref ?? '').trim();
    const hasToken = Boolean(row.access_token_encrypted) || Boolean(cred);
    const expiresRaw = row.token_expires_at;
    const expires =
      expiresRaw instanceof Date
        ? expiresRaw
        : expiresRaw
          ? new Date(String(expiresRaw))
          : null;
    const tokenStatus = computeTokenStatus({
      hasToken,
      tokenStatus: row.token_status as string | null,
      tokenExpiresAt: expires,
    });
    const meta = row.meta as Record<string, unknown> | null;
    const pixelId =
      meta && typeof meta === 'object'
        ? String(meta.pixel_id ?? meta.meta_pixel_id ?? '').trim() || null
        : null;
    const facebookPageId =
      meta && typeof meta === 'object'
        ? normMetaPageId(String(meta.facebook_page_id ?? meta.page_id ?? ''))
        : null;
    return {
      ...base,
      credential_ref: cred || null,
      has_token: hasToken,
      token_status: tokenStatus,
      token_expires_at: expires ? expires.toISOString() : null,
      pixel_id: pixelId,
      facebook_page_id: facebookPageId,
    };
  }

  async vaultColumnsReady(): Promise<boolean> {
    try {
      const result = await this.db.query(
        `SELECT COUNT(*)::int AS c FROM information_schema.columns
         WHERE table_schema = 'public'
           AND table_name = 'client_channel_accounts'
           AND column_name = 'access_token_encrypted'`,
      );
      return Number(result.rows[0]?.c ?? 0) >= 1;
    } catch {
      return false;
    }
  }

  async fetchChannelAccount(clientId: string, accountId: string): Promise<AgencyChannelAccount | null> {
    const vaultReady = await this.vaultColumnsReady();
    const result = await this.db.query(
      vaultReady
        ? `SELECT id::text, channel, external_account_id, display_name, status,
                  credential_ref, access_token_encrypted, token_expires_at, token_status, meta
           FROM client_channel_accounts
           WHERE client_id = $1::uuid AND id = $2::uuid`
        : `SELECT id::text, channel, external_account_id, display_name, status
           FROM client_channel_accounts
           WHERE client_id = $1::uuid AND id = $2::uuid`,
      [clientId, accountId],
    );
    const row = result.rows[0];
    if (!row) return null;
    return this.mapChannelAccountRow(row, vaultReady);
  }

  async setChannelAccountToken(
    clientId: string,
    accountId: string,
    params: {
      access_token?: string;
      credential_ref?: string;
      token_expires_at?: string;
      revoke?: boolean;
    },
  ): Promise<AgencyChannelAccount> {
    if (!(await this.vaultColumnsReady())) {
      throw new Error('DDL v3 chưa apply — chạy ./scripts/apply_pg_ddl_v3.sh');
    }
    const existing = await this.fetchChannelAccount(clientId, accountId);
    if (!existing) {
      throw new Error('account_not_found');
    }

    if (params.revoke) {
      await this.db.query(
        `UPDATE client_channel_accounts
         SET access_token_encrypted = NULL,
             credential_ref = NULL,
             token_status = 'revoked',
             last_token_refresh_at = NOW(),
             updated_at = NOW()
         WHERE client_id = $1::uuid AND id = $2::uuid`,
        [clientId, accountId],
      );
      const out = await this.fetchChannelAccount(clientId, accountId);
      if (!out) throw new Error('account_not_found');
      return out;
    }

    const token = params.access_token?.trim() ?? '';
    const cred = params.credential_ref?.trim() ?? '';
    if (!token && !cred) {
      throw new Error('token_or_credential_required');
    }

    let encBlob: Buffer | null = null;
    if (token) {
      if (!vaultConfigured()) {
        throw new TokenVaultError('PTT_TOKEN_VAULT_KEY chưa cấu hình');
      }
      encBlob = encryptAccessToken(token);
    }

    const expiresAt = params.token_expires_at?.trim() || null;
    const status = computeTokenStatus({
      hasToken: Boolean(encBlob || cred),
      tokenExpiresAt: expiresAt ? new Date(expiresAt) : null,
    });

    await this.db.query(
      `UPDATE client_channel_accounts
       SET access_token_encrypted = COALESCE($3, access_token_encrypted),
           credential_ref = COALESCE($4, credential_ref),
           token_expires_at = COALESCE($5::timestamptz, token_expires_at),
           token_status = $6,
           last_token_refresh_at = NOW(),
           updated_at = NOW()
       WHERE client_id = $1::uuid AND id = $2::uuid`,
      [clientId, accountId, encBlob, cred || null, expiresAt, status],
    );
    const out = await this.fetchChannelAccount(clientId, accountId);
    if (!out) throw new Error('account_not_found');
    return out;
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
      link_url: row.link_url ?? null,
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
      `SELECT id::text AS map_id, hub_campaign_id, channel, external_campaign_id,
              external_campaign_name, external_account_id, target_cpl_vnd, active, updated_at
       FROM hub_campaign_map
       WHERE ${clauses.join(' AND ')}
       ORDER BY active DESC, external_campaign_name NULLS LAST, external_campaign_id
       LIMIT $${idx}`,
      values,
    );

    return result.rows.map((row) => this.mapHubCampaignRow(row));
  }

  /** Agency-native hub_campaign_id range (no SQLite Hub row required). */
  private static readonly AGENCY_HUB_ID_BASE = 9_000_000_000;

  private mapHubCampaignRow(row: Record<string, unknown>): HubCampaignMapRow {
    const hubId =
      row.hub_campaign_id != null ? Math.trunc(Number(row.hub_campaign_id)) : null;
    return {
      map_id: String(row.map_id ?? ''),
      hub_campaign_id: hubId,
      channel: String(row.channel ?? 'meta'),
      external_campaign_id: row.external_campaign_id != null ? String(row.external_campaign_id) : null,
      external_campaign_name: row.external_campaign_name != null ? String(row.external_campaign_name) : null,
      external_account_id: row.external_account_id != null ? String(row.external_account_id) : null,
      target_cpl_vnd:
        row.target_cpl_vnd != null ? Math.round(Number(row.target_cpl_vnd) * 100) / 100 : null,
      active: Boolean(row.active),
      updated_at: iso(row.updated_at),
      hub_url: hubId != null ? `/crm/hub?campaign_id=${hubId}` : '/crm/hub',
    };
  }

  async allocateAgencyHubCampaignId(): Promise<number> {
    const base = AgencyRepository.AGENCY_HUB_ID_BASE;
    const result = await this.db.query(
      `SELECT COALESCE(MAX(hub_campaign_id), $1::bigint) + 1 AS next_id
       FROM hub_campaign_map
       WHERE hub_campaign_id >= $1::bigint`,
      [base],
    );
    return Math.trunc(Number(result.rows[0]?.next_id ?? base + 1));
  }

  async resolveMetaAccountId(clientId: string): Promise<string | null> {
    const result = await this.db.query(
      `SELECT external_account_id
       FROM client_channel_accounts
       WHERE client_id = $1::uuid AND channel = 'meta' AND status = 'active'
       ORDER BY updated_at DESC
       LIMIT 1`,
      [clientId],
    );
    const row = result.rows[0];
    return row?.external_account_id ? String(row.external_account_id).trim() : null;
  }

  async createHubCampaignMap(params: {
    clientId: string;
    hubCampaignId: number;
    channel: string;
    externalCampaignId: string;
    externalCampaignName?: string | null;
    externalAccountId?: string | null;
    targetCplVnd?: number | null;
  }): Promise<HubCampaignMapRow> {
    const result = await this.db.query(
      `INSERT INTO hub_campaign_map (
         client_id, hub_campaign_id, channel,
         external_campaign_id, external_campaign_name,
         external_account_id, target_cpl_vnd, active, meta
       ) VALUES (
         $1::uuid, $2, $3,
         $4, $5,
         $6, $7, TRUE, '{"source":"agency_ui"}'::jsonb
       )
       RETURNING id::text AS map_id, hub_campaign_id, channel, external_campaign_id,
                 external_campaign_name, external_account_id, target_cpl_vnd, active, updated_at`,
      [
        params.clientId,
        params.hubCampaignId,
        params.channel,
        params.externalCampaignId,
        params.externalCampaignName?.trim() || null,
        params.externalAccountId?.trim() || null,
        params.targetCplVnd ?? null,
      ],
    );
    return this.mapHubCampaignRow(result.rows[0]);
  }

  async fetchHubCampaignMapById(
    mapId: string,
    clientId?: string,
  ): Promise<(HubCampaignMapRow & { client_id: string }) | null> {
    const clauses = ['hcm.id = $1::uuid'];
    const values: unknown[] = [mapId];
    if (clientId) {
      clauses.push('hcm.client_id = $2::uuid');
      values.push(clientId);
    }
    const result = await this.db.query(
      `SELECT hcm.id::text AS map_id, hcm.client_id::text, hcm.hub_campaign_id, hcm.channel,
              hcm.external_campaign_id, hcm.external_campaign_name, hcm.external_account_id,
              hcm.target_cpl_vnd, hcm.active, hcm.updated_at
       FROM hub_campaign_map hcm
       WHERE ${clauses.join(' AND ')}
       LIMIT 1`,
      values,
    );
    const row = result.rows[0];
    if (!row) return null;
    return {
      ...this.mapHubCampaignRow(row),
      client_id: String(row.client_id),
    };
  }

  async updateHubCampaignMapById(
    mapId: string,
    params: {
      clientId?: string;
      externalCampaignId?: string;
      externalCampaignName?: string | null;
      externalAccountId?: string | null;
      targetCplVnd?: number | null;
      active?: boolean;
    },
  ): Promise<HubCampaignMapRow | null> {
    const sets: string[] = ['updated_at = NOW()'];
    const values: unknown[] = [];
    let idx = 1;

    if (params.externalCampaignId !== undefined) {
      sets.push(`external_campaign_id = $${idx++}`);
      values.push(params.externalCampaignId);
    }
    if (params.externalCampaignName !== undefined) {
      sets.push(`external_campaign_name = $${idx++}`);
      values.push(params.externalCampaignName);
    }
    if (params.externalAccountId !== undefined) {
      sets.push(`external_account_id = $${idx++}`);
      values.push(params.externalAccountId);
    }
    if (params.targetCplVnd !== undefined) {
      sets.push(`target_cpl_vnd = $${idx++}`);
      values.push(params.targetCplVnd);
    }
    if (params.active !== undefined) {
      sets.push(`active = $${idx++}`);
      values.push(params.active);
    }

    const clauses = [`id = $${idx++}::uuid`];
    values.push(mapId);
    if (params.clientId) {
      clauses.push(`client_id = $${idx++}::uuid`);
      values.push(params.clientId);
    }

    const result = await this.db.query(
      `UPDATE hub_campaign_map
       SET ${sets.join(', ')}
       WHERE ${clauses.join(' AND ')}
       RETURNING id::text AS map_id, hub_campaign_id, channel, external_campaign_id,
                 external_campaign_name, external_account_id, target_cpl_vnd, active, updated_at`,
      values,
    );
    const row = result.rows[0];
    return row ? this.mapHubCampaignRow(row) : null;
  }

  async deleteHubCampaignMapById(mapId: string, clientId?: string): Promise<boolean> {
    const clauses = ['id = $1::uuid'];
    const values: unknown[] = [mapId];
    if (clientId) {
      clauses.push('client_id = $2::uuid');
      values.push(clientId);
    }
    const result = await this.db.query(
      `DELETE FROM hub_campaign_map WHERE ${clauses.join(' AND ')} RETURNING id`,
      values,
    );
    return (result.rowCount ?? 0) > 0;
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
      `SELECT hcm.id::text AS map_id, hcm.hub_campaign_id, hcm.channel, hcm.external_campaign_id,
              hcm.external_campaign_name, hcm.external_account_id, hcm.target_cpl_vnd, hcm.active,
              hcm.updated_at, hcm.client_id::text, c.code AS client_code, c.name AS client_name
       FROM hub_campaign_map hcm
       JOIN clients c ON c.id = hcm.client_id
       WHERE ${clauses.join(' AND ')}
       ORDER BY c.code, hcm.active DESC, hcm.external_campaign_name NULLS LAST
       LIMIT $${idx}`,
      values,
    );

    return result.rows.map((row) => ({
      ...this.mapHubCampaignRow(row),
      client_id: String(row.client_id),
      client_code: row.client_code != null ? String(row.client_code) : null,
      client_name: row.client_name != null ? String(row.client_name) : null,
    }));
  }

  async updateClient(
    clientId: string,
    fields: {
      name?: string;
      industry_slug?: string;
      owner_am_id?: string;
      notes?: string;
      status?: string;
    },
  ): Promise<AgencyClientRow | null> {
    const allowed: Record<string, string | null | undefined> = {
      name: fields.name?.trim(),
      industry_slug: fields.industry_slug?.trim(),
      owner_am_id: fields.owner_am_id?.trim(),
      notes: fields.notes?.trim(),
      status: fields.status?.trim(),
    };
    const sets: string[] = [];
    const values: unknown[] = [];
    let idx = 1;
    for (const [key, val] of Object.entries(allowed)) {
      if (val === undefined) continue;
      sets.push(`${key} = $${idx++}`);
      values.push(val || null);
    }
    if (!sets.length) {
      const existing = await this.fetchClient(clientId);
      return existing;
    }
    sets.push('updated_at = NOW()');
    values.push(clientId);
    const result = await this.db.query(
      `UPDATE clients SET ${sets.join(', ')} WHERE id = $${idx}::uuid
       RETURNING id::text, code, name, industry_slug, status, owner_am_id, notes, created_at, updated_at`,
      values,
    );
    const row = result.rows[0];
    if (!row) return null;
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
      channels: '',
    };
  }

  async listOnboardingItems(clientId: string): Promise<
    Array<{
      id: string;
      item_key: string;
      label: string;
      sort_order: number;
      completed: boolean;
      completed_at: string | null;
      completed_by: string | null;
      note: string | null;
    }>
  > {
    const result = await this.db.query(
      `SELECT id::text, item_key, label, sort_order, completed, completed_at, completed_by, note
       FROM client_onboarding_items
       WHERE client_id = $1::uuid
       ORDER BY sort_order ASC, item_key ASC`,
      [clientId],
    );
    return result.rows.map((row) => ({
      id: String(row.id),
      item_key: row.item_key ?? '',
      label: row.label ?? '',
      sort_order: Number(row.sort_order ?? 0),
      completed: Boolean(row.completed),
      completed_at: iso(row.completed_at),
      completed_by: row.completed_by ?? null,
      note: row.note ?? null,
    }));
  }

  async setOnboardingItem(
    clientId: string,
    itemKey: string,
    params: { completed: boolean; completed_by?: string; note?: string },
  ): Promise<boolean> {
    const result = await this.db.query(
      `UPDATE client_onboarding_items
       SET completed = $3,
           completed_at = CASE WHEN $3 THEN NOW() ELSE NULL END,
           completed_by = CASE WHEN $3 THEN $4 ELSE NULL END,
           note = COALESCE(NULLIF($5, ''), note)
       WHERE client_id = $1::uuid AND item_key = $2
       RETURNING id`,
      [
        clientId,
        itemKey,
        params.completed,
        params.completed_by?.trim() || null,
        params.note?.trim() ?? '',
      ],
    );
    return (result.rowCount ?? 0) > 0;
  }

  async addChannelAccount(
    clientId: string,
    params: {
      channel: string;
      external_account_id: string;
      display_name?: string;
      facebook_page_id?: string;
    },
  ): Promise<AgencyChannelAccount> {
    const channel = params.channel.trim().toLowerCase();
    let ext = params.external_account_id.trim();
    if (channel === 'meta') {
      ext = ext.replace(/\D/g, '') || ext;
    }
    const metaPatch = metaPagePatch(channel, params.facebook_page_id);
    const vaultReady = await this.vaultColumnsReady();
    const result = await this.db.query(
      vaultReady
        ? `INSERT INTO client_channel_accounts (
             client_id, channel, external_account_id, display_name, status, meta
           ) VALUES ($1::uuid, $2, $3, $4, 'active', COALESCE($5::jsonb, '{}'::jsonb))
           ON CONFLICT (client_id, channel, external_account_id)
           DO UPDATE SET
             display_name = COALESCE(NULLIF(EXCLUDED.display_name, ''), client_channel_accounts.display_name),
             status = 'active',
             meta = CASE
               WHEN $5::jsonb IS NOT NULL AND $5::jsonb <> '{}'::jsonb
               THEN COALESCE(client_channel_accounts.meta, '{}'::jsonb) || $5::jsonb
               ELSE client_channel_accounts.meta
             END,
             updated_at = NOW()
           RETURNING id::text, channel, external_account_id, display_name, status`
        : `INSERT INTO client_channel_accounts (
             client_id, channel, external_account_id, display_name, status
           ) VALUES ($1::uuid, $2, $3, $4, 'active')
           ON CONFLICT (client_id, channel, external_account_id)
           DO UPDATE SET
             display_name = COALESCE(NULLIF(EXCLUDED.display_name, ''), client_channel_accounts.display_name),
             status = 'active',
             updated_at = NOW()
           RETURNING id::text, channel, external_account_id, display_name, status`,
      vaultReady
        ? [clientId, channel, ext, params.display_name?.trim() || null, metaPatch ? JSON.stringify(metaPatch) : '{}']
        : [clientId, channel, ext, params.display_name?.trim() || null],
    );
    const row = result.rows[0];
    return {
      id: String(row.id),
      channel: row.channel ?? '',
      external_account_id: row.external_account_id ?? null,
      display_name: row.display_name ?? null,
      status: row.status ?? null,
    };
  }

  async updateChannelAccount(
    clientId: string,
    accountId: string,
    params: {
      display_name?: string;
      external_account_id?: string;
      status?: string;
      facebook_page_id?: string;
    },
  ): Promise<AgencyChannelAccount | null> {
    const existing = await this.fetchChannelAccount(clientId, accountId);
    if (!existing) return null;

    const sets: string[] = [];
    const values: unknown[] = [clientId, accountId];
    let idx = 3;

    if (params.display_name !== undefined) {
      sets.push(`display_name = $${idx++}`);
      values.push(params.display_name.trim() || null);
    }
    if (params.external_account_id !== undefined) {
      let ext = params.external_account_id.trim();
      if (!ext) throw new Error('external_account_id_required');
      if (existing.channel === 'meta') {
        ext = ext.replace(/\D/g, '') || ext;
      }
      sets.push(`external_account_id = $${idx++}`);
      values.push(ext);
    }
    if (params.status !== undefined) {
      sets.push(`status = $${idx++}`);
      values.push(params.status.trim());
    }
    const metaPatch = metaPagePatch(existing.channel, params.facebook_page_id);
    if (metaPatch) {
      sets.push(`meta = COALESCE(meta, '{}'::jsonb) || $${idx++}::jsonb`);
      values.push(JSON.stringify(metaPatch));
    }
    if (!sets.length) return existing;

    sets.push('updated_at = NOW()');
    await this.db.query(
      `UPDATE client_channel_accounts SET ${sets.join(', ')}
       WHERE client_id = $1::uuid AND id = $2::uuid`,
      values,
    );
    return this.fetchChannelAccount(clientId, accountId);
  }

  async deleteChannelAccount(clientId: string, accountId: string): Promise<boolean> {
    const result = await this.db.query(
      `DELETE FROM client_channel_accounts WHERE client_id = $1::uuid AND id = $2::uuid`,
      [clientId, accountId],
    );
    return (result.rowCount ?? 0) > 0;
  }

  async replayJob(jobId: string): Promise<{ id: string; status: string; replayed: boolean } | null> {
    const result = await this.db.query(
      `UPDATE job_queue
       SET status = 'pending', scheduled_at = NOW(), started_at = NULL,
           finished_at = NULL, last_error = NULL, updated_at = NOW()
       WHERE id = $1::uuid AND status = 'dead'
       RETURNING id::text, status`,
      [jobId],
    );
    const row = result.rows[0];
    if (!row) return null;
    return { id: String(row.id), status: String(row.status), replayed: true };
  }

  async markNotificationRead(notificationId: string, recipientId: string): Promise<boolean> {
    const result = await this.db.query(
      `UPDATE notification_inbox SET read_at = NOW()
       WHERE id = $1::uuid AND recipient_id = $2 AND read_at IS NULL`,
      [notificationId, recipientId],
    );
    return (result.rowCount ?? 0) > 0;
  }

  async markAllNotificationsRead(recipientId: string): Promise<number> {
    const result = await this.db.query(
      `UPDATE notification_inbox SET read_at = NOW()
       WHERE recipient_id = $1 AND read_at IS NULL`,
      [recipientId],
    );
    return result.rowCount ?? 0;
  }

  async listKpiDefinitions(): Promise<
    Array<{
      code: string;
      name: string;
      formula: string;
      granularity: string | null;
      description: string | null;
    }>
  > {
    const result = await this.db.query(
      `SELECT code, name, formula, granularity, description
       FROM kpi_definitions ORDER BY code`,
    );
    return result.rows.map((row) => ({
      code: row.code ?? '',
      name: row.name ?? '',
      formula: row.formula ?? '',
      granularity: row.granularity ?? null,
      description: row.description ?? null,
    }));
  }

  async createKpiDefinition(body: {
    code: string;
    name: string;
    formula: string;
    granularity?: string;
    description?: string;
  }): Promise<{ code: string; name: string; formula: string; granularity: string | null; description: string | null }> {
    const code = body.code.trim().toUpperCase();
    await this.db.query(
      `INSERT INTO kpi_definitions (code, name, formula, granularity, description)
       VALUES ($1, $2, $3, $4, $5)`,
      [
        code,
        body.name.trim(),
        body.formula.trim(),
        body.granularity?.trim() || null,
        body.description?.trim() || null,
      ],
    );
    return {
      code,
      name: body.name.trim(),
      formula: body.formula.trim(),
      granularity: body.granularity?.trim() || null,
      description: body.description?.trim() || null,
    };
  }

  async updateKpiDefinition(
    code: string,
    body: { name?: string; formula?: string; granularity?: string; description?: string },
  ): Promise<boolean> {
    const sets: string[] = [];
    const values: unknown[] = [];
    let idx = 1;
    if (body.name !== undefined) {
      sets.push(`name = $${idx++}`);
      values.push(body.name.trim());
    }
    if (body.formula !== undefined) {
      sets.push(`formula = $${idx++}`);
      values.push(body.formula.trim());
    }
    if (body.granularity !== undefined) {
      sets.push(`granularity = $${idx++}`);
      values.push(body.granularity.trim() || null);
    }
    if (body.description !== undefined) {
      sets.push(`description = $${idx++}`);
      values.push(body.description.trim() || null);
    }
    if (!sets.length) return true;
    values.push(code.trim().toUpperCase());
    const result = await this.db.query(
      `UPDATE kpi_definitions SET ${sets.join(', ')} WHERE code = $${idx}`,
      values,
    );
    return (result.rowCount ?? 0) > 0;
  }

  async deleteKpiDefinition(code: string): Promise<boolean> {
    const result = await this.db.query(`DELETE FROM kpi_definitions WHERE code = $1`, [
      code.trim().toUpperCase(),
    ]);
    return (result.rowCount ?? 0) > 0;
  }

  async listClientLeads(clientId: string, limit = 50): Promise<
    Array<{
      id: string;
      full_name: string | null;
      phone: string | null;
      email: string | null;
      status: string | null;
      channel: string | null;
      created_at: string | null;
    }>
  > {
    try {
      const result = await this.db.query(
        `SELECT id::text, full_name, phone, email, status, channel, created_at
         FROM crm_leads
         WHERE agency_client_id = $1::uuid
         ORDER BY created_at DESC
         LIMIT $2`,
        [clientId, limit],
      );
      return result.rows.map((row) => ({
        id: String(row.id),
        full_name: row.full_name ?? null,
        phone: row.phone ?? null,
        email: row.email ?? null,
        status: row.status ?? null,
        channel: row.channel ?? null,
        created_at: iso(row.created_at),
      }));
    } catch {
      return [];
    }
  }

  async updateHubCampaignMap(params: {
    clientId: string;
    hubCampaignId: number;
    externalCampaignId: string;
  }): Promise<{ map_id: string; external_campaign_id: string } | null> {
    const result = await this.db.query(
      `UPDATE hub_campaign_map
       SET external_campaign_id = $3, updated_at = NOW()
       WHERE client_id = $1::uuid AND hub_campaign_id = $2
       RETURNING id::text, external_campaign_id`,
      [params.clientId, params.hubCampaignId, params.externalCampaignId],
    );
    const row = result.rows[0];
    if (!row) return null;
    return {
      map_id: String(row.id),
      external_campaign_id: String(row.external_campaign_id),
    };
  }

  async facebookHubSummary(params: {
    windowDays?: number;
    dateTo?: string;
    dateFrom?: string;
    status?: string;
    clientId?: string;
    q?: string;
  }): Promise<{ clients: FacebookHubClientRow[]; summary: Record<string, unknown>; dateFrom: string; dateTo: string; windowDays: number }> {
    const { dateFrom, dateTo, windowDays } = resolveFacebookHubDateWindow({
      days: params.windowDays,
      dateTo: params.dateTo,
      dateFrom: params.dateFrom,
    });

    const clientClauses = ['1=1'];
    const sqlParams: unknown[] = [dateFrom, dateTo];
    let idx = 3;
    if (params.status) {
      clientClauses.push(`c.status = $${idx++}`);
      sqlParams.push(params.status);
    }
    if (params.clientId) {
      clientClauses.push(`c.id = $${idx++}::uuid`);
      sqlParams.push(params.clientId);
    }
    if (params.q) {
      clientClauses.push(`(c.code ILIKE $${idx} OR c.name ILIKE $${idx})`);
      sqlParams.push(`%${params.q}%`);
      idx++;
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

    return { clients, summary, dateFrom, dateTo, windowDays };
  }

  async googleHubSummary(params: {
    windowDays?: number;
    dateTo?: string;
    dateFrom?: string;
    status?: string;
    clientId?: string;
    q?: string;
  }): Promise<{ clients: GoogleHubClientRow[]; summary: Record<string, unknown>; dateFrom: string; dateTo: string; windowDays: number }> {
    const { dateFrom, dateTo, windowDays } = resolveFacebookHubDateWindow({
      days: params.windowDays,
      dateTo: params.dateTo,
      dateFrom: params.dateFrom,
    });

    const clientClauses = ['1=1'];
    const sqlParams: unknown[] = [dateFrom, dateTo];
    let idx = 3;
    if (params.status) {
      clientClauses.push(`c.status = $${idx++}`);
      sqlParams.push(params.status);
    }
    if (params.clientId) {
      clientClauses.push(`c.id = $${idx++}::uuid`);
      sqlParams.push(params.clientId);
    }
    if (params.q) {
      clientClauses.push(`(c.code ILIKE $${idx} OR c.name ILIKE $${idx})`);
      sqlParams.push(`%${params.q}%`);
      idx++;
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
         WHERE dp.channel = 'google'
           AND dp.performance_date BETWEEN $1::date AND $2::date
         GROUP BY dp.client_id
       ),
       google_acct AS (
         SELECT cca.client_id,
                COUNT(*) FILTER (WHERE cca.channel = 'google') AS google_account_count,
                BOOL_OR(cca.channel = 'google' AND cca.access_token_encrypted IS NOT NULL) AS google_has_token
         FROM client_channel_accounts cca
         GROUP BY cca.client_id
       )
       SELECT c.id::text, c.code, c.name, c.status, c.owner_am_id,
              COALESCE(ga.google_account_count, 0) AS google_account_count,
              COALESCE(ga.google_has_token, FALSE) AS google_has_token,
              COALESCE(p.spend, 0) AS spend,
              COALESCE(p.leads_crm, 0) AS leads_crm,
              COALESCE(p.campaigns, 0) AS campaigns,
              COALESCE(p.unmapped_campaigns, 0) AS unmapped_campaigns,
              COALESCE(p.over_target_rows, 0) AS over_target_rows
       FROM clients c
       LEFT JOIN google_acct ga ON ga.client_id = c.id
       LEFT JOIN perf p ON p.client_id = c.id
       WHERE ${clientClauses.join(' AND ')}
         AND (
           COALESCE(ga.google_account_count, 0) > 0
           OR COALESCE(p.spend, 0) > 0
           OR COALESCE(p.leads_crm, 0) > 0
           OR c.status IN ('active', 'onboarding')
         )
       ORDER BY COALESCE(p.spend, 0) DESC, c.code ASC
       LIMIT 200`,
      sqlParams,
    );

    const clients: GoogleHubClientRow[] = [];
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
        google_account_count: Math.trunc(Number(row.google_account_count ?? 0)),
        spend: Math.round(spend * 100) / 100,
        leads_crm: leads,
        cpl: computeCpl(spend, leads),
        campaigns: Math.trunc(Number(row.campaigns ?? 0)),
        unmapped_campaigns: Math.trunc(Number(row.unmapped_campaigns ?? 0)),
        over_target_rows: Math.trunc(Number(row.over_target_rows ?? 0)),
        google_has_token: Boolean(row.google_has_token),
        token_status: Boolean(row.google_has_token) ? 'ok' : 'missing',
      });
    }

    const summary = {
      google_clients: clients.length,
      total_spend: Math.round(totalSpend * 100) / 100,
      total_leads: totalLeads,
      avg_cpl: computeCpl(totalSpend, totalLeads),
      over_target_rows: overTarget,
      unmapped_campaigns: unmapped,
    };

    return { clients, summary, dateFrom, dateTo, windowDays };
  }

  async facebookHubCampaignExport(params: {
    dateFrom: string;
    dateTo: string;
    clientId?: string;
    status?: string;
    q?: string;
  }): Promise<FacebookHubCampaignExportRow[]> {
    const clauses = [`dp.channel = 'meta'`, `dp.performance_date BETWEEN $1::date AND $2::date`];
    const sqlParams: unknown[] = [params.dateFrom, params.dateTo];
    let idx = 3;

    if (params.clientId) {
      clauses.push(`dp.client_id = $${idx++}::uuid`);
      sqlParams.push(params.clientId);
    }
    if (params.status) {
      clauses.push(`c.status = $${idx++}`);
      sqlParams.push(params.status);
    }
    if (params.q) {
      clauses.push(`(c.code ILIKE $${idx} OR c.name ILIKE $${idx})`);
      sqlParams.push(`%${params.q}%`);
      idx++;
    }

    const result = await this.db.query(
      `SELECT c.id::text AS client_id,
              c.code AS client_code,
              c.name AS client_name,
              dp.external_campaign_id,
              MAX(hcm.external_campaign_name) AS external_campaign_name,
              SUM(dp.spend) AS spend,
              SUM(dp.leads_crm) AS leads_crm,
              MAX(hcm.target_cpl_vnd) AS target_cpl_vnd,
              BOOL_OR(dp.hub_campaign_map_id IS NOT NULL) AS hub_mapped
       FROM daily_performance dp
       JOIN clients c ON c.id = dp.client_id
       LEFT JOIN hub_campaign_map hcm ON hcm.id = dp.hub_campaign_map_id
       WHERE ${clauses.join(' AND ')}
       GROUP BY c.id, c.code, c.name, dp.external_campaign_id
       ORDER BY SUM(dp.spend) DESC, c.code ASC, dp.external_campaign_id ASC
       LIMIT 5000`,
      sqlParams,
    );

    return result.rows.map((row) => {
      const spend = Number(row.spend ?? 0);
      const leads = Math.trunc(Number(row.leads_crm ?? 0));
      return {
        client_id: String(row.client_id),
        client_code: row.client_code ?? null,
        client_name: row.client_name ?? null,
        external_campaign_id: row.external_campaign_id ?? null,
        external_campaign_name: row.external_campaign_name ?? null,
        spend: Math.round(spend * 100) / 100,
        leads_crm: leads,
        cpl: computeCpl(spend, leads),
        target_cpl_vnd:
          row.target_cpl_vnd != null ? Math.trunc(Number(row.target_cpl_vnd)) : null,
        hub_mapped: Boolean(row.hub_mapped),
      };
    });
  }

  async googleHubCampaignExport(params: {
    dateFrom: string;
    dateTo: string;
    clientId?: string;
    status?: string;
    q?: string;
  }): Promise<FacebookHubCampaignExportRow[]> {
    const clauses = [`dp.channel = 'google'`, `dp.performance_date BETWEEN $1::date AND $2::date`];
    const sqlParams: unknown[] = [params.dateFrom, params.dateTo];
    let idx = 3;

    if (params.clientId) {
      clauses.push(`dp.client_id = $${idx++}::uuid`);
      sqlParams.push(params.clientId);
    }
    if (params.status) {
      clauses.push(`c.status = $${idx++}`);
      sqlParams.push(params.status);
    }
    if (params.q) {
      clauses.push(`(c.code ILIKE $${idx} OR c.name ILIKE $${idx})`);
      sqlParams.push(`%${params.q}%`);
      idx++;
    }

    const result = await this.db.query(
      `SELECT c.id::text AS client_id,
              c.code AS client_code,
              c.name AS client_name,
              dp.external_campaign_id,
              MAX(hcm.external_campaign_name) AS external_campaign_name,
              SUM(dp.spend) AS spend,
              SUM(dp.leads_crm) AS leads_crm,
              MAX(hcm.target_cpl_vnd) AS target_cpl_vnd,
              BOOL_OR(dp.hub_campaign_map_id IS NOT NULL) AS hub_mapped
       FROM daily_performance dp
       JOIN clients c ON c.id = dp.client_id
       LEFT JOIN hub_campaign_map hcm ON hcm.id = dp.hub_campaign_map_id
       WHERE ${clauses.join(' AND ')}
       GROUP BY c.id, c.code, c.name, dp.external_campaign_id
       ORDER BY SUM(dp.spend) DESC, c.code ASC, dp.external_campaign_id ASC
       LIMIT 5000`,
      sqlParams,
    );

    return result.rows.map((row) => {
      const spend = Number(row.spend ?? 0);
      const leads = Math.trunc(Number(row.leads_crm ?? 0));
      return {
        client_id: String(row.client_id),
        client_code: row.client_code ?? null,
        client_name: row.client_name ?? null,
        external_campaign_id: row.external_campaign_id ?? null,
        external_campaign_name: row.external_campaign_name ?? null,
        spend: Math.round(spend * 100) / 100,
        leads_crm: leads,
        cpl: computeCpl(spend, leads),
        target_cpl_vnd:
          row.target_cpl_vnd != null ? Math.trunc(Number(row.target_cpl_vnd)) : null,
        hub_mapped: Boolean(row.hub_mapped),
      };
    });
  }
}

function normMetaPageId(raw: string): string | null {
  const id = String(raw ?? '')
    .replace(/\D/g, '')
    .trim();
  return id || null;
}

function metaPagePatch(channel: string, facebookPageId?: string): Record<string, string> | null {
  if (channel.trim().toLowerCase() !== 'meta') return null;
  const pageId = normMetaPageId(facebookPageId ?? '');
  if (!pageId) return null;
  return { facebook_page_id: pageId, page_id: pageId };
}
