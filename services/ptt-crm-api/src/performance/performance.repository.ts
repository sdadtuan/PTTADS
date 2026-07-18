import { Injectable, OnModuleDestroy } from '@nestjs/common';
import { Pool } from 'pg';
import { AppConfigService } from '../config/app-config.service';
import { PerformanceGroupBy, PerformanceChannel } from './performance.types';

export interface PerformanceDbRow {
  performance_date?: Date | string | null;
  channel?: string | null;
  external_campaign_id: string | null;
  external_campaign_name: string | null;
  spend: string | number | null;
  currency: string | null;
  impressions: string | number | null;
  clicks: string | number | null;
  leads_crm: string | number | null;
  leads_platform: string | number | null;
  conversion_value?: string | number | null;
  hub_campaign_map_id: string | null;
  hub_campaign_id: string | number | null;
  target_cpl_vnd: string | number | null;
  synced_at: Date | string | null;
  cpl_snapshot?: string | number | null;
  roas_snapshot?: string | number | null;
}

@Injectable()
export class PerformanceRepository implements OnModuleDestroy {
  private pool: Pool | null = null;

  constructor(private readonly config: AppConfigService) {}

  private get db(): Pool {
    if (!this.pool) {
      this.pool = new Pool({ connectionString: this.config.databaseUrl });
    }
    return this.pool;
  }

  onModuleDestroy(): void {
    void this.pool?.end();
    this.pool = null;
  }

  async clientExists(clientId: string): Promise<boolean> {
    const result = await this.db.query(`SELECT 1 FROM clients WHERE id = $1::uuid LIMIT 1`, [clientId]);
    return (result.rowCount ?? 0) > 0;
  }

  async pgPerformanceReady(): Promise<boolean> {
    const result = await this.db.query(
      `SELECT COUNT(*)::int AS c FROM information_schema.tables
       WHERE table_schema = 'public' AND table_name = 'daily_performance'`,
    );
    return Number(result.rows[0]?.c ?? 0) > 0;
  }

  async fetchRows(
    clientId: string,
    start: string,
    end: string,
    groupBy: PerformanceGroupBy,
    channels: PerformanceChannel[] = ['meta', 'google'],
  ): Promise<PerformanceDbRow[]> {
    if (groupBy === 'campaign') {
      const result = await this.db.query(
        `SELECT
            dp.external_campaign_id,
            MAX(dp.channel) AS channel,
            MAX(dp.external_campaign_name) AS external_campaign_name,
            SUM(dp.spend) AS spend,
            MAX(dp.currency) AS currency,
            SUM(dp.impressions) AS impressions,
            SUM(dp.clicks) AS clicks,
            SUM(dp.leads_crm) AS leads_crm,
            SUM(dp.leads_platform) AS leads_platform,
            SUM(dp.conversion_value) AS conversion_value,
            MAX(dp.hub_campaign_map_id::text) AS hub_campaign_map_id,
            MAX(hcm.hub_campaign_id) AS hub_campaign_id,
            MAX(hcm.target_cpl_vnd) AS target_cpl_vnd,
            MAX(dp.synced_at) AS synced_at,
            CASE
              WHEN SUM(dp.leads_crm) > 0 THEN SUM(dp.spend) / SUM(dp.leads_crm)
              ELSE NULL
            END AS cpl_snapshot,
            CASE
              WHEN SUM(dp.spend) > 0 AND SUM(dp.conversion_value) > 0
              THEN SUM(dp.conversion_value) / SUM(dp.spend)
              ELSE NULL
            END AS roas_snapshot
          FROM daily_performance dp
          LEFT JOIN hub_campaign_map hcm ON hcm.id = dp.hub_campaign_map_id
          WHERE dp.client_id = $1::uuid
            AND dp.channel = ANY($4::text[])
            AND dp.performance_date BETWEEN $2::date AND $3::date
          GROUP BY dp.external_campaign_id
          ORDER BY SUM(dp.spend) DESC, dp.external_campaign_id`,
        [clientId, start, end, channels],
      );
      return result.rows as PerformanceDbRow[];
    }

    const result = await this.db.query(
      `SELECT
          dp.performance_date,
          dp.channel,
          dp.external_campaign_id,
          dp.external_campaign_name,
          dp.spend,
          dp.currency,
          dp.impressions,
          dp.clicks,
          dp.leads_crm,
          dp.leads_platform,
          dp.conversion_value,
          dp.hub_campaign_map_id::text AS hub_campaign_map_id,
          hcm.hub_campaign_id,
          hcm.target_cpl_vnd,
          dp.synced_at,
          ms.value_numeric AS cpl_snapshot,
          ms_roas.value_numeric AS roas_snapshot
        FROM daily_performance dp
        LEFT JOIN hub_campaign_map hcm ON hcm.id = dp.hub_campaign_map_id
        LEFT JOIN metrics_snapshots ms
          ON ms.client_id = dp.client_id
         AND ms.kpi_code = 'CPL'
         AND ms.channel = dp.channel
         AND COALESCE(ms.external_campaign_id, '') = dp.external_campaign_id
         AND ms.period_start = dp.performance_date
         AND ms.period_end = dp.performance_date
         AND ms.granularity = 'day'
        LEFT JOIN metrics_snapshots ms_roas
          ON ms_roas.client_id = dp.client_id
         AND ms_roas.kpi_code = 'ROAS'
         AND ms_roas.channel = dp.channel
         AND COALESCE(ms_roas.external_campaign_id, '') = dp.external_campaign_id
         AND ms_roas.period_start = dp.performance_date
         AND ms_roas.period_end = dp.performance_date
         AND ms_roas.granularity = 'day'
        WHERE dp.client_id = $1::uuid
          AND dp.channel = ANY($4::text[])
          AND dp.performance_date BETWEEN $2::date AND $3::date
        ORDER BY dp.performance_date DESC, dp.external_campaign_name NULLS LAST`,
      [clientId, start, end, channels],
    );
    return result.rows as PerformanceDbRow[];
  }

  async fetchMeta(
    clientId: string,
    channels: PerformanceChannel[] = ['meta', 'google'],
  ): Promise<{ latestDate: string | null; latestSync: string | null; campaignCount: number }> {
    const result = await this.db.query(
      `SELECT
          MAX(performance_date)::text AS latest_date,
          MAX(synced_at) AS latest_synced_at,
          COUNT(DISTINCT external_campaign_id)::int AS campaigns_tracked
       FROM daily_performance
       WHERE client_id = $1::uuid AND channel = ANY($2::text[])`,
      [clientId, channels],
    );
    const row = result.rows[0];
    return {
      latestDate: row?.latest_date ?? null,
      latestSync: row?.latest_synced_at ? String(row.latest_synced_at) : null,
      campaignCount: Number(row?.campaigns_tracked ?? 0),
    };
  }
}
