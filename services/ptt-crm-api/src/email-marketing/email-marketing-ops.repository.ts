import {
  BadRequestException,
  Injectable,
  NotFoundException,
  OnModuleDestroy,
} from '@nestjs/common';
import { Pool } from 'pg';
import { AppConfigService } from '../config/app-config.service';
import {
  EmailClientListRow,
  EmailConsentRow,
  EmailContactRow,
  EmailImportResult,
  EmailListResponse,
  EmailPreferencePublicView,
  EmailSuppressionRow,
  EmailWorkspaceRow,
} from './email-marketing.types';
import {
  clampLimit,
  clampOffset,
  iso,
  isValidEmail,
  normalizeEmail,
  randomToken,
} from './email-marketing.util';

const SCHEMA = 'email_mkt';

@Injectable()
export class EmailMarketingOpsRepository implements OnModuleDestroy {
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

  private async audit(params: {
    clientId?: string | null;
    actor: string;
    action: string;
    entityType: string;
    entityId?: string | null;
    after?: Record<string, unknown>;
  }): Promise<void> {
    await this.db.query(
      `INSERT INTO ${SCHEMA}.audit_log (client_id, actor, action, entity_type, entity_id, after_json)
       VALUES ($1::uuid, $2, $3, $4, $5::uuid, $6::jsonb)`,
      [
        params.clientId ?? null,
        params.actor,
        params.action,
        params.entityType,
        params.entityId ?? null,
        JSON.stringify(params.after ?? {}),
      ],
    );
  }

  async listEmailClients(params: {
    q?: string;
    hasWorkspace?: boolean;
    limit: number;
    offset: number;
  }): Promise<EmailListResponse<EmailClientListRow>> {
    const values: unknown[] = [];
    const clauses = [`c.status NOT IN ('archived')`];
    let idx = 1;

    if (params.q) {
      clauses.push(`(c.code ILIKE $${idx} OR c.name ILIKE $${idx})`);
      values.push(`%${params.q.trim()}%`);
      idx += 1;
    }
    if (params.hasWorkspace === true) {
      clauses.push('w.id IS NOT NULL');
    } else if (params.hasWorkspace === false) {
      clauses.push('w.id IS NULL');
    }

    const countResult = await this.db.query<{ c: string }>(
      `SELECT COUNT(*) AS c
       FROM clients c
       LEFT JOIN ${SCHEMA}.workspaces w ON w.client_id = c.id
       WHERE ${clauses.join(' AND ')}`,
      values,
    );
    const total = Number(countResult.rows[0]?.c ?? 0);

    values.push(params.limit, params.offset);
    const result = await this.db.query(
      `SELECT c.id::text AS client_id, c.code AS client_code, c.name AS client_name, c.status AS client_status,
              w.id::text AS workspace_id, w.name AS workspace_name, w.esp_provider,
              COALESCE(cc.cnt, 0) AS contact_count,
              (w.id IS NOT NULL) AS has_workspace
       FROM clients c
       LEFT JOIN ${SCHEMA}.workspaces w ON w.client_id = c.id
       LEFT JOIN LATERAL (
         SELECT COUNT(*) AS cnt FROM ${SCHEMA}.contacts ct WHERE ct.client_id = c.id
       ) cc ON TRUE
       WHERE ${clauses.join(' AND ')}
       ORDER BY c.name ASC
       LIMIT $${idx++} OFFSET $${idx}`,
      values,
    );

    return {
      ok: true,
      items: result.rows.map((r) => ({
        client_id: String(r.client_id),
        client_code: String(r.client_code),
        client_name: String(r.client_name),
        client_status: String(r.client_status),
        workspace_id: r.workspace_id ? String(r.workspace_id) : null,
        workspace_name: r.workspace_name ? String(r.workspace_name) : null,
        esp_provider: r.esp_provider ? String(r.esp_provider) : null,
        contact_count: Number(r.contact_count ?? 0),
        has_workspace: Boolean(r.has_workspace),
      })),
      total,
      limit: params.limit,
      offset: params.offset,
    };
  }

  async listWorkspaces(params: {
    clientId?: string;
    limit: number;
    offset: number;
  }): Promise<EmailListResponse<EmailWorkspaceRow>> {
    const values: unknown[] = [];
    let filter = '';
    if (params.clientId) {
      values.push(params.clientId);
      filter = ` WHERE w.client_id = $1::uuid`;
    }

    const countResult = await this.db.query<{ c: string }>(
      `SELECT COUNT(*) AS c FROM ${SCHEMA}.workspaces w${filter}`,
      values,
    );
    const total = Number(countResult.rows[0]?.c ?? 0);

    values.push(params.limit, params.offset);
    const limitIdx = values.length - 1;
    const offsetIdx = values.length;
    const result = await this.db.query(
      `SELECT w.id::text, w.client_id::text, c.code AS client_code, c.name AS client_name,
              w.name, w.default_from_name, w.default_from_email, w.default_reply_to,
              w.esp_provider, w.daily_send_cap, w.frequency_cap_7d, w.timezone, w.status,
              w.created_at, w.updated_at,
              COALESCE(ct.cnt, 0) AS contact_count,
              COALESCE(sub.cnt, 0) AS subscriber_count,
              COALESCE(sup.cnt, 0) AS suppressed_count
       FROM ${SCHEMA}.workspaces w
       JOIN clients c ON c.id = w.client_id
       LEFT JOIN LATERAL (
         SELECT COUNT(*) AS cnt FROM ${SCHEMA}.contacts ct WHERE ct.client_id = w.client_id
       ) ct ON TRUE
       LEFT JOIN LATERAL (
         SELECT COUNT(DISTINCT cr.contact_id) AS cnt
         FROM ${SCHEMA}.consent_records cr
         JOIN ${SCHEMA}.contacts ct ON ct.id = cr.contact_id
         WHERE ct.client_id = w.client_id
           AND cr.status = 'opted_in'
           AND cr.topic = 'marketing'
       ) sub ON TRUE
       LEFT JOIN LATERAL (
         SELECT COUNT(*) AS cnt FROM ${SCHEMA}.suppression_entries se
         WHERE se.client_id = w.client_id AND se.expires_at IS NULL
       ) sup ON TRUE
       ${filter}
       ORDER BY c.name ASC
       LIMIT $${limitIdx} OFFSET $${offsetIdx}`,
      values,
    );

    return {
      ok: true,
      items: result.rows.map((r) => this.mapWorkspace(r)),
      total,
      limit: params.limit,
      offset: params.offset,
    };
  }

  async getWorkspaceByClient(clientId: string): Promise<EmailWorkspaceRow | null> {
    const out = await this.listWorkspaces({ clientId, limit: 1, offset: 0 });
    return out.items[0] ?? null;
  }

  async createWorkspace(params: {
    clientId: string;
    name: string;
    defaultFromName?: string;
    defaultFromEmail?: string;
    defaultReplyTo?: string;
    espProvider?: string;
    dailySendCap?: number;
    frequencyCap7d?: number;
    timezone?: string;
    actor: string;
  }): Promise<EmailWorkspaceRow> {
    const clientCheck = await this.db.query(`SELECT id, name, code FROM clients WHERE id = $1::uuid`, [
      params.clientId,
    ]);
    if (!clientCheck.rowCount) {
      throw new NotFoundException({ error: 'client_not_found' });
    }

    const existing = await this.getWorkspaceByClient(params.clientId);
    if (existing) {
      throw new BadRequestException({ error: 'workspace_exists', workspace_id: existing.id });
    }

    const clientName = String(clientCheck.rows[0].name);
    const result = await this.db.query(
      `INSERT INTO ${SCHEMA}.workspaces (
         client_id, name, default_from_name, default_from_email, default_reply_to,
         esp_provider, daily_send_cap, frequency_cap_7d, timezone
       ) VALUES ($1::uuid, $2, $3, $4, $5, $6, $7, $8, $9)
       RETURNING id::text`,
      [
        params.clientId,
        params.name.trim() || `${clientName} Email`,
        params.defaultFromName?.trim() || null,
        params.defaultFromEmail?.trim() || null,
        params.defaultReplyTo?.trim() || null,
        params.espProvider?.trim() || 'sendgrid',
        params.dailySendCap ?? 10000,
        params.frequencyCap7d ?? 5,
        params.timezone?.trim() || 'Asia/Ho_Chi_Minh',
      ],
    );
    const workspaceId = String(result.rows[0].id);
    await this.audit({
      clientId: params.clientId,
      actor: params.actor,
      action: 'workspace_created',
      entityType: 'workspace',
      entityId: workspaceId,
      after: { name: params.name },
    });
    const row = await this.getWorkspaceByClient(params.clientId);
    if (!row) throw new NotFoundException({ error: 'workspace_not_found' });
    return row;
  }

  async updateWorkspace(params: {
    workspaceId: string;
    patch: {
      name?: string;
      default_from_name?: string;
      default_from_email?: string;
      default_reply_to?: string;
      esp_provider?: string;
      daily_send_cap?: number;
      frequency_cap_7d?: number;
      timezone?: string;
      status?: string;
    };
    actor: string;
  }): Promise<EmailWorkspaceRow> {
    const fields: string[] = [];
    const values: unknown[] = [params.workspaceId];
    let idx = 2;
    const mapping: Record<string, unknown> = {
      name: params.patch.name,
      default_from_name: params.patch.default_from_name,
      default_from_email: params.patch.default_from_email,
      default_reply_to: params.patch.default_reply_to,
      esp_provider: params.patch.esp_provider,
      daily_send_cap: params.patch.daily_send_cap,
      frequency_cap_7d: params.patch.frequency_cap_7d,
      timezone: params.patch.timezone,
      status: params.patch.status,
    };
    for (const [col, val] of Object.entries(mapping)) {
      if (val !== undefined) {
        fields.push(`${col} = $${idx++}`);
        values.push(typeof val === 'string' ? val.trim() : val);
      }
    }
    if (fields.length === 0) {
      throw new BadRequestException({ error: 'empty_patch' });
    }
    fields.push('updated_at = NOW()');
    const result = await this.db.query(
      `UPDATE ${SCHEMA}.workspaces SET ${fields.join(', ')} WHERE id = $1::uuid RETURNING client_id::text`,
      values,
    );
    if (!result.rowCount) {
      throw new NotFoundException({ error: 'workspace_not_found' });
    }
    await this.audit({
      clientId: String(result.rows[0].client_id),
      actor: params.actor,
      action: 'workspace_updated',
      entityType: 'workspace',
      entityId: params.workspaceId,
      after: params.patch as Record<string, unknown>,
    });
    const row = await this.getWorkspaceByClient(String(result.rows[0].client_id));
    if (!row) throw new NotFoundException({ error: 'workspace_not_found' });
    return row;
  }

  async listContacts(params: {
    clientId?: string;
    q?: string;
    limit: number;
    offset: number;
  }): Promise<EmailListResponse<EmailContactRow>> {
    const values: unknown[] = [];
    const clauses = ['1=1'];
    let idx = 1;
    if (params.clientId) {
      clauses.push(`ct.client_id = $${idx++}::uuid`);
      values.push(params.clientId);
    }
    if (params.q) {
      clauses.push(
        `(ct.email ILIKE $${idx} OR ct.first_name ILIKE $${idx} OR ct.last_name ILIKE $${idx})`,
      );
      values.push(`%${params.q.trim()}%`);
      idx += 1;
    }

    const countResult = await this.db.query<{ c: string }>(
      `SELECT COUNT(*) AS c
       FROM ${SCHEMA}.contacts ct
       WHERE ${clauses.join(' AND ')}`,
      values,
    );
    const total = Number(countResult.rows[0]?.c ?? 0);

    values.push(params.limit, params.offset);
    const result = await this.db.query(
      `SELECT ct.id::text, ct.client_id::text, c.name AS client_name, ct.email,
              ct.first_name, ct.last_name, ct.lifecycle_stage, ct.created_at, ct.updated_at,
              ls.status AS consent_status,
              EXISTS (
                SELECT 1 FROM ${SCHEMA}.suppression_entries se
                WHERE se.email_normalized = ct.email_normalized
                  AND (se.client_id IS NULL OR se.client_id = ct.client_id)
                  AND se.expires_at IS NULL
              ) AS suppressed
       FROM ${SCHEMA}.contacts ct
       JOIN clients c ON c.id = ct.client_id
       LEFT JOIN LATERAL (
         SELECT status FROM ${SCHEMA}.consent_records cr
         WHERE cr.contact_id = ct.id AND cr.topic = 'marketing'
         ORDER BY cr.recorded_at DESC LIMIT 1
       ) ls ON TRUE
       WHERE ${clauses.join(' AND ')}
       ORDER BY ct.updated_at DESC
       LIMIT $${idx++} OFFSET $${idx}`,
      values,
    );

    return {
      ok: true,
      items: result.rows.map((r) => ({
        id: String(r.id),
        client_id: String(r.client_id),
        client_name: String(r.client_name),
        email: String(r.email),
        first_name: r.first_name ? String(r.first_name) : null,
        last_name: r.last_name ? String(r.last_name) : null,
        lifecycle_stage: r.lifecycle_stage ? String(r.lifecycle_stage) : null,
        consent_status: r.consent_status ? String(r.consent_status) : null,
        suppressed: Boolean(r.suppressed),
        created_at: iso(r.created_at) ?? '',
        updated_at: iso(r.updated_at) ?? '',
      })),
      total,
      limit: params.limit,
      offset: params.offset,
    };
  }

  async importContacts(params: {
    clientId: string;
    rows: Array<{
      email: string;
      first_name?: string;
      last_name?: string;
      lifecycle_stage?: string;
    }>;
    actor: string;
  }): Promise<EmailImportResult> {
    let created = 0;
    let updated = 0;
    let skipped = 0;
    const errors: string[] = [];

    for (const row of params.rows) {
      const email = normalizeEmail(row.email ?? '');
      if (!isValidEmail(email)) {
        skipped += 1;
        errors.push(`invalid_email:${row.email}`);
        continue;
      }
      try {
        const result = await this.db.query(
          `INSERT INTO ${SCHEMA}.contacts (
             client_id, email, email_normalized, first_name, last_name, lifecycle_stage
           ) VALUES ($1::uuid, $2, $3, $4, $5, $6)
           ON CONFLICT (client_id, email_normalized) DO UPDATE SET
             first_name = COALESCE(EXCLUDED.first_name, ${SCHEMA}.contacts.first_name),
             last_name = COALESCE(EXCLUDED.last_name, ${SCHEMA}.contacts.last_name),
             lifecycle_stage = COALESCE(EXCLUDED.lifecycle_stage, ${SCHEMA}.contacts.lifecycle_stage),
             updated_at = NOW()
           RETURNING (xmax = 0) AS inserted`,
          [
            params.clientId,
            email,
            email,
            row.first_name?.trim() || null,
            row.last_name?.trim() || null,
            row.lifecycle_stage?.trim() || 'subscriber',
          ],
        );
        if (result.rows[0]?.inserted) created += 1;
        else updated += 1;
      } catch (err) {
        skipped += 1;
        errors.push(`${email}:${String(err)}`);
      }
    }

    if (created + updated > 0) {
      await this.audit({
        clientId: params.clientId,
        actor: params.actor,
        action: 'contacts_imported',
        entityType: 'contact',
        after: { created, updated, skipped },
      });
    }

    return { ok: true, created, updated, skipped, errors: errors.slice(0, 20) };
  }

  async listConsent(params: {
    clientId?: string;
    contactId?: string;
    topic?: string;
    limit: number;
    offset: number;
  }): Promise<EmailListResponse<EmailConsentRow>> {
    const values: unknown[] = [];
    const clauses = ['1=1'];
    let idx = 1;
    if (params.clientId) {
      clauses.push(`cr.client_id = $${idx++}::uuid`);
      values.push(params.clientId);
    }
    if (params.contactId) {
      clauses.push(`cr.contact_id = $${idx++}::uuid`);
      values.push(params.contactId);
    }
    if (params.topic) {
      clauses.push(`cr.topic = $${idx++}`);
      values.push(params.topic);
    }

    const countResult = await this.db.query<{ c: string }>(
      `SELECT COUNT(*) AS c FROM ${SCHEMA}.consent_records cr WHERE ${clauses.join(' AND ')}`,
      values,
    );
    const total = Number(countResult.rows[0]?.c ?? 0);

    values.push(params.limit, params.offset);
    const result = await this.db.query(
      `SELECT cr.id::text, cr.client_id::text, cr.contact_id::text, ct.email AS contact_email,
              cr.topic, cr.status, cr.source, cr.consent_version, cr.recorded_at, cr.recorded_by
       FROM ${SCHEMA}.consent_records cr
       JOIN ${SCHEMA}.contacts ct ON ct.id = cr.contact_id
       WHERE ${clauses.join(' AND ')}
       ORDER BY cr.recorded_at DESC
       LIMIT $${idx++} OFFSET $${idx}`,
      values,
    );

    return {
      ok: true,
      items: result.rows.map((r) => ({
        id: String(r.id),
        client_id: String(r.client_id),
        contact_id: String(r.contact_id),
        contact_email: String(r.contact_email),
        topic: String(r.topic),
        status: String(r.status),
        source: String(r.source),
        consent_version: r.consent_version ? String(r.consent_version) : null,
        recorded_at: iso(r.recorded_at) ?? '',
        recorded_by: r.recorded_by ? String(r.recorded_by) : null,
      })),
      total,
      limit: params.limit,
      offset: params.offset,
    };
  }

  async recordConsent(params: {
    clientId: string;
    contactId?: string;
    email?: string;
    topic: string;
    status: string;
    source: string;
    consentVersion?: string;
    recordedBy: string;
    issueToken?: boolean;
  }): Promise<{ ok: boolean; consent_id: string; contact_id: string; preference_token?: string }> {
    const allowed = ['opted_in', 'opted_out', 'pending_confirm'];
    if (!allowed.includes(params.status)) {
      throw new BadRequestException({ error: 'invalid_status' });
    }

    let contactId = params.contactId;
    if (!contactId) {
      const email = normalizeEmail(params.email ?? '');
      if (!isValidEmail(email)) {
        throw new BadRequestException({ error: 'email_required' });
      }
      const upsert = await this.db.query(
        `INSERT INTO ${SCHEMA}.contacts (client_id, email, email_normalized)
         VALUES ($1::uuid, $2, $3)
         ON CONFLICT (client_id, email_normalized) DO UPDATE SET updated_at = NOW()
         RETURNING id::text`,
        [params.clientId, email, email],
      );
      contactId = String(upsert.rows[0].id);
    }

    const insert = await this.db.query(
      `INSERT INTO ${SCHEMA}.consent_records (
         client_id, contact_id, topic, status, source, consent_version, recorded_by
       ) VALUES ($1::uuid, $2::uuid, $3, $4, $5, $6, $7)
       RETURNING id::text`,
      [
        params.clientId,
        contactId,
        params.topic.trim() || 'marketing',
        params.status,
        params.source.trim() || 'manual',
        params.consentVersion?.trim() || null,
        params.recordedBy,
      ],
    );
    const consentId = String(insert.rows[0].id);
    await this.audit({
      clientId: params.clientId,
      actor: params.recordedBy,
      action: 'consent_recorded',
      entityType: 'consent',
      entityId: consentId,
      after: { topic: params.topic, status: params.status },
    });

    let preferenceToken: string | undefined;
    if (params.issueToken !== false) {
      preferenceToken = await this.createPreferenceToken({
        contactId,
        clientId: params.clientId,
        purpose: params.status === 'pending_confirm' ? 'confirm' : 'preferences',
      });
    }

    return {
      ok: true,
      consent_id: consentId,
      contact_id: contactId,
      preference_token: preferenceToken,
    };
  }

  async listSuppression(params: {
    clientId?: string;
    q?: string;
    limit: number;
    offset: number;
  }): Promise<EmailListResponse<EmailSuppressionRow>> {
    const values: unknown[] = [];
    const clauses = ['se.expires_at IS NULL'];
    let idx = 1;
    if (params.clientId) {
      clauses.push(`(se.client_id = $${idx++}::uuid OR se.scope = 'global')`);
      values.push(params.clientId);
    }
    if (params.q) {
      clauses.push(`se.email_normalized ILIKE $${idx++}`);
      values.push(`%${normalizeEmail(params.q)}%`);
    }

    const countResult = await this.db.query<{ c: string }>(
      `SELECT COUNT(*) AS c FROM ${SCHEMA}.suppression_entries se WHERE ${clauses.join(' AND ')}`,
      values,
    );
    const total = Number(countResult.rows[0]?.c ?? 0);

    values.push(params.limit, params.offset);
    const result = await this.db.query(
      `SELECT se.id::text, se.client_id::text, c.name AS client_name, se.email_normalized,
              se.reason, se.scope, se.expires_at, se.created_at, se.created_by
       FROM ${SCHEMA}.suppression_entries se
       LEFT JOIN clients c ON c.id = se.client_id
       WHERE ${clauses.join(' AND ')}
       ORDER BY se.created_at DESC
       LIMIT $${idx++} OFFSET $${idx}`,
      values,
    );

    return {
      ok: true,
      items: result.rows.map((r) => ({
        id: String(r.id),
        client_id: r.client_id ? String(r.client_id) : null,
        client_name: r.client_name ? String(r.client_name) : null,
        email_normalized: String(r.email_normalized),
        reason: String(r.reason),
        scope: String(r.scope),
        expires_at: iso(r.expires_at),
        created_at: iso(r.created_at) ?? '',
        created_by: r.created_by ? String(r.created_by) : null,
      })),
      total,
      limit: params.limit,
      offset: params.offset,
    };
  }

  async addSuppression(params: {
    clientId?: string;
    email: string;
    reason: string;
    scope?: string;
    createdBy: string;
  }): Promise<{ ok: boolean; id: string }> {
    const email = normalizeEmail(params.email);
    if (!isValidEmail(email)) {
      throw new BadRequestException({ error: 'invalid_email' });
    }
    const allowedReasons = [
      'unsubscribe',
      'complaint',
      'hard_bounce',
      'manual',
      'legal_hold',
      'global_block',
    ];
    if (!allowedReasons.includes(params.reason)) {
      throw new BadRequestException({ error: 'invalid_reason' });
    }
    const scope = params.scope?.trim() || 'client';
    const result = await this.db.query(
      `INSERT INTO ${SCHEMA}.suppression_entries (
         client_id, email_normalized, reason, scope, created_by
       ) VALUES ($1::uuid, $2, $3, $4, $5)
       ON CONFLICT DO NOTHING
       RETURNING id::text`,
      [params.clientId ?? null, email, params.reason, scope, params.createdBy],
    );
    if (!result.rowCount) {
      const existing = await this.db.query(
        `SELECT id::text FROM ${SCHEMA}.suppression_entries
         WHERE email_normalized = $1 AND reason = $2
           AND COALESCE(client_id, '00000000-0000-0000-0000-000000000000'::uuid)
               = COALESCE($3::uuid, '00000000-0000-0000-0000-000000000000'::uuid)
           AND expires_at IS NULL
         LIMIT 1`,
        [email, params.reason, params.clientId ?? null],
      );
      return { ok: true, id: String(existing.rows[0]?.id ?? '') };
    }
    const id = String(result.rows[0].id);
    await this.audit({
      clientId: params.clientId ?? null,
      actor: params.createdBy,
      action: 'suppression_added',
      entityType: 'suppression',
      entityId: id,
      after: { email, reason: params.reason, scope },
    });
    return { ok: true, id };
  }

  async captureLead(params: {
    clientId: string;
    email: string;
    firstName?: string;
    source?: string;
  }): Promise<{ ok: boolean; contact_id: string; confirm_token?: string }> {
    const ws = await this.getWorkspaceByClient(params.clientId);
    if (!ws) {
      throw new BadRequestException({ error: 'workspace_required' });
    }
    const email = normalizeEmail(params.email);
    if (!isValidEmail(email)) {
      throw new BadRequestException({ error: 'invalid_email' });
    }
    const contact = await this.db.query(
      `INSERT INTO ${SCHEMA}.contacts (client_id, email, email_normalized, first_name)
       VALUES ($1::uuid, $2, $3, $4)
       ON CONFLICT (client_id, email_normalized) DO UPDATE SET
         first_name = COALESCE(EXCLUDED.first_name, ${SCHEMA}.contacts.first_name),
         updated_at = NOW()
       RETURNING id::text`,
      [params.clientId, email, email, params.firstName?.trim() || null],
    );
    const contactId = String(contact.rows[0].id);
    await this.recordConsent({
      clientId: params.clientId,
      contactId,
      topic: 'marketing',
      status: 'pending_confirm',
      source: params.source?.trim() || 'web_capture',
      recordedBy: 'public_capture',
      issueToken: false,
    });
    const token = await this.createPreferenceToken({
      contactId,
      clientId: params.clientId,
      purpose: 'confirm',
    });
    return { ok: true, contact_id: contactId, confirm_token: token };
  }

  async createPreferenceToken(params: {
    contactId: string;
    clientId: string;
    purpose: 'preferences' | 'unsubscribe' | 'confirm';
  }): Promise<string> {
    const token = randomToken();
    await this.db.query(
      `INSERT INTO ${SCHEMA}.preference_tokens (token, contact_id, client_id, purpose, expires_at)
       VALUES ($1, $2::uuid, $3::uuid, $4, NOW() + INTERVAL '90 days')`,
      [token, params.contactId, params.clientId, params.purpose],
    );
    return token;
  }

  async resolveToken(token: string): Promise<{
    contact_id: string;
    client_id: string;
    client_name: string;
    email: string;
    purpose: string;
  } | null> {
    const result = await this.db.query(
      `SELECT pt.contact_id::text, pt.client_id::text, pt.purpose, c.name AS client_name, ct.email
       FROM ${SCHEMA}.preference_tokens pt
       JOIN clients c ON c.id = pt.client_id
       JOIN ${SCHEMA}.contacts ct ON ct.id = pt.contact_id
       WHERE pt.token = $1
         AND (pt.expires_at IS NULL OR pt.expires_at > NOW())
       LIMIT 1`,
      [token.trim()],
    );
    if (!result.rowCount) return null;
    const row = result.rows[0];
    return {
      contact_id: String(row.contact_id),
      client_id: String(row.client_id),
      client_name: String(row.client_name),
      email: String(row.email),
      purpose: String(row.purpose),
    };
  }

  async getPublicPreferences(token: string): Promise<EmailPreferencePublicView> {
    const resolved = await this.resolveToken(token);
    if (!resolved) {
      throw new NotFoundException({ error: 'token_invalid' });
    }
    const topics = await this.db.query(
      `SELECT DISTINCT ON (topic) topic, status
       FROM ${SCHEMA}.consent_records
       WHERE contact_id = $1::uuid
       ORDER BY topic, recorded_at DESC`,
      [resolved.contact_id],
    );
    return {
      ok: true,
      client_name: resolved.client_name,
      email: resolved.email,
      topics: topics.rows.map((r) => ({
        topic: String(r.topic),
        status: String(r.status),
      })),
      token_purpose: resolved.purpose,
    };
  }

  async updatePublicPreferences(
    token: string,
    body: { marketing?: boolean; topics?: Array<{ topic: string; opted_in: boolean }> },
  ): Promise<{ ok: boolean }> {
    const resolved = await this.resolveToken(token);
    if (!resolved) {
      throw new NotFoundException({ error: 'token_invalid' });
    }
    const updates =
      body.topics ??
      (body.marketing !== undefined
        ? [{ topic: 'marketing', opted_in: body.marketing }]
        : []);
    for (const item of updates) {
      await this.recordConsent({
        clientId: resolved.client_id,
        contactId: resolved.contact_id,
        topic: item.topic,
        status: item.opted_in ? 'opted_in' : 'opted_out',
        source: 'preference_center',
        recordedBy: 'subscriber',
        issueToken: false,
      });
    }
    return { ok: true };
  }

  async publicUnsubscribe(token: string): Promise<{ ok: boolean; email: string }> {
    const resolved = await this.resolveToken(token);
    if (!resolved) {
      throw new NotFoundException({ error: 'token_invalid' });
    }
    await this.recordConsent({
      clientId: resolved.client_id,
      contactId: resolved.contact_id,
      topic: 'marketing',
      status: 'opted_out',
      source: 'one_click_unsubscribe',
      recordedBy: 'subscriber',
      issueToken: false,
    });
    await this.addSuppression({
      clientId: resolved.client_id,
      email: resolved.email,
      reason: 'unsubscribe',
      scope: 'client',
      createdBy: 'subscriber',
    });
    await this.db.query(
      `UPDATE ${SCHEMA}.preference_tokens SET used_at = NOW() WHERE token = $1`,
      [token.trim()],
    );
    return { ok: true, email: resolved.email };
  }

  async publicConfirm(token: string): Promise<{ ok: boolean; email: string }> {
    const resolved = await this.resolveToken(token);
    if (!resolved) {
      throw new NotFoundException({ error: 'token_invalid' });
    }
    await this.recordConsent({
      clientId: resolved.client_id,
      contactId: resolved.contact_id,
      topic: 'marketing',
      status: 'opted_in',
      source: 'double_opt_in',
      recordedBy: 'subscriber',
      issueToken: false,
    });
    await this.db.query(
      `UPDATE ${SCHEMA}.preference_tokens SET used_at = NOW() WHERE token = $1`,
      [token.trim()],
    );
    return { ok: true, email: resolved.email };
  }

  private mapWorkspace(r: Record<string, unknown>): EmailWorkspaceRow {
    return {
      id: String(r.id),
      client_id: String(r.client_id),
      client_code: String(r.client_code ?? ''),
      client_name: String(r.client_name ?? ''),
      name: String(r.name ?? ''),
      default_from_name: r.default_from_name ? String(r.default_from_name) : null,
      default_from_email: r.default_from_email ? String(r.default_from_email) : null,
      default_reply_to: r.default_reply_to ? String(r.default_reply_to) : null,
      esp_provider: String(r.esp_provider ?? 'sendgrid'),
      daily_send_cap: Number(r.daily_send_cap ?? 0),
      frequency_cap_7d: Number(r.frequency_cap_7d ?? 0),
      timezone: String(r.timezone ?? ''),
      status: String(r.status ?? ''),
      contact_count: Number(r.contact_count ?? 0),
      subscriber_count: Number(r.subscriber_count ?? 0),
      suppressed_count: Number(r.suppressed_count ?? 0),
      created_at: iso(r.created_at) ?? '',
      updated_at: iso(r.updated_at) ?? '',
    };
  }

  static pagination(limit?: number, offset?: number) {
    return { limit: clampLimit(limit), offset: clampOffset(offset) };
  }
}
