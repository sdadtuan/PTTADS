import { Injectable, OnModuleDestroy } from '@nestjs/common';
import { Pool } from 'pg';
import { AppConfigService } from '../config/app-config.service';
import type { ZaloFormSyncRow, ZaloLeadEventRow, ZaloLeadRow } from './zalo-leads.types';

function iso(value: unknown): string | null {
  if (value == null) return null;
  if (value instanceof Date) return value.toISOString();
  return String(value);
}

function parseMeta(raw: unknown): Record<string, unknown> {
  if (raw == null) return {};
  if (typeof raw === 'object' && !Array.isArray(raw)) return raw as Record<string, unknown>;
  try {
    return JSON.parse(String(raw)) as Record<string, unknown>;
  } catch {
    return {};
  }
}

function readFormIds(meta: Record<string, unknown>): string[] {
  const raw = meta.form_ids;
  if (!Array.isArray(raw)) return [];
  return raw.map((x) => String(x).trim()).filter(Boolean);
}

@Injectable()
export class ZaloLeadsRepository implements OnModuleDestroy {
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

  async tablesReady(): Promise<boolean> {
    try {
      const result = await this.db.query(
        `SELECT COUNT(*)::int AS c FROM information_schema.tables
         WHERE table_schema = 'public'
           AND table_name IN ('zalo_lead_form_sync_cursor', 'zalo_lead_events', 'crm_leads')`,
      );
      return Number(result.rows[0]?.c ?? 0) >= 3;
    } catch {
      return false;
    }
  }

  async listLeads(params: {
    clientId?: string;
    formId?: string;
    q?: string;
    limit?: number;
    offset?: number;
  }): Promise<{ rows: ZaloLeadRow[]; total: number }> {
    const clauses = [`lower(COALESCE(l.channel, '')) = 'zalo'`];
    const values: unknown[] = [];
    let idx = 1;

    if (params.clientId) {
      clauses.push(`l.agency_client_id = $${idx++}::uuid`);
      values.push(params.clientId);
    }
    if (params.formId) {
      clauses.push(`COALESCE(l.meta_json->>'form_id', '') = $${idx++}`);
      values.push(params.formId);
    }
    if (params.q?.trim()) {
      clauses.push(
        `(l.full_name ILIKE $${idx} OR l.phone ILIKE $${idx} OR l.email ILIKE $${idx} OR COALESCE(l.external_lead_id, '') ILIKE $${idx})`,
      );
      values.push(`%${params.q.trim()}%`);
      idx += 1;
    }

    const where = clauses.length ? `WHERE ${clauses.join(' AND ')}` : '';
    const limit = Math.min(Math.max(params.limit ?? 50, 1), 200);
    const offset = Math.max(params.offset ?? 0, 0);

    const countResult = await this.db.query(
      `SELECT COUNT(*)::int AS c FROM crm_leads l ${where}`,
      values,
    );
    const total = Number(countResult.rows[0]?.c ?? 0);

    const listResult = await this.db.query(
      `SELECT
         l.sqlite_lead_id::text AS id,
         l.full_name,
         l.phone,
         l.email,
         l.status,
         l.channel,
         l.external_lead_id,
         COALESCE(l.meta_json->>'form_id', '') AS form_id,
         COALESCE(l.meta_json->>'oa_id', '') AS oa_id,
         COALESCE(l.is_duplicate, FALSE) AS is_duplicate,
         l.created_at
       FROM crm_leads l
       ${where}
       ORDER BY l.created_at DESC NULLS LAST, l.sqlite_lead_id DESC
       LIMIT $${idx++} OFFSET $${idx++}`,
      [...values, limit, offset],
    );

    const rows: ZaloLeadRow[] = listResult.rows.map((row) => ({
      id: String(row.id),
      full_name: row.full_name ?? null,
      phone: row.phone ?? null,
      email: row.email ?? null,
      status: row.status ?? null,
      channel: row.channel ?? null,
      external_lead_id: row.external_lead_id ?? null,
      form_id: row.form_id || null,
      oa_id: row.oa_id || null,
      is_duplicate: Boolean(row.is_duplicate),
      created_at: iso(row.created_at),
    }));
    return { rows, total };
  }

  async listForms(params: { clientId?: string }): Promise<ZaloFormSyncRow[]> {
    const values: unknown[] = [];
    let clientFilter = '';
    if (params.clientId) {
      clientFilter = 'AND cca.client_id = $1::uuid';
      values.push(params.clientId);
    }

    const accounts = await this.db.query(
      `SELECT
         cca.id::text AS channel_account_id,
         cca.client_id::text,
         c.code AS client_code,
         c.name AS client_name,
         cca.external_account_id,
         cca.meta,
         (cca.access_token_encrypted IS NOT NULL OR cca.credential_ref IS NOT NULL) AS has_token
       FROM client_channel_accounts cca
       JOIN clients c ON c.id = cca.client_id
       WHERE cca.channel = 'zalo'
         AND COALESCE(cca.status, 'active') <> 'revoked'
         ${clientFilter}
       ORDER BY c.name ASC, cca.external_account_id ASC`,
      values,
    );

    const cursorResult = await this.db.query(
      `SELECT client_id::text, oa_id, form_id, last_form_data_id, last_polled_at, last_status, last_error
       FROM zalo_lead_form_sync_cursor
       ${params.clientId ? 'WHERE client_id = $1::uuid' : ''}`,
      params.clientId ? [params.clientId] : [],
    );
    const cursorMap = new Map<string, (typeof cursorResult.rows)[number]>();
    for (const row of cursorResult.rows) {
      cursorMap.set(`${row.client_id}:${row.oa_id}:${row.form_id}`, row);
    }

    const out: ZaloFormSyncRow[] = [];
    for (const acc of accounts.rows) {
      const meta = parseMeta(acc.meta);
      const oaId = String(acc.external_account_id ?? meta.oa_id ?? '').trim();
      const formIds = readFormIds(meta);
      for (const formId of formIds) {
        const key = `${acc.client_id}:${oaId}:${formId}`;
        const cursor = cursorMap.get(key);
        out.push({
          client_id: String(acc.client_id),
          client_code: acc.client_code ?? null,
          client_name: acc.client_name ?? null,
          oa_id: oaId,
          form_id: formId,
          channel_account_id: String(acc.channel_account_id),
          last_form_data_id: cursor?.last_form_data_id ?? null,
          last_polled_at: iso(cursor?.last_polled_at),
          last_status: cursor?.last_status ?? null,
          last_error: cursor?.last_error ?? null,
          has_token: Boolean(acc.has_token),
        });
      }
    }
    return out;
  }

  async listLeadEvents(leadId: string): Promise<ZaloLeadEventRow[]> {
    const result = await this.db.query(
      `SELECT id::text, lead_id::text, client_id::text, event_type, payload_json, created_at
       FROM zalo_lead_events
       WHERE lead_id = $1::bigint
       ORDER BY created_at ASC, id ASC`,
      [leadId],
    );
    return result.rows.map((row) => ({
      id: String(row.id),
      lead_id: row.lead_id ?? null,
      client_id: row.client_id ?? null,
      event_type: String(row.event_type ?? ''),
      payload_json: parseMeta(row.payload_json),
      created_at: iso(row.created_at),
    }));
  }

  async resolveFormContext(formId: string, clientId?: string): Promise<{
    client_id: string;
    oa_id: string;
    form_id: string;
  } | null> {
    const forms = await this.listForms({ clientId });
    const match = forms.find((f) => f.form_id === formId);
    if (!match) return null;
    return { client_id: match.client_id, oa_id: match.oa_id, form_id: match.form_id };
  }

  async countZaloLeads(clientId: string): Promise<number> {
    try {
      const result = await this.db.query(
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
