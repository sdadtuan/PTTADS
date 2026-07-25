import {
  BadRequestException,
  Injectable,
  NotFoundException,
  OnModuleDestroy,
} from '@nestjs/common';
import { randomBytes } from 'node:crypto';
import { Pool } from 'pg';
import { AppConfigService } from '../config/app-config.service';
import { cmsPilotSecret, SEO_CMS_SCHEMA } from './seo-cms.constants';
import { SeoCmsPublishJobRow, SeoCmsPublishResult, SeoCmsTargetRow } from './seo-cms.types';

const SCHEMA = SEO_CMS_SCHEMA;

function parseJsonObject(raw: unknown): Record<string, unknown> {
  if (raw && typeof raw === 'object' && !Array.isArray(raw)) return raw as Record<string, unknown>;
  if (raw == null) return {};
  try {
    const parsed = JSON.parse(String(raw));
    return parsed && typeof parsed === 'object' && !Array.isArray(parsed)
      ? (parsed as Record<string, unknown>)
      : {};
  } catch {
    return {};
  }
}

@Injectable()
export class SeoCmsRepository implements OnModuleDestroy {
  private pool: Pool | null = null;

  constructor(private readonly config: AppConfigService) {}

  private get db(): Pool {
    if (!this.pool) this.pool = new Pool({ connectionString: this.config.databaseUrl });
    return this.pool;
  }

  onModuleDestroy(): void {
    void this.pool?.end();
    this.pool = null;
  }

  async getTarget(customerId: number): Promise<SeoCmsTargetRow | null> {
    const result = await this.db.query(
      `SELECT * FROM ${SCHEMA}.seo_cms_targets WHERE customer_id = $1`,
      [customerId],
    );
    const row = result.rows[0];
    if (!row) return null;
    return {
      customer_id: Number(row.customer_id),
      cms_type: String(row.cms_type ?? 'webhook'),
      base_url: String(row.base_url ?? ''),
      auth: parseJsonObject(row.auth_json),
      active: Boolean(row.active),
      updated_at: row.updated_at != null ? String(row.updated_at) : null,
    };
  }

  async upsertTarget(customerId: number, payload: Record<string, unknown>): Promise<SeoCmsTargetRow> {
    const auth = (payload.auth as Record<string, unknown>) ?? {};
    await this.db.query(
      `INSERT INTO ${SCHEMA}.seo_cms_targets (customer_id, cms_type, base_url, auth_json, active, updated_at)
       VALUES ($1,$2,$3,$4::jsonb,$5,NOW())
       ON CONFLICT (customer_id) DO UPDATE SET
         cms_type = EXCLUDED.cms_type,
         base_url = EXCLUDED.base_url,
         auth_json = EXCLUDED.auth_json,
         active = EXCLUDED.active,
         updated_at = NOW()`,
      [
        customerId,
        String(payload.cms_type ?? 'webhook'),
        String(payload.base_url ?? ''),
        JSON.stringify(auth),
        payload.active !== false,
      ],
    );
    const target = await this.getTarget(customerId);
    if (!target) throw new NotFoundException('CMS target not found after upsert');
    return target;
  }

  async listJobs(customerId: number, limit = 50): Promise<SeoCmsPublishJobRow[]> {
    const result = await this.db.query(
      `SELECT * FROM ${SCHEMA}.seo_cms_publish_jobs
       WHERE customer_id = $1 ORDER BY id DESC LIMIT $2`,
      [customerId, Math.max(1, Math.min(limit, 100))],
    );
    return result.rows.map((row) => ({
      id: Number(row.id),
      customer_id: Number(row.customer_id),
      content_id: Number(row.content_id),
      cms_type: String(row.cms_type ?? 'webhook'),
      status: String(row.status ?? 'pending'),
      remote_url: String(row.remote_url ?? ''),
      payload: parseJsonObject(row.payload_json),
      response: parseJsonObject(row.response_json),
      error_message: String(row.error_message ?? ''),
      created_at: row.created_at != null ? String(row.created_at) : null,
      finished_at: row.finished_at != null ? String(row.finished_at) : null,
    }));
  }

  private authHeaders(auth: Record<string, unknown>): Record<string, string> {
    const headers: Record<string, string> = {};
    const token = auth.bearer_token ?? auth.api_key;
    if (token) {
      const prefix = String(auth.auth_prefix ?? 'Bearer').trim();
      headers.Authorization = prefix ? `${prefix} ${String(token)}`.trim() : String(token);
    }
    const headerName = String(auth.header_name ?? '').trim();
    const headerValue = String(auth.header_value ?? '').trim();
    if (headerName && headerValue) headers[headerName] = headerValue;
    const secret = cmsPilotSecret();
    if (secret && auth.send_pilot_secret_header) {
      headers['X-PTT-CMS-Secret'] = secret;
    }
    return headers;
  }

  private buildPayload(content: Record<string, unknown>): Record<string, unknown> {
    const brief = parseJsonObject(content.brief_json ?? content.brief);
    const outline = parseJsonObject(content.outline_json ?? content.outline);
    return {
      event: 'seo.content.publish',
      title: content.title,
      slug: content.slug,
      content_type: content.content_type,
      body_html: content.body_html,
      meta_title: brief.meta_title ?? content.title,
      meta_description: brief.meta_description ?? '',
      target_keyword: brief.target_keyword ?? '',
      schema_json: outline.schema_json ?? outline.schema ?? '',
      publish_date: content.publish_date ?? new Date().toISOString().slice(0, 10),
      content_id: content.id,
      customer_id: content.customer_id,
    };
  }

  buildTestPayload(customerId: number, title = 'CMS Pilot Test'): Record<string, unknown> {
    const stamp = new Date().toISOString().replace(/[: ]/g, '-').slice(0, 19);
    return {
      event: 'seo.content.publish.test',
      title,
      slug: `cms-pilot-test-${stamp}`,
      content_type: 'blog',
      body_html: '<p>CMS webhook pilot ping from PTTADS SEO/AEO.</p>',
      meta_title: title,
      meta_description: 'Pilot webhook connectivity test',
      publish_date: new Date().toISOString().slice(0, 10),
      customer_id: customerId,
    };
  }

  private async dispatchWebhook(
    target: SeoCmsTargetRow,
    payload: Record<string, unknown>,
  ): Promise<{ status: string; response: Record<string, unknown>; remoteUrl: string }> {
    const url = target.base_url.trim();
    if (!url) {
      return { status: 'failed', response: {}, remoteUrl: '' };
    }
    const headers: Record<string, string> = {
      'Content-Type': 'application/json',
      'User-Agent': 'PTTADS-SEO-CMS/1.0',
      ...this.authHeaders(target.auth),
    };
    const resp = await fetch(url, {
      method: 'POST',
      headers,
      body: JSON.stringify(payload),
      signal: AbortSignal.timeout(30000),
    });
    const raw = await resp.text();
    let data: Record<string, unknown> = {};
    try {
      data = raw.trim() ? (JSON.parse(raw) as Record<string, unknown>) : {};
    } catch {
      data = { raw: raw.slice(0, 2000) };
    }
    if (!resp.ok) {
      return { status: 'failed', response: { status: resp.status, body: raw.slice(0, 500) }, remoteUrl: '' };
    }
    const remoteUrl = String(data.url ?? data.permalink ?? '');
    return { status: 'published', response: data, remoteUrl };
  }

  async queuePublish(contentId: number, dryRun = false): Promise<SeoCmsPublishResult> {
    const contentRes = await this.db.query(
      `SELECT * FROM ${SCHEMA}.seo_content WHERE id = $1`,
      [contentId],
    );
    const content = contentRes.rows[0];
    if (!content) throw new NotFoundException('Content không tồn tại');
    const customerId = Number(content.customer_id);
    const target = await this.getTarget(customerId);
    const payload = this.buildPayload(content);
    const cmsType = target?.cms_type ?? 'webhook';
    const ins = await this.db.query<{ id: string }>(
      `INSERT INTO ${SCHEMA}.seo_cms_publish_jobs
         (customer_id, content_id, cms_type, status, payload_json, created_at)
       VALUES ($1,$2,$3,'pending',$4::jsonb,NOW()) RETURNING id`,
      [customerId, contentId, cmsType, JSON.stringify(payload)],
    );
    const jobId = Number(ins.rows[0].id);

    if (dryRun || !target || !target.active) {
      const msg = dryRun
        ? `Dry-run — payload sẵn sàng gửi tới ${target?.base_url ?? '(chưa cấu hình)'}`
        : target
          ? 'Chưa cấu hình CMS target active'
          : 'Chưa cấu hình CMS target';
      const status = dryRun ? 'sent' : 'pending';
      await this.db.query(
        `UPDATE ${SCHEMA}.seo_cms_publish_jobs
         SET status = $2, error_message = $3, finished_at = NOW(), payload_json = $4::jsonb
         WHERE id = $1`,
        [jobId, status, msg, JSON.stringify(payload)],
      );
      return { job_id: jobId, status, message: msg, payload, dry_run: dryRun };
    }

    const { status, response, remoteUrl } = await this.dispatchWebhook(target, payload);
    await this.db.query(
      `UPDATE ${SCHEMA}.seo_cms_publish_jobs
       SET status = $2, response_json = $3::jsonb, remote_url = $4,
           error_message = $5, finished_at = NOW()
       WHERE id = $1`,
      [
        jobId,
        status,
        JSON.stringify(response),
        remoteUrl,
        status === 'published' ? '' : String(response.body ?? JSON.stringify(response)).slice(0, 500),
      ],
    );
    if (status === 'published') {
      await this.db.query(
        `UPDATE ${SCHEMA}.seo_content SET publish_date = CURRENT_DATE, updated_at = NOW() WHERE id = $1`,
        [contentId],
      );
    }
    return { job_id: jobId, status, remote_url: remoteUrl, response };
  }

  async testWebhook(customerId: number): Promise<Record<string, unknown>> {
    const target = await this.getTarget(customerId);
    if (!target?.base_url.trim()) {
      throw new BadRequestException('Chưa cấu hình CMS webhook URL cho client này');
    }
    const payload = this.buildTestPayload(customerId);
    const { status, response, remoteUrl } = await this.dispatchWebhook(target, payload);
    return {
      ok: status === 'published',
      status,
      remote_url: remoteUrl,
      response,
      webhook_url: target.base_url,
    };
  }

  generateWebhookSecret(): string {
    return randomBytes(18).toString('base64url');
  }

  async getContentPublishState(contentId: number): Promise<{ customer_id: number; workflow_status: string } | null> {
    const result = await this.db.query(
      `SELECT customer_id, workflow_status FROM ${SCHEMA}.seo_content WHERE id = $1`,
      [contentId],
    );
    const row = result.rows[0];
    if (!row) return null;
    return {
      customer_id: Number(row.customer_id),
      workflow_status: String(row.workflow_status ?? ''),
    };
  }
}
