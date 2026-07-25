import { Injectable } from '@nestjs/common';
import { SeoReportsService } from '../seo-reports/seo-reports.service';
import { SeoAutomationsRepository } from './seo-automations.repository';

@Injectable()
export class SeoAutomationsService {
  constructor(
    private readonly repo: SeoAutomationsRepository,
    private readonly reports: SeoReportsService,
  ) {}

  async status(customerId?: number) {
    const [summary, syncRuns, jobs, alerts] = await Promise.all([
      this.repo.statusSummary(),
      this.repo.syncRuns(30, customerId),
      this.repo.recentJobs(20),
      this.reports.listAlerts('open'),
    ]);
    return { ok: true, summary, sync_runs: syncRuns, recent_jobs: jobs, open_alerts: alerts };
  }

  syncRuns(customerId?: number, limit?: number) {
    return this.repo.syncRuns(limit ?? 50, customerId).then((sync_runs) => ({ ok: true, sync_runs }));
  }

  runAlertChecks() {
    return this.reports.runAlertChecks();
  }
}
