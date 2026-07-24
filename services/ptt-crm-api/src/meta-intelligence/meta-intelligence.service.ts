import { BadRequestException, Injectable, ServiceUnavailableException } from '@nestjs/common';
import { buildMetaAttributionMeta } from '../meta-attribution.util';
import { computeRoas, toNumber } from '../performance/performance.util';
import { MetaIntelligenceRepository } from './meta-intelligence.repository';
import {
  MetaAnomaliesListResponse,
  MetaAnomalyRow,
  MetaBudgetRecommendationsResponse,
  MetaDailyInsightRow,
  MetaDailyInsightsResponse,
  MetaInsightsBreakdownResponse,
  MetaInsightsBreakdownRow,
  MetaForecastMetric,
  MetaForecastResponse,
  MetaIntelligenceSnapshotResponse,
  MetaPixelMutationResponse,
  MetaPixelRow,
  MetaPixelsListResponse,
  MetaRoasResponse,
} from './meta-intelligence.types';
import {
  buildForecastProjection,
  computeSpikePct,
  detectCampaignAnomalies,
  detectCampaignStatAnomalies,
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

  isBreakdownEnabled(): boolean {
    return ['1', 'true', 'yes', 'on'].includes(
      (process.env.PTT_META_INSIGHTS_BREAKDOWN ?? '0').trim().toLowerCase(),
    );
  }

  isAnomalyStatEnabled(): boolean {
    return ['1', 'true', 'yes', 'on'].includes(
      (process.env.PTT_META_ANOMALY_STAT_ENABLED ?? '0').trim().toLowerCase(),
    );
  }

  isForecastEnabled(): boolean {
    return ['1', 'true', 'yes', 'on'].includes(
      (process.env.PTT_META_FORECAST_ENABLED ?? '0').trim().toLowerCase(),
    );
  }

  isPixelsEnabled(): boolean {
    return ['1', 'true', 'yes', 'on'].includes(
      (process.env.PTT_META_PIXELS_ENABLED ?? '0').trim().toLowerCase(),
    );
  }

  isSnapshotEnabled(): boolean {
    return ['1', 'true', 'yes', 'on'].includes(
      (process.env.PTT_META_INTEL_SNAPSHOT_ENABLED ?? '0').trim().toLowerCase(),
    );
  }

  insightsLevelEnabled(): string {
    const raw = (process.env.PTT_META_INSIGHTS_LEVEL ?? 'campaign').trim().toLowerCase();
    return ['campaign', 'adset', 'ad'].includes(raw) ? raw : 'campaign';
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
    mode?: string;
  }): Promise<MetaAnomaliesListResponse> {
    if ((query.mode ?? '').trim().toLowerCase() === 'stat') {
      return this.listStatAnomalies(query);
    }
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

  async listStatAnomalies(query: {
    client_id?: string;
    limit?: string;
    days?: string;
  }): Promise<MetaAnomaliesListResponse> {
    await this.ensurePerformanceReady();
    const windowDays = envInt('PTT_META_ANOMALY_STAT_WINDOW_DAYS', 14);
    const { start, end } = this.repo.resolveWindow(query, windowDays);
    const { dateFrom, dateTo } = this.repo.formatWindow(start, end);
    const clientId = query.client_id?.trim() || undefined;
    const attribution = await this.buildAttribution({ clientId, dateFrom, dateTo });

    if (!this.isAnomalyStatEnabled()) {
      return {
        ok: true,
        disabled: true,
        mode: 'stat',
        anomalies: [],
        count: 0,
        attribution,
      };
    }

    const limit = query.limit ? Number(query.limit) : 100;
    const stored = await this.repo.listStoredStatAnomalies({
      clientId,
      limit: Number.isFinite(limit) ? limit : 100,
    });
    if (stored.length) {
      const anomalies: MetaAnomalyRow[] = stored.map((row) => ({
        id: String(row.id),
        client_id: String(row.client_id),
        client_code: row.client_code != null ? String(row.client_code) : null,
        client_name: row.client_name != null ? String(row.client_name) : null,
        external_campaign_id: row.external_campaign_id ? String(row.external_campaign_id) : null,
        alert_type: String(row.alert_type),
        severity: String(row.severity),
        metric_value: row.metric_value != null ? Number(row.metric_value) : null,
        threshold_value: row.threshold_value != null ? Number(row.threshold_value) : null,
        spike_pct: null,
        z_score: null,
        message: String(row.message ?? ''),
        performance_date: row.performance_date ? String(row.performance_date).slice(0, 10) : null,
        created_at: new Date(String(row.created_at)).toISOString(),
      }));
      return { ok: true, mode: 'stat', anomalies, count: anomalies.length, attribution };
    }

    const zThreshold = envFloat('PTT_META_ANOMALY_ZSCORE_THRESHOLD', 2);
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
      const detected = detectCampaignStatAnomalies({
        spendToday: latest.spend,
        leadsToday: latest.leads_crm,
        spendHistory,
        cplHistory,
        zscoreThreshold: zThreshold,
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
          spike_pct: null,
          z_score: item.z_score,
          message: item.message,
          performance_date: latest.performance_date,
          created_at: new Date().toISOString(),
        });
      }
    }

    anomalies.sort((a, b) => (b.performance_date ?? '').localeCompare(a.performance_date ?? ''));
    const capped = anomalies.slice(0, Number.isFinite(limit) ? limit : 100);
    return { ok: true, mode: 'stat', anomalies: capped, count: capped.length, attribution };
  }

  async getForecast(query: {
    client_id?: string;
    metric?: string;
    days?: string;
  }): Promise<MetaForecastResponse> {
    await this.ensurePerformanceReady();
    const metricRaw = (query.metric ?? 'cpl').trim().toLowerCase();
    const metric: MetaForecastMetric = metricRaw === 'spend' ? 'spend' : 'cpl';
    const historyDays = envInt('PTT_META_FORECAST_HISTORY_DAYS', 14);
    const { start, end } = this.repo.resolveWindow(query, historyDays);
    const { dateFrom, dateTo } = this.repo.formatWindow(start, end);
    const clientId = query.client_id?.trim() || undefined;
    const attribution = await this.buildAttribution({ clientId, dateFrom, dateTo });

    if (!this.isForecastEnabled()) {
      return {
        ok: true,
        disabled: true,
        metric,
        date_from: dateFrom,
        date_to: dateTo,
        slope: 0,
        intercept: 0,
        historical: [],
        projection: [],
        attribution,
      };
    }

    const historical = await this.repo.listDailyMetricSeries({
      clientId,
      dateFrom,
      dateTo,
      metric,
    });
    const projectionDays = envInt('PTT_META_FORECAST_PROJECTION_DAYS', 7);
    const forecast = buildForecastProjection({ historical, projectionDays });

    return {
      ok: true,
      metric,
      date_from: dateFrom,
      date_to: dateTo,
      slope: forecast.slope,
      intercept: forecast.intercept,
      historical: forecast.historical,
      projection: forecast.projection,
      attribution,
    };
  }

  private mapPixelRow(row: Record<string, unknown>, clientId?: string | null): MetaPixelRow {
    return {
      id: String(row.id),
      client_channel_account_id: String(row.client_channel_account_id),
      client_id: clientId ?? (row.client_id != null ? String(row.client_id) : null),
      pixel_id: String(row.pixel_id),
      label: String(row.label ?? ''),
      is_primary: Boolean(row.is_primary),
      capi_enabled: Boolean(row.capi_enabled),
      created_at: new Date(String(row.created_at)).toISOString(),
    };
  }

  async listPixels(query: {
    client_id?: string;
    client_channel_account_id?: string;
  }): Promise<MetaPixelsListResponse> {
    if (!this.isPixelsEnabled()) {
      return { ok: true, disabled: true, pixels: [], count: 0 };
    }
    if (!(await this.repo.pgMetaPixelsReady())) {
      return {
        ok: true,
        disabled: true,
        reason: 'meta_pixels_not_ready',
        hint: './scripts/apply_pg_ddl_v7_meta_advanced.sh',
        pixels: [],
        count: 0,
      };
    }

    const rows = await this.repo.listMetaPixels({
      clientId: query.client_id?.trim() || undefined,
      channelAccountId: query.client_channel_account_id?.trim() || undefined,
    });
    const pixels = rows.map((row) =>
      this.mapPixelRow(row as Record<string, unknown>, String(row.client_id ?? '')),
    );
    return { ok: true, pixels, count: pixels.length };
  }

  async createPixel(body: Record<string, unknown>): Promise<MetaPixelMutationResponse> {
    if (!this.isPixelsEnabled()) {
      return { ok: true, disabled: true };
    }
    if (!(await this.repo.pgMetaPixelsReady())) {
      return { ok: false, error: 'meta_pixels_not_ready' };
    }

    const accountId = String(body.client_channel_account_id ?? '').trim();
    const pixelId = String(body.pixel_id ?? '').trim();
    if (!accountId || !pixelId) {
      throw new BadRequestException({ ok: false, error: 'client_channel_account_id_and_pixel_id_required' });
    }

    const row = await this.repo.insertMetaPixel({
      clientChannelAccountId: accountId,
      pixelId,
      label: String(body.label ?? '').trim(),
      isPrimary: Boolean(body.is_primary),
      capiEnabled: body.capi_enabled == null ? true : Boolean(body.capi_enabled),
    });
    return { ok: true, pixel: this.mapPixelRow(row as Record<string, unknown>) };
  }

  async patchPixel(pixelRowId: string, body: Record<string, unknown>): Promise<MetaPixelMutationResponse> {
    if (!this.isPixelsEnabled()) {
      return { ok: true, disabled: true };
    }
    if (!(await this.repo.pgMetaPixelsReady())) {
      return { ok: false, error: 'meta_pixels_not_ready' };
    }

    const row = await this.repo.patchMetaPixel(pixelRowId, {
      label: body.label != null ? String(body.label).trim() : undefined,
      isPrimary: body.is_primary != null ? Boolean(body.is_primary) : undefined,
      capiEnabled: body.capi_enabled != null ? Boolean(body.capi_enabled) : undefined,
    });
    if (!row) {
      throw new BadRequestException({ ok: false, error: 'not_found' });
    }
    return { ok: true, pixel: this.mapPixelRow(row as Record<string, unknown>) };
  }

  async createSnapshot(body: Record<string, unknown>): Promise<MetaIntelligenceSnapshotResponse> {
    if (!this.isSnapshotEnabled()) {
      return { ok: true, disabled: true, skipped: true, reason: 'PTT_META_INTEL_SNAPSHOT_ENABLED=0' };
    }
    if (!(await this.repo.pgMetaIntelligenceSnapshotsReady())) {
      return {
        ok: false,
        reason: 'meta_intelligence_snapshots_not_ready',
        hint: './scripts/apply_pg_ddl_v7_meta_advanced.sh',
      };
    }

    const clientId = body.client_id ? String(body.client_id).trim() : undefined;
    const periodDays = body.days ? Number(body.days) : 7;
    const end = new Date();
    end.setUTCDate(end.getUTCDate() - 1);
    const start = new Date(end);
    start.setUTCDate(start.getUTCDate() - Math.max(1, periodDays) - 1);
    const dateFrom = this.repo.formatWindow(start, end).dateFrom;
    const dateTo = this.repo.formatWindow(start, end).dateTo;

    const historical = await this.repo.listDailyMetricSeries({
      clientId,
      dateFrom,
      dateTo,
      metric: 'spend',
    });
    const payload = {
      generated_at: new Date().toISOString(),
      period_start: dateFrom,
      period_end: dateTo,
      client_id: clientId ?? null,
      performance: historical,
    };
    const raw = Buffer.from(JSON.stringify(payload), 'utf8');
    const { gzipSync } = await import('zlib');
    const compressed = gzipSync(raw);
    const artifactsDir = process.env.PTT_ARTIFACTS_DIR?.trim() || '.local-dev';
    const { mkdirSync, writeFileSync } = await import('fs');
    const { join } = await import('path');
    const dir = join(process.cwd(), artifactsDir, 'meta-intel-snapshots');
    mkdirSync(dir, { recursive: true });
    const stamp = new Date().toISOString().replace(/[-:]/g, '').replace(/\..+/, 'Z');
    const filename = `meta-intel-${clientId ?? 'all'}-${stamp}.json.gz`;
    const artifactPath = join(dir, filename);
    writeFileSync(artifactPath, compressed);

    const row = await this.repo.insertIntelligenceSnapshot({
      clientId,
      periodStart: dateFrom,
      periodEnd: dateTo,
      artifactPath,
      byteSize: raw.length,
    });

    return {
      ok: true,
      snapshot: {
        id: String(row.id),
        client_id: row.client_id != null ? String(row.client_id) : null,
        period_start: String(row.period_start).slice(0, 10),
        period_end: String(row.period_end).slice(0, 10),
        artifact_path: String(row.artifact_path),
        byte_size: Number(row.byte_size ?? 0),
        gzip: Boolean(row.gzip),
        created_at: new Date(String(row.created_at)).toISOString(),
      },
    };
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

  async getDailyInsights(query: {
    client_id?: string;
    level?: string;
    from?: string;
    to?: string;
    days?: string;
    limit?: string;
  }): Promise<MetaDailyInsightsResponse> {
    await this.ensurePerformanceReady();
    const level = (query.level ?? 'campaign').trim().toLowerCase();
    if (!['campaign', 'adset', 'ad'].includes(level)) {
      throw new BadRequestException({ ok: false, error: 'invalid_insight_level', level });
    }

    const enabledLevel = this.insightsLevelEnabled();
    const { start, end } = this.repo.resolveWindow(query, 7);
    const { dateFrom, dateTo } = this.repo.formatWindow(start, end);
    const clientId = query.client_id?.trim() || undefined;
    const attribution = await this.buildAttribution({ clientId, dateFrom, dateTo });
    const limit = query.limit ? Number(query.limit) : 500;

    if (level !== 'campaign' && enabledLevel !== level) {
      return {
        ok: true,
        disabled: true,
        level,
        enabled_level: enabledLevel,
        date_from: dateFrom,
        date_to: dateTo,
        rows: [],
        count: 0,
        attribution,
      };
    }

    const { rows, hasLevelCol } = await this.repo.listDailyInsights({
      clientId,
      level,
      dateFrom,
      dateTo,
      limit: Number.isFinite(limit) ? limit : 500,
    });

    if (!hasLevelCol && level !== 'campaign') {
      return {
        ok: true,
        disabled: true,
        level,
        enabled_level: enabledLevel,
        reason: 'insight_level_column_not_ready',
        hint: './scripts/apply_pg_ddl_v6_meta_insights_level.sh',
        date_from: dateFrom,
        date_to: dateTo,
        rows: [],
        count: 0,
        attribution,
      };
    }

    const mapped: MetaDailyInsightRow[] = rows.map((row) => ({
      client_id: String(row.client_id),
      client_code: row.client_code != null ? String(row.client_code) : null,
      client_name: row.client_name != null ? String(row.client_name) : null,
      external_campaign_id: row.external_campaign_id ? String(row.external_campaign_id) : null,
      external_campaign_name: row.external_campaign_name != null ? String(row.external_campaign_name) : null,
      external_adset_id:
        row.external_adset_id && String(row.external_adset_id) !== ''
          ? String(row.external_adset_id)
          : null,
      external_adset_name: row.external_adset_name != null ? String(row.external_adset_name) : null,
      insight_level: String(row.insight_level ?? level),
      performance_date: String(row.performance_date).slice(0, 10),
      spend: Math.round(toNumber(row.spend) * 100) / 100,
      impressions: Math.round(toNumber(row.impressions)),
      clicks: Math.round(toNumber(row.clicks)),
      leads_crm: Math.round(toNumber(row.leads_crm)),
      conversion_value: Math.round(toNumber(row.conversion_value) * 100) / 100,
    }));

    return {
      ok: true,
      level,
      enabled_level: enabledLevel,
      date_from: dateFrom,
      date_to: dateTo,
      rows: mapped,
      count: mapped.length,
      attribution,
    };
  }

  async getInsightsBreakdown(query: {
    client_id?: string;
    campaign_id?: string;
    date?: string;
    type?: string;
    from?: string;
    to?: string;
    days?: string;
  }): Promise<MetaInsightsBreakdownResponse> {
    await this.ensurePerformanceReady();
    const breakdownType = (query.type ?? 'publisher_platform').trim().toLowerCase();
    const allowed = ['publisher_platform', 'platform_position', 'age', 'gender', 'device_platform', 'country'];
    if (!allowed.includes(breakdownType)) {
      throw new BadRequestException({ ok: false, error: 'invalid_breakdown_type', type: breakdownType });
    }

    let start: Date;
    let end: Date;
    if (query.date?.trim()) {
      const day = this.repo.parseOptionalDate(query.date.trim(), new Date());
      start = day;
      end = day;
    } else {
      const window = this.repo.resolveWindow(query, 7);
      start = window.start;
      end = window.end;
    }
    const { dateFrom, dateTo } = this.repo.formatWindow(start, end);
    const clientId = query.client_id?.trim() || undefined;
    const campaignId = query.campaign_id?.trim() || undefined;
    const attribution = await this.buildAttribution({ clientId, dateFrom, dateTo });

    if (!this.isBreakdownEnabled()) {
      return {
        ok: true,
        disabled: true,
        breakdown_type: breakdownType,
        date_from: dateFrom,
        date_to: dateTo,
        rows: [],
        count: 0,
        total_spend: 0,
        breakdown_spend: 0,
        spend_delta_pct: null,
        attribution,
      };
    }

    if (!(await this.repo.pgDailyPerformanceBreakdownReady())) {
      return {
        ok: true,
        disabled: true,
        reason: 'daily_performance_breakdown_not_ready',
        hint: './scripts/apply_pg_ddl_v8_meta_insights_breakdown.sh',
        breakdown_type: breakdownType,
        date_from: dateFrom,
        date_to: dateTo,
        rows: [],
        count: 0,
        total_spend: 0,
        breakdown_spend: 0,
        spend_delta_pct: null,
        attribution,
      };
    }

    const rawRows = await this.repo.listInsightsBreakdown({
      clientId,
      externalCampaignId: campaignId,
      breakdownType,
      dateFrom,
      dateTo,
    });
    const rows: MetaInsightsBreakdownRow[] = rawRows.map((row) => ({
      client_id: String(row.client_id),
      external_campaign_id: String(row.external_campaign_id),
      performance_date: String(row.performance_date).slice(0, 10),
      breakdown_type: String(row.breakdown_type),
      breakdown_value: String(row.breakdown_value),
      spend: Math.round(toNumber(row.spend) * 100) / 100,
      impressions: Math.round(toNumber(row.impressions)),
      clicks: Math.round(toNumber(row.clicks)),
      leads_platform: Math.round(toNumber(row.leads_platform)),
    }));

    const breakdownSpend = rows.reduce((acc, row) => acc + row.spend, 0);
    let totalSpend = 0;
    if (campaignId) {
      totalSpend = await this.repo.sumCampaignSpend({
        clientId,
        externalCampaignId: campaignId,
        dateFrom,
        dateTo,
      });
    }
    const spendDeltaPct =
      totalSpend > 0 ? Math.round(((breakdownSpend - totalSpend) / totalSpend) * 1000) / 10 : null;

    return {
      ok: true,
      breakdown_type: breakdownType,
      date_from: dateFrom,
      date_to: dateTo,
      rows,
      count: rows.length,
      total_spend: Math.round(totalSpend * 100) / 100,
      breakdown_spend: Math.round(breakdownSpend * 100) / 100,
      spend_delta_pct: spendDeltaPct,
      attribution,
    };
  }
}
