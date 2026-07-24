import { Injectable, OnModuleDestroy } from '@nestjs/common';
import { Pool } from 'pg';
import { AppConfigService } from '../config/app-config.service';
import {
  CapiEventRow,
  ConversionRuleRow,
  CreateConversionRuleBody,
  PatchConversionRuleBody,
  TrackingHealthAccountRow,
} from './meta-tracking.types';

@Injectable()
export class MetaTrackingRepository implements OnModuleDestroy {
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

  async pgCapiEventLogReady(): Promise<boolean> {
    try {
      const result = await this.db.query(
        `SELECT 1 FROM information_schema.tables
         WHERE table_schema = 'public' AND table_name = 'capi_event_log'
         LIMIT 1`,
      );
      return (result.rowCount ?? 0) > 0;
    } catch {
      return false;
    }
  }

  async countCapiByStatus(windowDays: number, clientId?: string): Promise<Record<string, number>> {
    const days = Math.min(Math.max(windowDays, 1), 90);
    const values: unknown[] = [days];
    let clientClause = '';
    if (clientId) {
      clientClause = ' AND client_id = $2::uuid';
      values.push(clientId);
    }
    const result = await this.db.query(
      `SELECT status, COUNT(*)::int AS c
       FROM capi_event_log
       WHERE created_at >= NOW() - ($1::text || ' days')::interval
       ${clientClause}
       GROUP BY status`,
      values,
    );
    const out: Record<string, number> = {};
    for (const row of result.rows) {
      out[String(row.status)] = Number(row.c ?? 0);
    }
    return out;
  }

  async avgCapiLatencyMs(windowDays: number, clientId?: string): Promise<number | null> {
    const days = Math.min(Math.max(windowDays, 1), 90);
    const values: unknown[] = [days];
    let clientClause = '';
    if (clientId) {
      clientClause = ' AND client_id = $2::uuid';
      values.push(clientId);
    }
    const result = await this.db.query(
      `SELECT AVG(EXTRACT(EPOCH FROM (sent_at - created_at)) * 1000)::float AS avg_ms
       FROM capi_event_log
       WHERE status = 'sent'
         AND sent_at IS NOT NULL
         AND created_at >= NOW() - ($1::text || ' days')::interval
         ${clientClause}`,
      values,
    );
    const avg = result.rows[0]?.avg_ms;
    return avg != null && Number.isFinite(Number(avg)) ? Number(avg) : null;
  }

  async listTrackingAccounts(clientId?: string): Promise<TrackingHealthAccountRow[]> {
    const values: unknown[] = [];
    let clientClause = '';
    if (clientId) {
      clientClause = ' AND cca.client_id = $1::uuid';
      values.push(clientId);
    }
    const result = await this.db.query(
      `SELECT
         cca.id::text AS channel_account_id,
         cca.client_id::text AS client_id,
         cca.meta,
         cca.status,
         c.code AS client_code,
         c.name AS client_name,
         (
           SELECT MAX(cel.sent_at)
           FROM capi_event_log cel
           WHERE cel.client_id = cca.client_id AND cel.status = 'sent'
         ) AS last_sent_at
       FROM client_channel_accounts cca
       JOIN clients c ON c.id = cca.client_id
       WHERE cca.channel = 'meta'
         AND COALESCE(cca.status, 'active') = 'active'
         ${clientClause}
       ORDER BY c.code NULLS LAST, cca.display_name NULLS LAST`,
      values,
    );
    return result.rows.map((row) => this.mapAccountRow(row));
  }

  private parseMeta(raw: unknown): Record<string, unknown> {
    if (raw && typeof raw === 'object' && !Array.isArray(raw)) {
      return raw as Record<string, unknown>;
    }
    return {};
  }

  private mapAccountRow(row: Record<string, unknown>): TrackingHealthAccountRow {
    const meta = this.parseMeta(row.meta);
    const pixelId = String(meta.pixel_id ?? meta.meta_pixel_id ?? '').trim() || null;
    const pageId = String(meta.facebook_page_id ?? meta.page_id ?? '').trim() || null;
    const capiRaw = meta.capi_enabled;
    const capiEnabled =
      capiRaw === false || capiRaw === '0' || capiRaw === 0
        ? false
        : pixelId
          ? true
          : false;
    const lastSent = row.last_sent_at
      ? new Date(String(row.last_sent_at)).toISOString()
      : null;
    return {
      client_id: String(row.client_id),
      channel_account_id: String(row.channel_account_id),
      client_code: row.client_code != null ? String(row.client_code) : null,
      client_name: row.client_name != null ? String(row.client_name) : null,
      pixel_id: pixelId,
      page_id: pageId,
      capi_enabled: capiEnabled,
      last_sent_at: lastSent,
      pixel_test_ok: null,
    };
  }

  async listCapiEvents(params: {
    clientId?: string;
    status?: string;
    eventName?: string;
    limit?: number;
    offset?: number;
  }): Promise<CapiEventRow[]> {
    const clauses: string[] = ['1=1'];
    const values: unknown[] = [];
    let idx = 1;

    if (params.clientId) {
      clauses.push(`cel.client_id = $${idx++}::uuid`);
      values.push(params.clientId);
    }
    if (params.status) {
      clauses.push(`cel.status = $${idx++}`);
      values.push(params.status);
    }
    if (params.eventName) {
      clauses.push(`cel.event_name = $${idx++}`);
      values.push(params.eventName);
    }

    const limit = Math.min(Math.max(params.limit ?? 50, 1), 200);
    const offset = Math.max(params.offset ?? 0, 0);
    values.push(limit, offset);

    const result = await this.db.query(
      `SELECT cel.*, c.code AS client_code, c.name AS client_name
       FROM capi_event_log cel
       JOIN clients c ON c.id = cel.client_id
       WHERE ${clauses.join(' AND ')}
       ORDER BY cel.created_at DESC
       LIMIT $${idx++} OFFSET $${idx}`,
      values,
    );
    return result.rows.map((row) => this.mapCapiEventRow(row));
  }

  private mapCapiEventRow(row: Record<string, unknown>): CapiEventRow {
    return {
      id: String(row.id),
      client_id: String(row.client_id),
      event_name: String(row.event_name),
      event_id: String(row.event_id),
      lead_id: row.lead_id != null ? Number(row.lead_id) : null,
      pixel_id: row.pixel_id != null ? String(row.pixel_id) : null,
      status: String(row.status),
      error_message: row.error_message != null ? String(row.error_message) : null,
      created_at: new Date(String(row.created_at)).toISOString(),
      sent_at: row.sent_at ? new Date(String(row.sent_at)).toISOString() : null,
      client_code: row.client_code != null ? String(row.client_code) : null,
      client_name: row.client_name != null ? String(row.client_name) : null,
    };
  }

  async pgMetaConversionRulesReady(): Promise<boolean> {
    try {
      const result = await this.db.query(
        `SELECT 1 FROM information_schema.tables
         WHERE table_schema = 'public' AND table_name = 'meta_conversion_rules'
         LIMIT 1`,
      );
      return (result.rowCount ?? 0) > 0;
    } catch {
      return false;
    }
  }

  async listConversionRules(clientId?: string): Promise<ConversionRuleRow[]> {
    const values: unknown[] = [];
    let clientClause = '';
    if (clientId) {
      clientClause = ' AND (client_id = $1::uuid OR client_id IS NULL)';
      values.push(clientId);
    }
    const result = await this.db.query(
      `SELECT id::text, client_id::text, lead_status, event_name, enabled,
              require_meta_attribution, value_vnd, notes, created_at, updated_at
       FROM meta_conversion_rules
       WHERE 1=1 ${clientClause}
       ORDER BY client_id NULLS FIRST, lead_status, event_name`,
      values,
    );
    return result.rows.map((row) => this.mapConversionRuleRow(row));
  }

  async createConversionRule(body: CreateConversionRuleBody): Promise<ConversionRuleRow> {
    const clientId = body.client_id?.trim() || null;
    const result = await this.db.query(
      `INSERT INTO meta_conversion_rules (
         client_id, lead_status, event_name, enabled,
         require_meta_attribution, value_vnd, notes
       ) VALUES (
         $1::uuid, $2, $3, COALESCE($4, TRUE),
         COALESCE($5, TRUE), COALESCE($6, 0), COALESCE($7, '')
       )
       RETURNING id::text, client_id::text, lead_status, event_name, enabled,
                 require_meta_attribution, value_vnd, notes, created_at, updated_at`,
      [
        clientId,
        body.lead_status.trim(),
        body.event_name.trim(),
        body.enabled ?? true,
        body.require_meta_attribution ?? true,
        body.value_vnd ?? 0,
        body.notes?.trim() ?? '',
      ],
    );
    return this.mapConversionRuleRow(result.rows[0]);
  }

  async patchConversionRule(
    ruleId: string,
    body: PatchConversionRuleBody,
  ): Promise<ConversionRuleRow | null> {
    const sets: string[] = ['updated_at = NOW()'];
    const params: unknown[] = [];
    const push = (clause: string, value: unknown) => {
      params.push(value);
      sets.push(clause.replace('?', `$${params.length}`));
    };

    if (body.enabled !== undefined) {
      push('enabled = ?', body.enabled);
    }
    if (body.value_vnd !== undefined) {
      push('value_vnd = ?', body.value_vnd);
    }
    if (body.require_meta_attribution !== undefined) {
      push('require_meta_attribution = ?', body.require_meta_attribution);
    }
    if (body.notes !== undefined) {
      push('notes = ?', body.notes.trim());
    }
    if (sets.length <= 1) {
      return this.getConversionRuleById(ruleId);
    }

    params.push(ruleId);
    const result = await this.db.query(
      `UPDATE meta_conversion_rules SET ${sets.join(', ')}
       WHERE id = $${params.length}::uuid
       RETURNING id::text, client_id::text, lead_status, event_name, enabled,
                 require_meta_attribution, value_vnd, notes, created_at, updated_at`,
      params,
    );
    const row = result.rows[0];
    return row ? this.mapConversionRuleRow(row) : null;
  }

  async getConversionRuleById(ruleId: string): Promise<ConversionRuleRow | null> {
    const result = await this.db.query(
      `SELECT id::text, client_id::text, lead_status, event_name, enabled,
              require_meta_attribution, value_vnd, notes, created_at, updated_at
       FROM meta_conversion_rules WHERE id = $1::uuid`,
      [ruleId],
    );
    const row = result.rows[0];
    return row ? this.mapConversionRuleRow(row) : null;
  }

  private mapConversionRuleRow(row: Record<string, unknown>): ConversionRuleRow {
    return {
      id: String(row.id),
      client_id: row.client_id != null ? String(row.client_id) : null,
      lead_status: String(row.lead_status),
      event_name: String(row.event_name),
      enabled: Boolean(row.enabled),
      require_meta_attribution: Boolean(row.require_meta_attribution),
      value_vnd: Number(row.value_vnd ?? 0),
      notes: String(row.notes ?? ''),
      created_at: new Date(String(row.created_at)).toISOString(),
      updated_at: new Date(String(row.updated_at)).toISOString(),
    };
  }

  async getCapiEventById(logId: string): Promise<CapiEventRow | null> {
    const result = await this.db.query(
      `SELECT cel.*, c.code AS client_code, c.name AS client_name
       FROM capi_event_log cel
       JOIN clients c ON c.id = cel.client_id
       WHERE cel.id = $1::uuid`,
      [logId],
    );
    const row = result.rows[0];
    return row ? this.mapCapiEventRow(row) : null;
  }

  async resetCapiEventPending(logId: string): Promise<CapiEventRow | null> {
    const result = await this.db.query(
      `UPDATE capi_event_log
       SET status = 'pending', error_message = NULL, sent_at = NULL
       WHERE id = $1::uuid
       RETURNING id, client_id, event_name, event_id, lead_id, pixel_id,
                 status, error_message, created_at, sent_at`,
      [logId],
    );
    const row = result.rows[0];
    if (!row) return null;
    return {
      id: String(row.id),
      client_id: String(row.client_id),
      event_name: String(row.event_name),
      event_id: String(row.event_id),
      lead_id: row.lead_id != null ? Number(row.lead_id) : null,
      pixel_id: row.pixel_id != null ? String(row.pixel_id) : null,
      status: String(row.status),
      error_message: null,
      created_at: new Date(String(row.created_at)).toISOString(),
      sent_at: null,
    };
  }

  async listFlushableCapiEvents(params: {
    clientId?: string;
    limit?: number;
  }): Promise<CapiEventRow[]> {
    const limit = Math.min(Math.max(params.limit ?? 50, 1), 200);
    const values: unknown[] = [limit];
    let clientClause = '';
    if (params.clientId) {
      clientClause = ' AND cel.client_id = $2::uuid';
      values.push(params.clientId);
    }
    const result = await this.db.query(
      `SELECT cel.*, c.code AS client_code, c.name AS client_name
       FROM capi_event_log cel
       JOIN clients c ON c.id = cel.client_id
       WHERE cel.status IN ('pending', 'failed')
       ${clientClause}
       ORDER BY cel.created_at ASC
       LIMIT $1`,
      values,
    );
    return result.rows.map((row) => this.mapCapiEventRow(row));
  }

  async getMetaChannelAccount(
    clientId: string,
    accountId: string,
  ): Promise<{
    client_id: string;
    account_id: string;
    pixel_id: string | null;
    access_token_encrypted: string | null;
    credential_ref: string | null;
    meta: Record<string, unknown>;
  } | null> {
    const result = await this.db.query(
      `SELECT id::text AS account_id, client_id::text, meta,
              access_token_encrypted, credential_ref
       FROM client_channel_accounts
       WHERE client_id = $1::uuid
         AND id = $2::uuid
         AND channel = 'meta'
       LIMIT 1`,
      [clientId, accountId],
    );
    const row = result.rows[0];
    if (!row) return null;
    const meta = this.parseMeta(row.meta);
    const pixelId = String(meta.pixel_id ?? meta.meta_pixel_id ?? '').trim() || null;
    return {
      client_id: String(row.client_id),
      account_id: String(row.account_id),
      pixel_id: pixelId,
      access_token_encrypted: row.access_token_encrypted
        ? String(row.access_token_encrypted)
        : null,
      credential_ref: row.credential_ref ? String(row.credential_ref) : null,
      meta,
    };
  }
}
