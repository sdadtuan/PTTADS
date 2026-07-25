import { Injectable } from '@nestjs/common';
import { SeoReportsRepository } from './seo-reports.repository';
import { SeoAlertRow, SeoDashboardResponse, SeoReportScheduleRow } from './seo-reports.types';

@Injectable()
export class SeoReportsService {
  constructor(private readonly repo: SeoReportsRepository) {}

  dashboard(customerId: number | null, type: string): Promise<SeoDashboardResponse> {
    return this.repo.dashboard(customerId, type);
  }

  exportDashboard(
    customerId: number | null,
    type: string,
    format: string,
    customerLabel?: string,
  ): Promise<{ contentType: string; body: string; filename: string }> {
    return this.repo.dashboard(customerId, type).then((data) => {
      const stamp = new Date().toISOString().slice(0, 10);
      if (format === 'csv') {
        return {
          contentType: 'text/csv; charset=utf-8',
          body: this.repo.buildCsvExport(data),
          filename: `seo-aeo-${type}-${stamp}.csv`,
        };
      }
      return {
        contentType: 'text/html; charset=utf-8',
        body: this.repo.buildHtmlExport(data, customerLabel),
        filename: `seo-aeo-${type}-${stamp}.html`,
      };
    });
  }

  listSchedules(customerId?: number): Promise<SeoReportScheduleRow[]> {
    return this.repo.listSchedules(customerId);
  }

  createSchedule(customerId: number, payload: Record<string, unknown>): Promise<SeoReportScheduleRow> {
    return this.repo.createSchedule(customerId, payload);
  }

  listAlerts(status?: string): Promise<SeoAlertRow[]> {
    return this.repo.listAlerts(status ?? 'open');
  }

  resolveAlert(alertId: number): Promise<{ ok: boolean }> {
    return this.repo.resolveAlert(alertId).then(() => ({ ok: true }));
  }

  runAlertChecks(): Promise<{ ok: boolean; created: Array<{ id: number; type: string }> }> {
    return this.repo.runAlertChecks().then((created) => ({ ok: true, created }));
  }
}
