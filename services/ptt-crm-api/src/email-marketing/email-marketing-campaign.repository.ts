import {
  BadRequestException,
  Injectable,
  NotFoundException,
  OnModuleDestroy,
} from '@nestjs/common';
import { Pool } from 'pg';
import { AppConfigService } from '../config/app-config.service';
import {
  EmailCampaignRow,
  EmailListResponse,
  EmailPreflightResponse,
  EmailSegmentComputeResult,
  EmailSegmentRow,
  EmailTemplateRow,
} from './email-marketing.types';
import {
  runCampaignPreflight,
  runTemplatePreflight,
} from './email-marketing-preflight.util';
import { clampLimit, clampOffset, iso } from './email-marketing.util';

const SCHEMA = 'email_mkt';

@Injectable()
export class EmailMarketingCampaignRepository implements OnModuleDestroy {
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

  static pagination(limit?: number, offset?: number) {
    return { limit: clampLimit(limit), offset: clampOffset(offset) };
  }

  private async audit(params: {
    clientId: string;
    actor: string;
    action: string;
    entityType: string;
    entityId: string;
    after?: Record<string, unknown>;
  }): Promise<void> {
    await this.db.query(
      `INSERT INTO ${SCHEMA}.audit_log (client_id, actor, action, entity_type, entity_id, after_json)
       VALUES ($1::uuid, $2, $3, $4, $5::uuid, $6::jsonb)`,
      [
        params.clientId,
        params.actor,
        params.action,
        params.entityType,
        params.entityId,
        JSON.stringify(params.after ?? {}),
      ],
    );
  }

  async listSegments(params: {
    clientId?: string;
    limit: number;
    offset: number;
  }): Promise<EmailListResponse<EmailSegmentRow>> {
    const values: unknown[] = [];
    let filter = '';
    if (params.clientId) {
      values.push(params.clientId);
      filter = ` WHERE s.client_id = $1::uuid`;
    }
    const count = await this.db.query<{ c: string }>(
      `SELECT COUNT(*) AS c FROM ${SCHEMA}.segments s${filter}`,
      values,
    );
    values.push(params.limit, params.offset);
    const result = await this.db.query(
      `SELECT s.id::text, s.client_id::text, c.name AS client_name, s.name, s.segment_type,
              s.definition_json, s.member_count, s.last_computed_at, s.status, s.created_at, s.updated_at
       FROM ${SCHEMA}.segments s
       JOIN clients c ON c.id = s.client_id
       ${filter}
       ORDER BY s.updated_at DESC
       LIMIT $${values.length - 1} OFFSET $${values.length}`,
      values,
    );
    return {
      ok: true,
      items: result.rows.map((r) => this.mapSegment(r)),
      total: Number(count.rows[0]?.c ?? 0),
      limit: params.limit,
      offset: params.offset,
    };
  }

  async createSegment(params: {
    clientId: string;
    name: string;
    segmentType?: string;
    definitionJson?: Record<string, unknown>;
    actor: string;
  }): Promise<EmailSegmentRow> {
    const result = await this.db.query(
      `INSERT INTO ${SCHEMA}.segments (client_id, name, segment_type, definition_json)
       VALUES ($1::uuid, $2, $3, $4::jsonb)
       RETURNING id::text`,
      [
        params.clientId,
        params.name.trim(),
        params.segmentType?.trim() || 'dynamic',
        JSON.stringify(params.definitionJson ?? {}),
      ],
    );
    const id = String(result.rows[0].id);
    await this.audit({
      clientId: params.clientId,
      actor: params.actor,
      action: 'segment_created',
      entityType: 'segment',
      entityId: id,
      after: { name: params.name },
    });
    const row = await this.getSegment(id);
    if (!row) throw new NotFoundException({ error: 'segment_not_found' });
    return row;
  }

  async updateSegment(params: {
    id: string;
    name?: string;
    segmentType?: string;
    definitionJson?: Record<string, unknown>;
    actor: string;
  }): Promise<EmailSegmentRow> {
    const existing = await this.getSegment(params.id);
    if (!existing) throw new NotFoundException({ error: 'segment_not_found' });

    const name = params.name?.trim() || existing.name;
    const segmentType = params.segmentType?.trim() || existing.segment_type;
    const definitionJson = params.definitionJson ?? existing.definition_json;

    await this.db.query(
      `UPDATE ${SCHEMA}.segments
       SET name = $2, segment_type = $3, definition_json = $4::jsonb, updated_at = NOW()
       WHERE id = $1::uuid`,
      [params.id, name, segmentType, JSON.stringify(definitionJson)],
    );
    await this.audit({
      clientId: existing.client_id,
      actor: params.actor,
      action: 'segment_updated',
      entityType: 'segment',
      entityId: params.id,
      after: { name, segment_type: segmentType },
    });
    const row = await this.getSegment(params.id);
    if (!row) throw new NotFoundException({ error: 'segment_not_found' });
    return row;
  }

  async getSegment(id: string): Promise<EmailSegmentRow | null> {
    const result = await this.db.query(
      `SELECT s.id::text, s.client_id::text, c.name AS client_name, s.name, s.segment_type,
              s.definition_json, s.member_count, s.last_computed_at, s.status, s.created_at, s.updated_at
       FROM ${SCHEMA}.segments s
       JOIN clients c ON c.id = s.client_id
       WHERE s.id = $1::uuid`,
      [id],
    );
    if (!result.rowCount) return null;
    return this.mapSegment(result.rows[0]);
  }

  async computeSegment(id: string, actor: string): Promise<EmailSegmentComputeResult> {
    const segment = await this.getSegment(id);
    if (!segment) throw new NotFoundException({ error: 'segment_not_found' });

    const clientId = segment.client_id;
    const def = segment.definition_json ?? {};
    let contactIds: string[] = [];

    if (segment.segment_type === 'static' && Array.isArray(def.contact_ids)) {
      contactIds = def.contact_ids.map(String);
    } else {
      const lifecycle = typeof def.lifecycle_stage === 'string' ? def.lifecycle_stage : null;
      const values: unknown[] = [clientId];
      let sql = `SELECT ct.id::text FROM ${SCHEMA}.contacts ct WHERE ct.client_id = $1::uuid`;
      if (lifecycle) {
        values.push(lifecycle);
        sql += ` AND ct.lifecycle_stage = $2`;
      }
      const rows = await this.db.query<{ id: string }>(sql, values);
      contactIds = rows.rows.map((r) => r.id);
    }

    let eligible = contactIds;
    let excludedSuppression = 0;
    let excludedConsent = 0;

    if (eligible.length > 0) {
      const filtered = await this.db.query<{ id: string; suppressed: boolean; consent_ok: boolean }>(
        `SELECT ct.id::text,
                EXISTS (
                  SELECT 1 FROM ${SCHEMA}.suppression_entries se
                  WHERE se.email_normalized = ct.email_normalized
                    AND (se.client_id IS NULL OR se.client_id = ct.client_id)
                    AND se.expires_at IS NULL
                ) AS suppressed,
                COALESCE((
                  SELECT cr.status FROM ${SCHEMA}.consent_records cr
                  WHERE cr.contact_id = ct.id AND cr.topic = 'marketing'
                  ORDER BY cr.recorded_at DESC LIMIT 1
                ), '') = 'opted_in' AS consent_ok
         FROM ${SCHEMA}.contacts ct
         WHERE ct.id = ANY($1::uuid[])`,
        [eligible],
      );
      excludedSuppression = filtered.rows.filter((r) => r.suppressed).length;
      excludedConsent = filtered.rows.filter((r) => !r.consent_ok && !r.suppressed).length;
      eligible = filtered.rows.filter((r) => !r.suppressed && r.consent_ok).map((r) => r.id);
    }

    await this.db.query(`DELETE FROM ${SCHEMA}.segment_members WHERE segment_id = $1::uuid`, [id]);
    for (const contactId of eligible) {
      await this.db.query(
        `INSERT INTO ${SCHEMA}.segment_members (segment_id, contact_id) VALUES ($1::uuid, $2::uuid)
         ON CONFLICT DO NOTHING`,
        [id, contactId],
      );
    }
    await this.db.query(
      `UPDATE ${SCHEMA}.segments SET member_count = $2, last_computed_at = NOW(), updated_at = NOW()
       WHERE id = $1::uuid`,
      [id, eligible.length],
    );
    await this.audit({
      clientId,
      actor,
      action: 'segment_computed',
      entityType: 'segment',
      entityId: id,
      after: { member_count: eligible.length },
    });

    return {
      ok: true,
      segment_id: id,
      member_count: eligible.length,
      excluded_suppression: excludedSuppression,
      excluded_consent: excludedConsent,
    };
  }

  async listTemplates(params: {
    clientId?: string;
    limit: number;
    offset: number;
  }): Promise<EmailListResponse<EmailTemplateRow>> {
    const values: unknown[] = [];
    let filter = '';
    if (params.clientId) {
      values.push(params.clientId);
      filter = ` WHERE t.client_id = $1::uuid`;
    }
    const count = await this.db.query<{ c: string }>(
      `SELECT COUNT(*) AS c FROM ${SCHEMA}.templates t${filter}`,
      values,
    );
    values.push(params.limit, params.offset);
    const result = await this.db.query(
      `SELECT t.id::text, t.client_id::text, c.name AS client_name, t.name, t.subject_template,
              t.html_body, t.text_body, t.locale, t.version, t.status, t.created_at, t.updated_at
       FROM ${SCHEMA}.templates t
       JOIN clients c ON c.id = t.client_id
       ${filter}
       ORDER BY t.updated_at DESC
       LIMIT $${values.length - 1} OFFSET $${values.length}`,
      values,
    );
    return {
      ok: true,
      items: result.rows.map((r) => this.mapTemplate(r)),
      total: Number(count.rows[0]?.c ?? 0),
      limit: params.limit,
      offset: params.offset,
    };
  }

  async createTemplate(params: {
    clientId: string;
    name: string;
    subjectTemplate: string;
    htmlBody: string;
    textBody?: string;
    actor: string;
  }): Promise<EmailTemplateRow> {
    const result = await this.db.query(
      `INSERT INTO ${SCHEMA}.templates (client_id, name, subject_template, html_body, text_body)
       VALUES ($1::uuid, $2, $3, $4, $5)
       RETURNING id::text`,
      [
        params.clientId,
        params.name.trim(),
        params.subjectTemplate.trim(),
        params.htmlBody,
        params.textBody?.trim() || null,
      ],
    );
    const id = String(result.rows[0].id);
    await this.audit({
      clientId: params.clientId,
      actor: params.actor,
      action: 'template_created',
      entityType: 'template',
      entityId: id,
    });
    const row = await this.getTemplate(id);
    if (!row) throw new NotFoundException({ error: 'template_not_found' });
    return row;
  }

  async getTemplate(id: string): Promise<EmailTemplateRow | null> {
    const result = await this.db.query(
      `SELECT t.id::text, t.client_id::text, c.name AS client_name, t.name, t.subject_template,
              t.html_body, t.text_body, t.locale, t.version, t.status, t.created_at, t.updated_at
       FROM ${SCHEMA}.templates t
       JOIN clients c ON c.id = t.client_id
       WHERE t.id = $1::uuid`,
      [id],
    );
    if (!result.rowCount) return null;
    return this.mapTemplate(result.rows[0]);
  }

  async updateTemplate(
    id: string,
    patch: {
      name?: string;
      subject_template?: string;
      html_body?: string;
      text_body?: string;
      status?: string;
    },
    actor: string,
  ): Promise<EmailTemplateRow> {
    const existing = await this.getTemplate(id);
    if (!existing) throw new NotFoundException({ error: 'template_not_found' });
    const fields: string[] = [];
    const values: unknown[] = [id];
    let idx = 2;
    for (const [col, val] of Object.entries(patch)) {
      if (val !== undefined) {
        fields.push(`${col} = $${idx++}`);
        values.push(val);
      }
    }
    if (fields.length === 0) throw new BadRequestException({ error: 'empty_patch' });
    fields.push('updated_at = NOW()', 'version = version + 1');
    await this.db.query(
      `UPDATE ${SCHEMA}.templates SET ${fields.join(', ')} WHERE id = $1::uuid`,
      values,
    );
    await this.audit({
      clientId: existing.client_id,
      actor,
      action: 'template_updated',
      entityType: 'template',
      entityId: id,
      after: patch as Record<string, unknown>,
    });
    const row = await this.getTemplate(id);
    if (!row) throw new NotFoundException({ error: 'template_not_found' });
    return row;
  }

  async preflightTemplate(id: string): Promise<EmailPreflightResponse> {
    const template = await this.getTemplate(id);
    if (!template) throw new NotFoundException({ error: 'template_not_found' });
    const ws = await this.db.query<{ default_from_email: string | null }>(
      `SELECT default_from_email FROM ${SCHEMA}.workspaces WHERE client_id = $1::uuid LIMIT 1`,
      [template.client_id],
    );
    const fromEmail = ws.rows[0]?.default_from_email ? String(ws.rows[0].default_from_email) : null;
    let domainAuth: { spfStatus: string | null; dkimStatus: string | null } | null = null;
    if (fromEmail && fromEmail.includes('@')) {
      const domain = fromEmail.split('@')[1]?.toLowerCase();
      if (domain) {
        const dom = await this.db.query<{ spf_status: string; dkim_status: string }>(
          `SELECT spf_status, dkim_status FROM ${SCHEMA}.sending_domains
           WHERE client_id = $1::uuid AND lower(domain) = $2 AND status != 'paused'
           ORDER BY updated_at DESC LIMIT 1`,
          [template.client_id, domain],
        );
        if (dom.rowCount) {
          domainAuth = {
            spfStatus: String(dom.rows[0].spf_status ?? 'unknown'),
            dkimStatus: String(dom.rows[0].dkim_status ?? 'unknown'),
          };
        }
      }
    }
    return runTemplatePreflight({
      subject: template.subject_template,
      htmlBody: template.html_body,
      textBody: template.text_body,
      fromEmail,
      domainAuth,
    });
  }

  async listCampaigns(params: {
    clientId?: string;
    status?: string;
    limit: number;
    offset: number;
  }): Promise<EmailListResponse<EmailCampaignRow>> {
    const values: unknown[] = [];
    const clauses = ['1=1'];
    let idx = 1;
    if (params.clientId) {
      clauses.push(`cam.client_id = $${idx++}::uuid`);
      values.push(params.clientId);
    }
    if (params.status) {
      clauses.push(`cam.status = $${idx++}`);
      values.push(params.status);
    }
    const count = await this.db.query<{ c: string }>(
      `SELECT COUNT(*) AS c FROM ${SCHEMA}.campaigns cam WHERE ${clauses.join(' AND ')}`,
      values,
    );
    values.push(params.limit, params.offset);
    const result = await this.db.query(
      `SELECT cam.id::text, cam.client_id::text, cl.name AS client_name, cam.workspace_id::text,
              cam.name, cam.campaign_type, cam.segment_id::text, seg.name AS segment_name,
              cam.template_id::text, tmpl.name AS template_name, cam.status, cam.scheduled_at,
              cam.sent_at, cam.audience_count, cam.created_by, cam.created_at, cam.updated_at
       FROM ${SCHEMA}.campaigns cam
       JOIN clients cl ON cl.id = cam.client_id
       LEFT JOIN ${SCHEMA}.segments seg ON seg.id = cam.segment_id
       JOIN ${SCHEMA}.templates tmpl ON tmpl.id = cam.template_id
       WHERE ${clauses.join(' AND ')}
       ORDER BY cam.updated_at DESC
       LIMIT $${idx++} OFFSET $${idx}`,
      values,
    );
    return {
      ok: true,
      items: result.rows.map((r) => this.mapCampaign(r)),
      total: Number(count.rows[0]?.c ?? 0),
      limit: params.limit,
      offset: params.offset,
    };
  }

  async createCampaign(params: {
    clientId: string;
    name: string;
    templateId: string;
    segmentId?: string;
    campaignType?: string;
    actor: string;
  }): Promise<EmailCampaignRow> {
    const ws = await this.db.query<{ id: string }>(
      `SELECT id::text FROM ${SCHEMA}.workspaces WHERE client_id = $1::uuid LIMIT 1`,
      [params.clientId],
    );
    if (!ws.rowCount) {
      throw new BadRequestException({ error: 'workspace_required' });
    }
    const tmpl = await this.getTemplate(params.templateId);
    if (!tmpl || tmpl.client_id !== params.clientId) {
      throw new BadRequestException({ error: 'template_invalid' });
    }
    if (params.segmentId) {
      const seg = await this.getSegment(params.segmentId);
      if (!seg || seg.client_id !== params.clientId) {
        throw new BadRequestException({ error: 'segment_invalid' });
      }
    }
    const audience =
      params.segmentId != null
        ? (await this.getSegment(params.segmentId))?.member_count ?? null
        : null;
    const result = await this.db.query(
      `INSERT INTO ${SCHEMA}.campaigns (
         client_id, workspace_id, name, campaign_type, segment_id, template_id,
         audience_count, created_by, status
       ) VALUES ($1::uuid, $2::uuid, $3, $4, $5::uuid, $6::uuid, $7, $8, 'draft')
       RETURNING id::text`,
      [
        params.clientId,
        ws.rows[0].id,
        params.name.trim(),
        params.campaignType?.trim() || 'broadcast',
        params.segmentId ?? null,
        params.templateId,
        audience,
        params.actor,
      ],
    );
    const id = String(result.rows[0].id);
    await this.audit({
      clientId: params.clientId,
      actor: params.actor,
      action: 'campaign_created',
      entityType: 'campaign',
      entityId: id,
    });
    const row = await this.getCampaign(id);
    if (!row) throw new NotFoundException({ error: 'campaign_not_found' });
    return row;
  }

  async getCampaign(id: string): Promise<EmailCampaignRow | null> {
    const result = await this.db.query(
      `SELECT cam.id::text, cam.client_id::text, cl.name AS client_name, cam.workspace_id::text,
              cam.name, cam.campaign_type, cam.segment_id::text, seg.name AS segment_name,
              cam.template_id::text, tmpl.name AS template_name, cam.status, cam.scheduled_at,
              cam.sent_at, cam.audience_count, cam.created_by, cam.created_at, cam.updated_at
       FROM ${SCHEMA}.campaigns cam
       JOIN clients cl ON cl.id = cam.client_id
       LEFT JOIN ${SCHEMA}.segments seg ON seg.id = cam.segment_id
       JOIN ${SCHEMA}.templates tmpl ON tmpl.id = cam.template_id
       WHERE cam.id = $1::uuid`,
      [id],
    );
    if (!result.rowCount) return null;
    return this.mapCampaign(result.rows[0]);
  }

  async submitCampaign(id: string, actor: string): Promise<EmailCampaignRow> {
    const campaign = await this.getCampaign(id);
    if (!campaign) throw new NotFoundException({ error: 'campaign_not_found' });
    if (campaign.status !== 'draft') {
      throw new BadRequestException({ error: 'invalid_status', status: campaign.status });
    }
    const preflight = await this.preflightCampaign(id);
    if (!preflight.passed) {
      throw new BadRequestException({ error: 'preflight_failed', checks: preflight.checks });
    }
    await this.db.query(
      `UPDATE ${SCHEMA}.campaigns SET status = 'pending_approval', updated_at = NOW() WHERE id = $1::uuid`,
      [id],
    );
    await this.audit({
      clientId: campaign.client_id,
      actor,
      action: 'campaign_submitted',
      entityType: 'campaign',
      entityId: id,
    });
    const row = await this.getCampaign(id);
    if (!row) throw new NotFoundException({ error: 'campaign_not_found' });
    return row;
  }

  async approveCampaign(
    id: string,
    actor: string,
    options?: { scheduledAt?: string | null },
  ): Promise<EmailCampaignRow> {
    const campaign = await this.getCampaign(id);
    if (!campaign) throw new NotFoundException({ error: 'campaign_not_found' });
    if (campaign.status !== 'pending_approval') {
      throw new BadRequestException({ error: 'invalid_status', status: campaign.status });
    }

    const scheduledAt = options?.scheduledAt?.trim() || null;
    let scheduledIso: string | null = null;
    let nextStatus = 'approved';
    if (scheduledAt) {
      const when = new Date(scheduledAt);
      if (Number.isNaN(when.getTime())) {
        throw new BadRequestException({ error: 'invalid_scheduled_at' });
      }
      if (when.getTime() <= Date.now()) {
        throw new BadRequestException({ error: 'scheduled_at_must_be_future' });
      }
      scheduledIso = when.toISOString();
      nextStatus = 'scheduled';
    }

    await this.db.query(
      `UPDATE ${SCHEMA}.campaigns
       SET status = $2, scheduled_at = $3, updated_at = NOW()
       WHERE id = $1::uuid`,
      [id, nextStatus, scheduledIso],
    );
    await this.audit({
      clientId: campaign.client_id,
      actor,
      action: nextStatus === 'scheduled' ? 'campaign_scheduled' : 'campaign_approved',
      entityType: 'campaign',
      entityId: id,
      after: scheduledIso ? { scheduled_at: scheduledIso } : undefined,
    });
    const row = await this.getCampaign(id);
    if (!row) throw new NotFoundException({ error: 'campaign_not_found' });
    return row;
  }

  async scheduleCampaign(id: string, actor: string, scheduledAt: string): Promise<EmailCampaignRow> {
    const campaign = await this.getCampaign(id);
    if (!campaign) throw new NotFoundException({ error: 'campaign_not_found' });
    if (campaign.status !== 'approved') {
      throw new BadRequestException({ error: 'invalid_status', status: campaign.status });
    }
    const when = new Date(scheduledAt);
    if (Number.isNaN(when.getTime())) {
      throw new BadRequestException({ error: 'invalid_scheduled_at' });
    }
    if (when.getTime() <= Date.now()) {
      throw new BadRequestException({ error: 'scheduled_at_must_be_future' });
    }
    const scheduledIso = when.toISOString();
    await this.db.query(
      `UPDATE ${SCHEMA}.campaigns
       SET status = 'scheduled', scheduled_at = $2, updated_at = NOW()
       WHERE id = $1::uuid`,
      [id, scheduledIso],
    );
    await this.audit({
      clientId: campaign.client_id,
      actor,
      action: 'campaign_scheduled',
      entityType: 'campaign',
      entityId: id,
      after: { scheduled_at: scheduledIso },
    });
    const row = await this.getCampaign(id);
    if (!row) throw new NotFoundException({ error: 'campaign_not_found' });
    return row;
  }

  async preflightCampaign(id: string): Promise<EmailPreflightResponse> {
    const campaign = await this.getCampaign(id);
    if (!campaign) throw new NotFoundException({ error: 'campaign_not_found' });
    const templateChecks = await this.preflightTemplate(campaign.template_id);
    return runCampaignPreflight({
      templateChecks,
      audienceCount: campaign.audience_count,
      segmentName: campaign.segment_name,
    });
  }

  private mapSegment(r: Record<string, unknown>): EmailSegmentRow {
    return {
      id: String(r.id),
      client_id: String(r.client_id),
      client_name: String(r.client_name ?? ''),
      name: String(r.name ?? ''),
      segment_type: String(r.segment_type ?? 'dynamic'),
      definition_json: (r.definition_json ?? {}) as Record<string, unknown>,
      member_count: Number(r.member_count ?? 0),
      last_computed_at: iso(r.last_computed_at),
      status: String(r.status ?? 'active'),
      created_at: iso(r.created_at) ?? '',
      updated_at: iso(r.updated_at) ?? '',
    };
  }

  private mapTemplate(r: Record<string, unknown>): EmailTemplateRow {
    return {
      id: String(r.id),
      client_id: String(r.client_id),
      client_name: String(r.client_name ?? ''),
      name: String(r.name ?? ''),
      subject_template: String(r.subject_template ?? ''),
      html_body: String(r.html_body ?? ''),
      text_body: r.text_body ? String(r.text_body) : null,
      locale: r.locale ? String(r.locale) : null,
      version: Number(r.version ?? 1),
      status: String(r.status ?? 'draft'),
      created_at: iso(r.created_at) ?? '',
      updated_at: iso(r.updated_at) ?? '',
    };
  }

  private mapCampaign(r: Record<string, unknown>): EmailCampaignRow {
    return {
      id: String(r.id),
      client_id: String(r.client_id),
      client_name: String(r.client_name ?? ''),
      workspace_id: String(r.workspace_id),
      name: String(r.name ?? ''),
      campaign_type: String(r.campaign_type ?? 'broadcast'),
      segment_id: r.segment_id ? String(r.segment_id) : null,
      segment_name: r.segment_name ? String(r.segment_name) : null,
      template_id: String(r.template_id),
      template_name: String(r.template_name ?? ''),
      status: String(r.status ?? 'draft'),
      scheduled_at: iso(r.scheduled_at),
      sent_at: iso(r.sent_at),
      audience_count: r.audience_count == null ? null : Number(r.audience_count),
      created_by: r.created_by ? String(r.created_by) : null,
      created_at: iso(r.created_at) ?? '',
      updated_at: iso(r.updated_at) ?? '',
    };
  }
}
