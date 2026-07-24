import { Injectable, ServiceUnavailableException } from '@nestjs/common';
import { buildMetaAttributionMeta } from '../meta-attribution.util';
import { computeRoas } from '../performance/performance.util';
import { MetaIntelligenceRepository } from './meta-intelligence.repository';
import {
  MetaAnomaliesListResponse,
  MetaAnomalyRow,
  MetaBudgetRecommendationsResponse,
  MetaRoasResponse,
} from './meta-intelligence.types';
import {
  computeSpikePct,
  detectCampaignAnomalies,
  envFloat,
  envInt,
  recommendBudgetChange,
} from './meta-intelligence.util';

@Injectable()
export class MetaIntelligenceService {
  constructor(private readonly repo: MetaIntelligenceRepository) {}

  isAnomalyEnabled(): boolean {
    return ['1', 'true', 'yes', 'on'].includes(
      (process.env.PTT_META_ANOMALY_ENABLED ?? '0').trim().toLowerCase(),
    );
  }

  isRoasEnabled(): boolean {
    return ['1', 'true', 'yes', 'on'].includes(
      (process.env.PTT_META_ROAS_ENABLED ?? '0').trim().toLowerCase(),
    );
  }

  isRecommendEnabled(): boolean {
    return this.isAnomalyEnabled() || this.isRoasEnabled();
  }

  private async ensurePerformanceReady(): Promise<void> {
    if (!(await this.repo.pgDailyPerformanceReady())) {
      throw new ServiceUnavailableException({ ok: false, error: 'daily_performance_not_ready' });
    }
  }

  private async buildAttribution(params: { clientId?: string; dateFrom: string; dateTo: string }) {
    const ctx = await this.repo.fetchAttributionContext(params);
    return buildMetaAttributionMeta({
      dateTo: ctx.throughDate,
      syncedAt: ctx.syncedAt,
      unmappedSpendPct: ctx.unmappedSpendPct,
    });
  }

  async listAnomalies(query: {
    client_id?: string;
    limit?: string;
    days?: string;
  }): Promise<MetaAnomaliesListResponse> {
    await this.ensurePerformanceReady();
    if (!this.isAnomalyEnabled()) {
      const { start, end } = this.repo.resolveWindow(query, 7);
      const { dateFrom, dateTo } = this.repo.formatWindow(start, end);
      return {
        ok: true,
        disabled: true,
        anomalies: [],
        count: 0,
        attribution: await this.buildAttribution({
          clientId: query.client_id?.trim() || undefined,
          dateFrom,
          dateTo,
        }),
      };
    }

    const limit = query.limit ? Number(query.limit) : 100;
    const { start, end } = this.repo.resolveWindow(query, envInt('PTT_META_ANOMALY_WINDOW_DAYS', 7));
    const { dateFrom, dateTo } = this.repo.formatWindow(start, end);
    const clientId = query.client_id?.trim() || undefined;
    const attribution = await this.buildAttribution({ clientId, dateFrom, dateTo });

    const stored = await this.repo.listStoredAnomalies({
      clientId,
      limit: Number.isFinite(limit) ? limit : 100,
    });
    if (stored.length) {
      const anomalies: MetaAnomalyRow[] = stored.map((row) => {
        const metric = row.metric_value != null ? Number(row.metric_value) : null;
        const threshold = row.threshold_value != null ? Number(row.threshold_value) : null;
        let spikePct: number | null = null;
        if (metric != null && threshold != null && threshold > 0 && row.alert_type !== 'roas_low') {
          spikePct = computeSpikePct(metric, threshold / (1 + envFloat('PTT_META_ANOMALY_SPIKE_PCT', 50) / 100));
        }
        return {
          id: String(row.id),
          client_id: String(row.client_id),
          client_code: row.client_code != null ? String(row.client_code) : null,
          client_name: row.client_name != null ? String(row.client_name) : null,
          external_campaign_id: row.external_campaign_id ? String(row.external_campaign_id) : null,
          alert_type: String(row.alert_type),
          severity: String(row.severity),
          metric_value: metric,
          threshold_value: threshold,
          spike_pct: spikePct,
          message: String(row.message ?? ''),
          performance_date: row.performance_date ? String(row.performance_date).slice(0, 10) : null,
          created_at: new Date(String(row.created_at)).toISOString(),
        };
      });
      return { ok: true, anomalies, count: anomalies.length, attribution };
    }

    const spikePct = envFloat('PTT_META_ANOMALY_SPIKE_PCT', 50);
    const roasMin = envFloat('PTT_META_ROAS_MIN_TARGET', 3);
    const roasMinSpend = envFloat('PTT_META_ROAS_MIN_SPEND_VND', 500_000);
    const metrics = await this.repo.listCampaignDayMetrics({ clientId, dateFrom, dateTo });
    const byCampaign = new Map<string, typeof metrics>();
    for (const row of metrics) {
      const key = `${row.client_id}:${row.external_campaign_id}`;
      const list = byCampaign.get(key) ?? [];
      list.push(row);
      byCampaign.set(key, list);
    }

    const anomalies: MetaAnomalyRow[] = [];
    for (const rows of byCampaign.values()) {
      const latest = rows[0];
      const history = rows.filter((r) => r.performance_date < latest.performance_date);
      const spendHistory = history.map((r) => r.spend);
      const cplHistory = history.filter((r) => r.leads_crm > 0).map((r) => r.spend / r.leads_crm);
      const detected = detectCampaignAnomalies({
        spendToday: latest.spend,
        leadsToday: latest.leads_crm,
        conversionValueToday: latest.conversion_value,
        spendHistory,
        cplHistory,
        spikePct,
        roasMinTarget: roasMin,
        roasMinSpend,
      });
      for (const item of detected) {
        anomalies.push({
          id: `${latest.client_id}:${latest.external_campaign_id}:${item.alert_type}:${latest.performance_date}`,
          client_id: latest.client_id,
          client_code: latest.client_code,
          client_name: latest.client_name,
          external_campaign_id: latest.external_campaign_id || null,
          alert_type: item.alert_type,
          severity: item.severity,
          metric_value: item.metric_value,
          threshold_value: item.threshold_value,
          spike_pct: item.spike_pct,
          message: item.message,
          performance_date: latest.performance_date,
          created_at: new Date().toISOString(),
        });
      }
    }

    anomalies.sort((a, b) => (b.performance_date ?? '').localeCompare(a.performance_date ?? ''));
    const capped = anomalies.slice(0, Number.isFinite(limit) ? limit : 100);
    return { ok: true, anomalies: capped, count: capped.length, attribution };
  }

  async getRoas(query: {
    client_id?: string;
    from?: string;
    to?: string;
    days?: string;
  }): Promise<MetaRoasResponse> {
    await this.ensurePerformanceReady();
    const { start, end } = this.repo.resolveWindow(query, 7);
    const { dateFrom, dateTo } = this.repo.formatWindow(start, end);
    const clientId = query.client_id?.trim() || undefined;
    const attribution = await this.buildAttribution({ clientId, dateFrom, dateTo });

    if (!this.isRoasEnabled()) {
      return {
        ok: true,
        disabled: true,
        date_from: dateFrom,
        date_to: dateTo,
        summary: {
          total_spend: 0,
          total_conversion_value: 0,
          avg_roas: null,
          roas_stub: false,
        },
        series: [],
        attribution,
      };
    }

    const rows = await this.repo.listRoasDailySeries({ clientId, dateFrom, dateTo });
    let totalSpend = 0;
    let totalConv = 0;
    const series = rows.map((row) => {
      const spend = Number(row.spend ?? 0);
      const conv = Number(row.conversion_value ?? 0);
      totalSpend += spend;
      totalConv += conv;
      const roas = computeRoas(conv, spend);
      return {
        performance_date: String(row.performance_date).slice(0, 10),
        spend: Math.round(spend * 100) / 100,
        conversion_value: Math.round(conv * 100) / 100,
        roas,
        roas_stub: roas == null && spend > 0,
      };
    });
    const avgRoas = computeRoas(totalConv, totalSpend);

    return {
      ok: true,
      date_from: dateFrom,
      date_to: dateTo,
      summary: {
        total_spend: Math.round(totalSpend * 100) / 100,
        total_conversion_value: Math.round(totalConv * 100) / 100,
        avg_roas: avgRoas,
        roas_stub: avgRoas == null && totalSpend > 0,
      },
      series,
      attribution,
    };
  }

  async listBudgetRecommendations(query: {
    client_id?: string;
    days?: string;
  }): Promise<MetaBudgetRecommendationsResponse> {
    await this.ensurePerformanceReady();
    const { start, end } = this.repo.resolveWindow(query, 7);
    const { dateFrom, dateTo } = this.repo.formatWindow(start, end);
    const clientId = query.client_id?.trim() || undefined;
    const attribution = await this.buildAttribution({ clientId, dateFrom, dateTo });

    if (!this.isRecommendEnabled()) {
      return {
        ok: true,
        disabled: true,
        read_only: true,
        date_from: dateFrom,
        date_to: dateTo,
        recommendations: [],
        count: 0,
        attribution,
      };
    }

    const decreasePct = envFloat('PTT_META_BUDGET_RECOMMEND_DECREASE_PCT', 15);
    const increasePct = envFloat('PTT_META_BUDGET_RECOMMEND_INCREASE_PCT', 10);
    const cplOver = envFloat('PTT_META_BUDGET_RECOMMEND_CPL_OVER', 1.15);
    const cplUnder = envFloat('PTT_META_BUDGET_RECOMMEND_CPL_UNDER', 0.85);
    const rows = await this.repo.listCampaignWindowMetrics({ clientId, dateFrom, dateTo });
    const recommendations = [];

    for (const row of rows) {
      if (row.target_cpl_vnd == null || row.leads_crm <= 0) continue;
      const cpl = row.spend / row.leads_crm;
      const avgDaily = row.spend / row.day_count;
      const roas = computeRoas(row.conversion_value, row.spend);
      const rec = recommendBudgetChange({
        avgDailySpend: avgDaily,
        cpl,
        targetCpl: row.target_cpl_vnd,
        leads: row.leads_crm,
        roas,
        decreasePct,
        increasePct,
        cplOverRatio: cplOver,
        cplUnderRatio: cplUnder,
      });
      if (!rec) continue;
      recommendations.push({
        client_id: row.client_id,
        client_code: row.client_code,
        client_name: row.client_name,
        external_campaign_id: row.external_campaign_id || null,
        external_campaign_name: row.external_campaign_name,
        recommendation_type: rec.recommendation_type,
        current_daily_spend_vnd: Math.round(avgDaily * 100) / 100,
        suggested_daily_budget_vnd: rec.suggested_daily_budget_vnd,
        change_pct: rec.change_pct,
        rationale: rec.rationale,
        write_request: {
          change_type: 'daily_budget' as const,
          external_campaign_id: row.external_campaign_id,
          daily_budget_vnd: rec.suggested_daily_budget_vnd,
        },
      });
    }

    return {
      ok: true,
      read_only: true,
      date_from: dateFrom,
      date_to: dateTo,
      recommendations,
      count: recommendations.length,
      attribution,
    };
  }
}
