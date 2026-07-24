import { Injectable, NotFoundException, ServiceUnavailableException } from '@nestjs/common';
import { PerformanceRepository, PerformanceDbRow } from './performance.repository';
import {
  PerformanceGroupBy,
  PerformanceListResponse,
  PerformanceQuery,
  PerformanceRow,
  PerformanceSummary,
} from './performance.types';
import {
  computeCpl,
  computeRoas,
  formatDateOnly,
  normalizePerformanceChannel,
  performanceChannelSql,
  resolveDateWindow,
  toIso,
  toNumber,
} from './performance.util';
import {
  buildMetaAttributionMeta,
  computeUnmappedSpendPct,
} from '../meta-attribution.util';

@Injectable()
export class PerformanceService {
  constructor(private readonly repo: PerformanceRepository) {}

  async listForClient(clientId: string, query: PerformanceQuery): Promise<PerformanceListResponse> {
    if (!(await this.repo.pgPerformanceReady())) {
      throw new ServiceUnavailableException({ ok: false, error: 'performance_tables_not_ready' });
    }

    if (!(await this.repo.clientExists(clientId))) {
      throw new NotFoundException({ error: 'Not found' });
    }

    const { start, end } = resolveDateWindow(query);
    const groupBy = this.normalizeGroupBy(query.group_by);
    const channel = normalizePerformanceChannel(query.channel);
    const channels = performanceChannelSql(channel) as Array<'meta' | 'google'>;
    const dateFrom = formatDateOnly(start);
    const dateTo = formatDateOnly(end);

    const dbRows = await this.repo.fetchRows(clientId, dateFrom, dateTo, groupBy, channels);
    const rows = dbRows.map((row) => this.mapRow(row));
    const meta = await this.repo.fetchMeta(clientId, channels);
    const summary = this.buildSummary(rows, meta);

    const totalSpend = summary.total_spend;
    const unmappedSpend = rows.filter((r) => !r.hub_mapped).reduce((sum, r) => sum + r.spend, 0);
    const unmappedSpendPct = computeUnmappedSpendPct(unmappedSpend, totalSpend);
    const attribution = buildMetaAttributionMeta({
      dateTo,
      syncedAt: summary.latest_synced_at,
      unmappedSpendPct,
    });

    return {
      ok: true,
      client_id: clientId,
      date_from: dateFrom,
      date_to: dateTo,
      group_by: groupBy,
      channel,
      rows,
      summary,
      attribution_model: attribution.attribution_model,
      unmapped_spend_pct: attribution.unmapped_spend_pct,
      spend_source: attribution.spend_source,
      data_freshness: attribution.data_freshness,
    };
  }

  private normalizeGroupBy(value: string | undefined): PerformanceGroupBy {
    const group = (value ?? 'day').trim().toLowerCase();
    return group === 'campaign' ? 'campaign' : 'day';
  }

  private mapRow(rec: PerformanceDbRow): PerformanceRow {
    const spend = toNumber(rec.spend);
    const leadsCrm = Math.trunc(toNumber(rec.leads_crm));
    const leadsPlatform = Math.trunc(toNumber(rec.leads_platform));
    const convValue = toNumber(rec.conversion_value);

    let cplVal: number | null = null;
    if (rec.cpl_snapshot != null && rec.cpl_snapshot !== '') {
      cplVal = Math.round(toNumber(rec.cpl_snapshot) * 100) / 100;
    } else {
      cplVal = computeCpl(spend, leadsCrm);
    }

    const targetRaw = rec.target_cpl_vnd;
    const targetVal =
      targetRaw != null && targetRaw !== '' ? Math.round(toNumber(targetRaw) * 100) / 100 : null;

    let deltaVnd: number | null = null;
    let deltaPct: number | null = null;
    if (cplVal != null && targetVal != null && targetVal > 0) {
      deltaVnd = Math.round((cplVal - targetVal) * 100) / 100;
      deltaPct = Math.round(((cplVal - targetVal) / targetVal) * 1000) / 10;
    }

    let roasVal: number | null = null;
    let roasStub = false;
    if (rec.roas_snapshot != null && rec.roas_snapshot !== '') {
      roasVal = Math.round(toNumber(rec.roas_snapshot) * 10000) / 10000;
    } else {
      roasVal = computeRoas(convValue, spend);
      roasStub = roasVal == null && spend > 0;
    }

    const hubIdRaw = rec.hub_campaign_id;
    const hubId =
      hubIdRaw != null && hubIdRaw !== '' ? Math.trunc(toNumber(hubIdRaw)) : null;

    const perfDate =
      rec.performance_date != null
        ? formatDateOnly(new Date(rec.performance_date))
        : null;

    return {
      performance_date: perfDate,
      channel: rec.channel?.trim() || 'meta',
      external_campaign_id: rec.external_campaign_id,
      external_campaign_name: rec.external_campaign_name,
      spend,
      currency: rec.currency?.trim() || 'VND',
      impressions: Math.trunc(toNumber(rec.impressions)),
      clicks: Math.trunc(toNumber(rec.clicks)),
      leads_crm: leadsCrm,
      leads_platform: leadsPlatform,
      cpl: cplVal,
      target_cpl_vnd: targetVal,
      cpl_delta_vnd: deltaVnd,
      cpl_delta_pct: deltaPct,
      conversion_value: convValue,
      roas: roasVal,
      roas_stub: roasStub,
      hub_campaign_map_id: rec.hub_campaign_map_id,
      hub_campaign_id: hubId,
      hub_mapped: Boolean(rec.hub_campaign_map_id),
      synced_at: toIso(rec.synced_at),
    };
  }

  private buildSummary(
    rows: PerformanceRow[],
    meta: { latestDate: string | null; latestSync: string | null; campaignCount: number },
  ): PerformanceSummary {
    const totalSpend = rows.reduce((sum, r) => sum + r.spend, 0);
    const totalLeads = rows.reduce((sum, r) => sum + r.leads_crm, 0);
    const totalConv = rows.reduce((sum, r) => sum + r.conversion_value, 0);
    const mappedRows = rows.filter((r) => r.hub_mapped);
    const overTarget = mappedRows.filter(
      (r) =>
        r.cpl != null &&
        r.target_cpl_vnd != null &&
        r.cpl > r.target_cpl_vnd,
    );
    const avgRoas = computeRoas(totalConv, totalSpend);

    return {
      row_count: rows.length,
      total_spend: Math.round(totalSpend * 100) / 100,
      total_leads_crm: totalLeads,
      avg_cpl: computeCpl(totalSpend, totalLeads),
      total_conversion_value: Math.round(totalConv * 100) / 100,
      avg_roas: avgRoas,
      roas_stub: avgRoas == null && totalSpend > 0,
      latest_performance_date: meta.latestDate,
      latest_synced_at: meta.latestSync,
      campaigns_tracked: meta.campaignCount,
      mapped_rows: mappedRows.length,
      over_target_rows: overTarget.length,
    };
  }
}
