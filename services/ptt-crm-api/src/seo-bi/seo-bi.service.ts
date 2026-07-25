import { Injectable } from '@nestjs/common';
import { JobQueueRepository } from '../webhooks/job-queue.repository';
import {
  clickhouseConfigured,
  seoBiExportEnabled,
} from './seo-bi.constants';
import { SeoBiRepository } from './seo-bi.repository';
import {
  SeoBiDashboardResponse,
  SeoBiParityResponse,
  SeoBiStatusResponse,
  SeoClickhouseExportResult,
} from './seo-bi.types';

function envFlag(name: string, defaultOn = true): boolean {
  const raw = (process.env[name] ?? (defaultOn ? '1' : '0')).trim().toLowerCase();
  return raw !== '0' && raw !== 'false' && raw !== 'no';
}

@Injectable()
export class SeoBiService {
  constructor(
    private readonly repo: SeoBiRepository,
    private readonly jobQueue: JobQueueRepository,
  ) {}

  status(): SeoBiStatusResponse {
    const cwvStub = ['1', 'true', 'yes'].includes((process.env.PTT_CWV_STUB ?? '0').trim().toLowerCase());
    return {
      ok: true,
      clickhouse_configured: clickhouseConfigured(),
      bi_export_enabled: seoBiExportEnabled(),
      cwv_stub: cwvStub,
      serp_provider: (process.env.PTT_SERP_PROVIDER ?? 'stub').trim(),
      grafana_dashboard: 'deploy/grafana/seo-ops-dashboard.json',
      gate_d_flags: {
        cwv_enabled: envFlag('PTT_CWV_ENABLED'),
        crawl_reminder_enabled: envFlag('PTT_CRAWL_REMINDER_ENABLED'),
        aeo_schedule_enabled: envFlag('PTT_AEO_SCHEDULE_ENABLED'),
        teams_webhook: Boolean((process.env.PTT_SEO_TEAMS_WEBHOOK ?? '').trim()),
      },
      gate_e_flags: {
        crawl_connector_enabled: envFlag('PTT_CRAWL_CONNECTOR_ENABLED'),
        rank_live_enabled: envFlag('PTT_RANK_LIVE_ENABLED'),
        cms_auto_publish: envFlag('PTT_SEO_CMS_AUTO_PUBLISH', false),
        enterprise_enabled: envFlag('PTT_SEO_ENTERPRISE_ENABLED', false),
      },
    };
  }

  dashboard(customerId: number | null, days?: number): Promise<SeoBiDashboardResponse> {
    return this.repo.biDashboard(customerId, days ?? 28);
  }

  parity(days?: number): Promise<SeoBiParityResponse> {
    return this.repo.paritySample(days ?? 7);
  }

  async exportClickhouse(factDate?: string): Promise<SeoClickhouseExportResult> {
    if (!seoBiExportEnabled()) {
      return { ok: false, mode: 'disabled', error: 'bi_export_disabled' };
    }
    const stamp = factDate ?? new Date().toISOString().slice(0, 10);
    const idem = `seo_clickhouse_export:${stamp}`;
    const job = await this.jobQueue.enqueueSeoClickhouseExportJob({
      payload: { fact_date: stamp },
      idempotencyKey: idem,
    });
    if (job) {
      return { ok: true, job_id: job.id, mode: 'queue' };
    }
    return { ok: false, mode: 'none', error: 'job_queue_unavailable' };
  }

  attribution(customerId: number, days?: number) {
    return this.repo.attributionSummary(customerId, days ?? 28).then(async (summary) => ({
      ok: true,
      summary,
      top_landing_pages: await this.repo.topOrganicLandingPages(customerId, days ?? 28, 10),
    }));
  }
}
