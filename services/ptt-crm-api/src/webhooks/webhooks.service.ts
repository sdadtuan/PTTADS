import { Injectable, Logger, ServiceUnavailableException, UnauthorizedException } from '@nestjs/common';
import { Request } from 'express';
import { AppConfigService } from '../config/app-config.service';
import { JobQueueRepository } from './job-queue.repository';
import {
  metaConfigFromEnv,
  normalizeWebhookChannel,
  parseMetaWebhook,
  parseFacebookWebhookJson,
} from './meta-webhook.parser';
import { extractMetaLeadgenContext } from './meta-webhook-context';
import { MetaWebhookRepository } from './meta-webhook.repository';
import { MetaOpsWebhookService } from './meta-ops-webhook.service';
import { parseEmailWebhook } from './email-webhook.parser';
import { parseGoogleWebhook } from './google-webhook.parser';
import { parseZaloWebhook } from './zalo-webhook.parser';

export interface WebhookHandleResult {
  kind: 'json' | 'challenge';
  status: number;
  body: Record<string, unknown> | string;
  contentType?: string;
}

@Injectable()
export class WebhooksService {
  private readonly logger = new Logger(WebhooksService.name);

  constructor(
    private readonly config: AppConfigService,
    private readonly jobQueue: JobQueueRepository,
    private readonly metaWebhookRepo: MetaWebhookRepository,
    private readonly metaOpsWebhookService: MetaOpsWebhookService,
  ) {}

  listChannels(): Record<string, unknown> {
    return {
      channels: ['meta', 'zalo', 'google', 'email'],
      capabilities: {
        meta: { supports_webhooks: true, supports_lead_ingest: true, nest_native: true },
        zalo: { supports_webhooks: true, supports_lead_ingest: true, nest_native: true },
        google: { supports_webhooks: true, supports_lead_ingest: true, nest_native: true },
        email: { supports_webhooks: true, supports_lead_ingest: false, nest_native: true },
      },
      routing: {
        meta: this.config.webhooksNestMetaEnabled ? 'nest' : 'none',
        zalo: this.config.webhooksNestZaloEnabled ? 'nest' : 'none',
        google: this.config.webhooksNestGoogleEnabled ? 'nest' : 'none',
        email: this.config.webhooksNestEmailEnabled ? 'nest' : 'none',
        default_fallback: 'none',
      },
    };
  }

  async handle(channelRaw: string, req: Request): Promise<WebhookHandleResult> {
    const channel = normalizeWebhookChannel(channelRaw);
    if (channel === 'meta' && this.config.webhooksNestMetaEnabled) {
      return this.handleMeta(req);
    }
    if (channel === 'email' && this.config.webhooksNestEmailEnabled) {
      return this.handleEmail(req);
    }
    if (channel === 'zalo' && this.config.webhooksNestZaloEnabled) {
      return this.handleZalo(req);
    }
    if (channel === 'google' && this.config.webhooksNestGoogleEnabled) {
      return this.handleGoogle(req);
    }
    throw new ServiceUnavailableException({ error: 'channel_not_migrated', channel });
  }

  private async handleMeta(req: Request): Promise<WebhookHandleResult> {
    const headers = req.headers as Record<string, string | string[] | undefined>;
    const rawBody = Buffer.isBuffer(req.rawBody)
      ? req.rawBody
      : Buffer.from(typeof req.body === 'string' ? req.body : JSON.stringify(req.body ?? {}));
    const query = req.query as Record<string, string>;
    const headerClientId = String(req.headers['x-ptt-client-id'] ?? query.client_id ?? '');
    const correlationId = String(req.headers['x-correlation-id'] ?? cryptoRandomUuid());

    const mode = query['hub.mode'] ?? query.hub_mode;
    if (mode === 'subscribe') {
      const parsed = await parseMetaWebhook({
        headers,
        rawBody,
        query,
        clientId: headerClientId,
        config: metaConfigFromEnv(),
      });
      if (parsed.challenge !== undefined) {
        return {
          kind: 'challenge',
          status: 200,
          body: String(parsed.challenge),
          contentType: 'text/plain',
        };
      }
      throw new UnauthorizedException({
        verified: false,
        reject_reason: parsed.reject_reason ?? 'Invalid verify token',
      });
    }

    const payload = parseFacebookWebhookJson(rawBody);
    const ctx = extractMetaLeadgenContext(payload);
    const resolvedClientId = await this.metaWebhookRepo.resolveClientId({
      headerClientId,
      pageIds: ctx.pageIds,
      formIds: ctx.formIds,
    });
    const pageToken = await this.metaWebhookRepo.resolvePageAccessToken(resolvedClientId);
    const effectiveClientId =
      resolvedClientId ??
      this.metaWebhookRepo.normalizeClientUuid(headerClientId) ??
      'unknown';

    const parsed = await parseMetaWebhook({
      headers,
      rawBody,
      query,
      clientId: effectiveClientId,
      resolvedClientId,
      pageAccessToken: pageToken,
      config: metaConfigFromEnv(),
    });

    if (!parsed.verified) {
      throw new UnauthorizedException({
        verified: false,
        reject_reason: parsed.reject_reason ?? 'Unauthorized',
      });
    }

    const response: Record<string, unknown> = {
      verified: true,
      channel: 'meta',
      correlation_id: correlationId,
      lead_count: parsed.leads.length,
      events: parsed.events,
      handler: 'nest',
      resolved_client_id: resolvedClientId,
      page_ids: parsed.page_ids ?? ctx.pageIds,
      form_ids: parsed.form_ids ?? ctx.formIds,
    };

    const opsResult = await this.metaOpsWebhookService.processPayload(payload);
    response.ops_webhook = opsResult;

    if (!parsed.leads.length) {
      return { kind: 'json', status: 200, body: response };
    }

    try {
      const enqueue = await this.jobQueue.enqueueIngestLeads(parsed.leads, {
        channel: 'meta',
        correlationId,
        clientId: effectiveClientId !== 'unknown' ? effectiveClientId : undefined,
      });
      response.mode = enqueue.mode;
      response.accepted = true;
      response.job_ids = enqueue.jobs.map((j) => j.id);
      response.jobs = enqueue.jobs;
      this.logger.log(
        `webhook v1 channel=meta mode=${enqueue.mode} leads=${parsed.leads.length} client=${effectiveClientId} correlation_id=${correlationId}`,
      );
    } catch (err) {
      this.logger.error(`webhook enqueue failed correlation_id=${correlationId}`, err as Error);
      throw new ServiceUnavailableException({
        verified: true,
        accepted: false,
        error: err instanceof Error ? err.message : 'enqueue_failed',
      });
    }

    return { kind: 'json', status: 200, body: response };
  }

  private async handleEmail(req: Request): Promise<WebhookHandleResult> {
    const rawBody = Buffer.isBuffer(req.rawBody)
      ? req.rawBody
      : Buffer.from(typeof req.body === 'string' ? req.body : JSON.stringify(req.body ?? {}));
    const query = req.query as Record<string, string>;
    const clientId = String(req.headers['x-ptt-client-id'] ?? query.client_id ?? '');
    const correlationId = String(req.headers['x-correlation-id'] ?? cryptoRandomUuid());
    const verify = ['1', 'true', 'yes', 'on'].includes(
      (process.env.PTT_EMAIL_WEBHOOK_VERIFY ?? '0').trim().toLowerCase(),
    );

    const parsed = parseEmailWebhook({
      headers: req.headers as Record<string, string | string[] | undefined>,
      rawBody,
      clientId,
      verify,
    });

    if (!parsed.verified) {
      throw new UnauthorizedException({
        verified: false,
        reject_reason: parsed.reject_reason ?? 'Unauthorized',
      });
    }

    const response: Record<string, unknown> = {
      verified: true,
      channel: 'email',
      correlation_id: correlationId,
      event_count: parsed.events.length,
      handler: 'nest',
    };

    if (!parsed.events.length) {
      return { kind: 'json', status: 200, body: response };
    }

    try {
      const enqueue = await this.jobQueue.enqueueEmailJob({
        jobType: 'email_engagement_ingest',
        payload: { events: parsed.events, client_id: clientId },
        idempotencyKey: `email_engagement:${correlationId}:${parsed.events.length}`,
        correlationId,
        clientId,
      });
      response.mode = 'queue';
      response.accepted = true;
      response.job_id = enqueue.id;
      this.logger.log(
        `webhook v1 channel=email events=${parsed.events.length} correlation_id=${correlationId}`,
      );
    } catch (err) {
      this.logger.error(`email webhook enqueue failed correlation_id=${correlationId}`, err as Error);
      throw new ServiceUnavailableException({
        verified: true,
        accepted: false,
        error: err instanceof Error ? err.message : 'enqueue_failed',
      });
    }

    return { kind: 'json', status: 200, body: response };
  }

  private async handleZalo(req: Request): Promise<WebhookHandleResult> {
    const headers = req.headers as Record<string, string | string[] | undefined>;
    const rawBody = Buffer.isBuffer(req.rawBody)
      ? req.rawBody
      : Buffer.from(typeof req.body === 'string' ? req.body : JSON.stringify(req.body ?? {}));
    const query = req.query as Record<string, string>;
    const clientId = String(req.headers['x-ptt-client-id'] ?? query.client_id ?? '');
    const correlationId = String(req.headers['x-correlation-id'] ?? cryptoRandomUuid());

    const parsed = parseZaloWebhook({ headers, rawBody, clientId });

    if (!parsed.verified) {
      throw new UnauthorizedException({
        verified: false,
        reject_reason: parsed.reject_reason ?? 'Unauthorized',
      });
    }

    const response: Record<string, unknown> = {
      verified: true,
      channel: 'zalo',
      correlation_id: correlationId,
      lead_count: parsed.leads.length,
      events: parsed.events,
      handler: 'nest',
    };

    if (!parsed.leads.length) {
      return { kind: 'json', status: 200, body: response };
    }

    try {
      const enqueue = await this.jobQueue.enqueueIngestLeads(parsed.leads, {
        channel: 'zalo',
        correlationId,
        clientId,
      });
      response.mode = enqueue.mode;
      response.accepted = true;
      response.job_ids = enqueue.jobs.map((j) => j.id);
      response.jobs = enqueue.jobs;
      this.logger.log(
        `webhook v1 channel=zalo mode=${enqueue.mode} leads=${parsed.leads.length} correlation_id=${correlationId}`,
      );
    } catch (err) {
      this.logger.error(`webhook enqueue failed correlation_id=${correlationId}`, err as Error);
      throw new ServiceUnavailableException({
        verified: true,
        accepted: false,
        error: err instanceof Error ? err.message : 'enqueue_failed',
      });
    }

    return { kind: 'json', status: 200, body: response };
  }

  private async handleGoogle(req: Request): Promise<WebhookHandleResult> {
    const headers = req.headers as Record<string, string | string[] | undefined>;
    const rawBody = Buffer.isBuffer(req.rawBody)
      ? req.rawBody
      : Buffer.from(typeof req.body === 'string' ? req.body : JSON.stringify(req.body ?? {}));
    const query = req.query as Record<string, string>;
    const clientId = String(req.headers['x-ptt-client-id'] ?? query.client_id ?? '');
    const correlationId = String(req.headers['x-correlation-id'] ?? cryptoRandomUuid());

    const parsed = parseGoogleWebhook({ headers, rawBody, clientId });

    if (!parsed.verified) {
      throw new UnauthorizedException({
        verified: false,
        reject_reason: parsed.reject_reason ?? 'Unauthorized',
      });
    }

    const response: Record<string, unknown> = {
      verified: true,
      channel: 'google',
      correlation_id: correlationId,
      lead_count: parsed.leads.length,
      events: parsed.events,
      handler: 'nest',
    };

    if (!parsed.leads.length) {
      return { kind: 'json', status: 200, body: response };
    }

    try {
      const enqueue = await this.jobQueue.enqueueIngestLeads(parsed.leads, {
        channel: 'google',
        correlationId,
        clientId,
      });
      response.mode = enqueue.mode;
      response.accepted = true;
      response.job_ids = enqueue.jobs.map((j) => j.id);
      response.jobs = enqueue.jobs;
      this.logger.log(
        `webhook v1 channel=google mode=${enqueue.mode} leads=${parsed.leads.length} correlation_id=${correlationId}`,
      );
    } catch (err) {
      this.logger.error(`webhook enqueue failed correlation_id=${correlationId}`, err as Error);
      throw new ServiceUnavailableException({
        verified: true,
        accepted: false,
        error: err instanceof Error ? err.message : 'enqueue_failed',
      });
    }

    return { kind: 'json', status: 200, body: response };
  }
}

function cryptoRandomUuid(): string {
  return globalThis.crypto?.randomUUID?.() ?? `corr-${Date.now()}`;
}
