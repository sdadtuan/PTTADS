import { Injectable, OnModuleDestroy } from '@nestjs/common';
import { Pool } from 'pg';
import { AppConfigService } from '../config/app-config.service';
import { decryptAccessToken } from '../agency/token-vault.util';

const UUID_RE = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i;

@Injectable()
export class MetaWebhookRepository implements OnModuleDestroy {
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

  normalizeClientUuid(clientId: string | undefined): string | null {
    const text = String(clientId ?? '').trim();
    if (!text || text === 'unknown') return null;
    if (!UUID_RE.test(text)) return null;
    return text.toLowerCase();
  }

  defaultClientIdFromEnv(): string | null {
    return this.normalizeClientUuid(process.env.PTT_META_WEBHOOK_DEFAULT_CLIENT_ID?.trim());
  }

  async resolveClientId(params: {
    headerClientId?: string;
    pageIds?: string[];
    formIds?: string[];
  }): Promise<string | null> {
    const fromHeader = this.normalizeClientUuid(params.headerClientId);
    if (fromHeader) return fromHeader;

    for (const pageId of params.pageIds ?? []) {
      const id = normDigits(pageId);
      if (!id) continue;
      const resolved = await this.lookupClientByPageId(id);
      if (resolved) return resolved;
    }

    for (const formId of params.formIds ?? []) {
      const id = normDigits(formId);
      if (!id) continue;
      const resolved = await this.lookupClientByFormId(id);
      if (resolved) return resolved;
    }

    return this.defaultClientIdFromEnv();
  }

  private async lookupClientByPageId(pageId: string): Promise<string | null> {
    const result = await this.db.query(
      `SELECT client_id::text
       FROM client_channel_accounts
       WHERE channel = 'meta'
         AND status = 'active'
         AND (
           meta->>'facebook_page_id' = $1
           OR meta->>'page_id' = $1
           OR regexp_replace(external_account_id, '\\D', '', 'g') = $1
           OR external_account_id = $1
         )
       ORDER BY updated_at DESC
       LIMIT 1`,
      [pageId],
    );
    const row = result.rows[0];
    return row?.client_id ? this.normalizeClientUuid(String(row.client_id)) : null;
  }

  private async lookupClientByFormId(formId: string): Promise<string | null> {
    const result = await this.db.query(
      `SELECT client_id::text
       FROM client_channel_accounts
       WHERE channel = 'meta'
         AND status = 'active'
         AND (
           meta->>'facebook_form_id' = $1
           OR meta @> jsonb_build_object('facebook_form_ids', jsonb_build_array($1))
         )
       ORDER BY updated_at DESC
       LIMIT 1`,
      [formId],
    );
    const row = result.rows[0];
    return row?.client_id ? this.normalizeClientUuid(String(row.client_id)) : null;
  }

  async resolveClientIdByAdAccount(adAccountId: string | null | undefined): Promise<string | null> {
    const account = normalizeAdAccountId(adAccountId);
    if (!account) return this.defaultClientIdFromEnv();

    const digits = account.replace(/\D/g, '');
    const result = await this.db.query(
      `SELECT client_id::text
       FROM client_channel_accounts
       WHERE channel = 'meta'
         AND status = 'active'
         AND (
           external_account_id = $1
           OR external_account_id = $2
           OR regexp_replace(external_account_id, '\\D', '', 'g') = $3
           OR meta->>'ad_account_id' = $1
         )
       ORDER BY updated_at DESC
       LIMIT 1`,
      [account, digits ? `act_${digits}` : account, digits],
    );
    const row = result.rows[0];
    return row?.client_id
      ? this.normalizeClientUuid(String(row.client_id))
      : this.defaultClientIdFromEnv();
  }

  async pgMetaAlertsReady(): Promise<boolean> {
    try {
      const result = await this.db.query(
        `SELECT 1 FROM information_schema.tables
         WHERE table_schema = 'public' AND table_name = 'meta_alerts'
         LIMIT 1`,
      );
      return (result.rowCount ?? 0) > 0;
    } catch {
      return false;
    }
  }

  async insertOpsAlert(params: {
    clientId: string;
    alertType: string;
    severity: string;
    message: string;
    externalCampaignId: string | null;
    dedupeKey: string;
  }): Promise<{ ok: boolean; created?: boolean; alert_id?: string; dedupe_key?: string; idempotent?: boolean }> {
    const result = await this.db.query(
      `INSERT INTO meta_alerts (
         client_id, channel, external_campaign_id, alert_type, severity,
         metric_value, threshold_value, message, performance_date, dedupe_key
       ) VALUES (
         $1::uuid, 'meta', $2, $3, $4,
         NULL, NULL, $5, CURRENT_DATE, $6
       )
       ON CONFLICT (dedupe_key) DO NOTHING
       RETURNING id::text`,
      [
        params.clientId,
        params.externalCampaignId,
        params.alertType,
        params.severity,
        params.message,
        params.dedupeKey,
      ],
    );
    if ((result.rowCount ?? 0) > 0) {
      return {
        ok: true,
        created: true,
        alert_id: String(result.rows[0]?.id),
        dedupe_key: params.dedupeKey,
      };
    }
    return { ok: true, created: false, dedupe_key: params.dedupeKey, idempotent: true };
  }

  async resolvePageAccessToken(clientId: string | null): Promise<string | null> {
    const global = cleanEnv(
      process.env.CRM_FACEBOOK_PAGE_ACCESS_TOKEN ?? process.env.FACEBOOK_PAGE_ACCESS_TOKEN,
    );
    if (!clientId) return global || null;

    try {
      const result = await this.db.query(
        `SELECT access_token_encrypted, credential_ref
         FROM client_channel_accounts
         WHERE client_id = $1::uuid
           AND channel = 'meta'
           AND status = 'active'
           AND access_token_encrypted IS NOT NULL
         ORDER BY updated_at DESC
         LIMIT 1`,
        [clientId],
      );
      const row = result.rows[0];
      if (row?.access_token_encrypted) {
        const plain = decryptAccessToken(row.access_token_encrypted as Buffer);
        if (plain) return plain;
      }
    } catch {
      /* fall back to global token */
    }
    return global || null;
  }
}

function normDigits(raw: string): string {
  return String(raw ?? '')
    .replace(/\D/g, '')
    .trim();
}

function normalizeAdAccountId(raw: unknown): string {
  const text = String(raw ?? '').trim();
  if (!text) return '';
  if (text.startsWith('act_')) return text;
  const digits = text.replace(/\D/g, '');
  if (digits) return `act_${digits}`;
  return text;
}

function cleanEnv(val: string | undefined): string {
  let s = String(val ?? '').trim();
  if (s.length >= 2 && (s.startsWith('"') || s.startsWith("'")) && s[0] === s.at(-1)) {
    s = s.slice(1, -1).trim();
  }
  return s.replace(/[\r\n\t]+/g, '');
}
