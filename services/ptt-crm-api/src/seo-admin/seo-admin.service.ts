import { BadRequestException, Injectable } from '@nestjs/common';
import { JobQueueRepository } from '../webhooks/job-queue.repository';
import { SeoAdminRepository } from './seo-admin.repository';
import {
  SeoClientSettings,
  SeoClientTasksResponse,
  SeoClientWorkspaceResponse,
  SeoClientsListResponse,
  SeoHubResponse,
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
}
