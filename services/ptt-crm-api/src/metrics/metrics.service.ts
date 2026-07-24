import { Injectable, ServiceUnavailableException } from '@nestjs/common';
import { MetricsRepository } from './metrics.repository';
import { CrossChannelSummaryResponse } from './metrics.types';

@Injectable()
export class MetricsService {
  constructor(private readonly repo: MetricsRepository) {}

  isEnabled(): boolean {
    return ['1', 'true', 'yes', 'on'].includes(
      (process.env.PTT_METRICS_CROSS_CHANNEL_ENABLED ?? '1').trim().toLowerCase(),
    );
  }

  async crossChannelSummary(query: {
    days?: string;
    client_id?: string;
    date_from?: string;
    date_to?: string;
  }): Promise<CrossChannelSummaryResponse> {
    if (!this.isEnabled()) {
      return {
        ok: false,
        window_days: 0,
        date_from: '',
        date_to: '',
        client_id: query.client_id?.trim() || null,
        totals: { spend: 0, leads_crm: 0, cpl: null },
        channels: [],
      };
    }
    if (!(await this.repo.pgPerformanceReady())) {
      throw new ServiceUnavailableException({ ok: false, error: 'daily_performance_not_ready' });
    }

    const windowDays = Math.min(Math.max(Number(query.days ?? 7) || 7, 1), 90);
    const dateTo =
      (query.date_to ?? '').trim() ||
      new Date().toISOString().slice(0, 10);
    const dateFrom =
      (query.date_from ?? '').trim() ||
      new Date(Date.parse(`${dateTo}T00:00:00Z`) - (windowDays - 1) * 86400000)
        .toISOString()
        .slice(0, 10);
    const clientId = query.client_id?.trim() || undefined;

    const channels = await this.repo.fetchCrossChannelSummary({
      dateFrom,
      dateTo,
      clientId,
    });
    const spend = channels.reduce((sum, c) => sum + c.spend, 0);
    const leads = channels.reduce((sum, c) => sum + c.leads_crm, 0);

    return {
      ok: true,
      window_days: windowDays,
      date_from: dateFrom,
      date_to: dateTo,
      client_id: clientId ?? null,
      totals: {
        spend,
        leads_crm: leads,
        cpl: leads > 0 ? Math.round(spend / leads) : null,
      },
      channels,
    };
  }
}
