import { BadRequestException, Injectable, ServiceUnavailableException } from '@nestjs/common';
import { JobQueueRepository } from '../webhooks/job-queue.repository';
import { SeoAdminRepository } from './seo-admin.repository';
import {
  encryptSeoRefreshToken,
  exchangeSeoAuthorizationCode,
  opsWebBaseUrl,
  parseSeoOAuthState,
  seoOAuthAuthorizationUrl,
  seoOAuthConfigured,
  type SeoOAuthProvider,
} from './seo-oauth.util';
import {
  SeoClientSettings,
  SeoClientTasksResponse,
  SeoClientWorkspaceResponse,
  SeoClientsListResponse,
  SeoHubResponse,
  SeoOAuthStartResponse,
  SeoSettingsUpdateBody,
  SeoSyncTriggerResponse,
} from './seo-admin.types';

const SYNC_SOURCES: Record<string, 'seo_gsc_sync' | 'seo_ga4_sync'> = {
  gsc: 'seo_gsc_sync',
  ga4: 'seo_ga4_sync',
};

@Injectable()
export class SeoAdminService {
  constructor(
    private readonly repo: SeoAdminRepository,
    private readonly jobQueue: JobQueueRepository,
  ) {}

  async hub(params: {
    customerId?: number;
    days?: number;
    market?: string;
  }): Promise<SeoHubResponse> {
    return this.repo.hubSummary({
      customerId: params.customerId,
      days: params.days ?? 90,
      market: params.market?.trim() || undefined,
    });
  }

  async listClients(params: {
    customerId?: number;
    market?: string;
  }): Promise<SeoClientsListResponse> {
    const hub = await this.hub(params);
    return {
      ok: true,
      clients: hub.clients,
      total: hub.clients.length,
    };
  }

  async getClientWorkspace(customerId: number): Promise<SeoClientWorkspaceResponse> {
    return this.repo.getClientWorkspace(customerId);
  }

  async getSettings(customerId: number): Promise<{ ok: boolean; settings: SeoClientSettings }> {
    const settings = await this.repo.getSettings(customerId);
    return { ok: true, settings };
  }

  async updateSettings(
    customerId: number,
    body: SeoSettingsUpdateBody,
  ): Promise<{ ok: boolean; settings: SeoClientSettings }> {
    const settings = await this.repo.upsertSettings(customerId, body);
    return { ok: true, settings };
  }

  async listTasks(customerId: number): Promise<SeoClientTasksResponse> {
    return this.repo.listClientTasks(customerId);
  }

  async triggerSync(customerId: number, sourceRaw: string): Promise<SeoSyncTriggerResponse> {
    const source = sourceRaw.trim().toLowerCase();
    const jobType = SYNC_SOURCES[source];
    if (!jobType) {
      throw new BadRequestException({ error: 'invalid_sync_source', allowed: Object.keys(SYNC_SOURCES) });
    }
    const syncRunId = await this.repo.createSyncRun(
      customerId,
      source === 'gsc' ? 'gsc_oauth' : 'ga4_oauth',
    );
    const today = new Date().toISOString().slice(0, 10);
    const idempotencyKey = `${jobType}:${customerId}:${today}`;
    const job = await this.jobQueue.enqueueSeoSyncJob({
      jobType,
      payload: { customer_id: customerId, days: 28, sync_run_id: syncRunId },
      idempotencyKey,
    });
    if (!job) {
      return {
        ok: true,
        source,
        customer_id: customerId,
        mode: 'none',
        job_id: null,
        sync_run_id: syncRunId,
        error: 'job_queue_disabled',
      };
    }
    return {
      ok: true,
      source,
      customer_id: customerId,
      mode: 'queue',
      job_id: job.id,
      sync_run_id: syncRunId,
    };
  }

  oauthStart(
    customerId: number,
    provider: SeoOAuthProvider,
    opts?: { siteUrl?: string; propertyId?: string },
  ): SeoOAuthStartResponse {
    if (!seoOAuthConfigured(provider)) {
      throw new ServiceUnavailableException({
        error: provider === 'gsc' ? 'missing_gsc_oauth_env' : 'missing_ga4_oauth_env',
        hint: 'Cấu hình PTT_GSC_OAUTH_* / PTT_GA4_OAUTH_* trên Nest',
      });
    }
    const url = seoOAuthAuthorizationUrl({
      customerId,
      provider,
      siteUrl: opts?.siteUrl?.trim(),
      propertyId: opts?.propertyId?.trim(),
    });
    return {
      ok: true,
      authorization_url: url,
      provider,
      customer_id: customerId,
      configured: true,
    };
  }

  async oauthCallback(
    provider: SeoOAuthProvider,
    code: string | undefined,
    state: string | undefined,
    error: string | undefined,
  ): Promise<string> {
    const opsWeb = opsWebBaseUrl();
    let customerId = 0;
    try {
      const parsed = parseSeoOAuthState(String(state ?? ''));
      customerId = parsed.customer_id;
    } catch {
      return `${opsWeb}/seo/clients?oauth_error=invalid_state`;
    }
    const base = `${opsWeb}/seo/clients/${customerId}?tab=settings`;
    if (error) {
      return `${base}&${provider}_oauth_error=${encodeURIComponent(error)}`;
    }
    if (!code?.trim()) {
      return `${base}&${provider}_oauth_error=missing_code`;
    }
    try {
      const parsed = parseSeoOAuthState(String(state ?? ''));
      if (parsed.provider !== provider) {
        throw new BadRequestException({ error: 'provider_mismatch' });
      }
      const tokens = await exchangeSeoAuthorizationCode(code, provider);
      const encrypted = encryptSeoRefreshToken(tokens.refresh_token);
      await this.repo.saveOAuthIntegration(customerId, provider, {
        refresh_token_encrypted: encrypted,
        site_url: parsed.site_url,
        property_id: parsed.property_id,
      });
      return `${base}&${provider}_connected=1`;
    } catch (err) {
      const message = err instanceof Error ? err.message : 'oauth_failed';
      return `${base}&${provider}_oauth_error=${encodeURIComponent(message)}`;
    }
  }
}
