import { Injectable } from '@nestjs/common';
import { SeoAeoService } from '../seo-aeo/seo-aeo.service';
import { SeoRanksRepository } from '../seo-ranks/seo-ranks.repository';
import { SeoTechnicalRepository } from '../seo-technical/seo-technical.repository';
import {
  aeoScheduleCronEnabled,
  aeoScheduleMaxClients,
  crawlConnectorEnabled,
  crawlReminderEnabled,
  crawlReminderDays,
  cwvCronEnabled,
  cwvMaxClients,
  cwvPerClientLimit,
  rankLiveEnabled,
  rankLiveMaxClients,
} from './seo-cron.constants';
import { SeoCronRepository } from './seo-cron.repository';
import { SeoGateCronResponse } from './seo-cron.types';

@Injectable()
export class SeoCronService {
  constructor(
    private readonly repo: SeoCronRepository,
    private readonly technical: SeoTechnicalRepository,
    private readonly aeo: SeoAeoService,
    private readonly ranks: SeoRanksRepository,
  ) {}

  cronStatus() {
    return {
      ok: true,
      gate_d: {
        cwv_enabled: cwvCronEnabled(),
        crawl_reminder_enabled: crawlReminderEnabled(),
        aeo_schedule_enabled: aeoScheduleCronEnabled(),
      },
      gate_e: {
        crawl_connector_enabled: crawlConnectorEnabled(),
        rank_live_enabled: rankLiveEnabled(),
      },
    };
  }

  async runGateD(): Promise<SeoGateCronResponse> {
    const out: SeoGateCronResponse = { ok: true, jobs: {} };

    if (cwvCronEnabled()) {
      const customerIds = await this.repo.listSeoCustomerIds(cwvMaxClients());
      let captured = 0;
      const errors: string[] = [];
      for (const cid of customerIds) {
        try {
          const result = await this.technical.captureCwv(cid, cwvPerClientLimit());
          captured += result.captured;
          errors.push(...result.errors);
        } catch (err) {
          errors.push(`${cid}: ${err instanceof Error ? err.message : String(err)}`);
        }
      }
      out.jobs.cwv_capture = {
        ok: errors.length === 0 || captured > 0,
        customers: customerIds.length,
        captured,
        errors: errors.slice(0, 20),
      };
      if (!out.jobs.cwv_capture.ok) out.ok = false;
    } else {
      out.jobs.cwv_capture = { ok: true, skipped: true, reason: 'cwv_disabled' };
    }

    if (aeoScheduleCronEnabled()) {
      const customerIds = await this.repo.listSeoCustomerIds(aeoScheduleMaxClients());
      const results: Array<Record<string, unknown>> = [];
      for (const cid of customerIds) {
        const scan = await this.aeo.enqueueScan(cid);
        results.push({ customer_id: cid, ...scan });
      }
      out.jobs.aeo_schedule = { ok: true, customers: customerIds.length, results };
    } else {
      out.jobs.aeo_schedule = { ok: true, skipped: true, reason: 'aeo_schedule_disabled' };
    }

    if (crawlReminderEnabled()) {
      out.jobs.crawl_reminder = await this.repo.runCrawlReminders(crawlReminderDays());
    } else {
      out.jobs.crawl_reminder = { ok: true, skipped: true, reason: 'crawl_reminder_disabled' };
    }

    for (const job of Object.values(out.jobs)) {
      if (job.ok === false && !job.skipped) out.ok = false;
    }
    return out;
  }

  async runGateE(): Promise<SeoGateCronResponse> {
    const out: SeoGateCronResponse = { ok: true, jobs: {} };

    if (crawlConnectorEnabled()) {
      out.jobs.crawl_connector = await this.repo.runCrawlScheduleChecks();
    } else {
      out.jobs.crawl_connector = { ok: true, skipped: true, reason: 'crawl_connector_disabled' };
    }

    if (rankLiveEnabled()) {
      const customerIds = await this.repo.listSeoCustomerIds(rankLiveMaxClients());
      const results: Array<Record<string, unknown>> = [];
      for (const cid of customerIds) {
        try {
          const result = await this.ranks.captureRanks(cid);
          results.push({ customer_id: cid, ok: true, result });
        } catch (err) {
          results.push({
            customer_id: cid,
            ok: false,
            error: err instanceof Error ? err.message : String(err),
          });
        }
      }
      const okCount = results.filter((r) => r.ok).length;
      out.jobs.rank_live = { ok: okCount === customerIds.length, customers: customerIds.length, results };
      if (!out.jobs.rank_live.ok) out.ok = false;
    } else {
      out.jobs.rank_live = { ok: true, skipped: true, reason: 'rank_live_disabled' };
    }

    for (const job of Object.values(out.jobs)) {
      if (job.ok === false && !job.skipped) out.ok = false;
    }
    return out;
  }
}
