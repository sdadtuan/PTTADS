import { Injectable, OnModuleDestroy } from '@nestjs/common';
import { Pool } from 'pg';
import { AppConfigService } from '../config/app-config.service';
import { CrossChannelChannelSummary } from './metrics.types';

@Injectable()
export class MetricsRepository implements OnModuleDestroy {
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

  async pgPerformanceReady(): Promise<boolean> {
    const result = await this.db.query(
      `SELECT 1 FROM information_schema.tables
       WHERE table_schema = 'public' AND table_name = 'daily_performance'
       LIMIT 1`,
    );
    return (result.rowCount ?? 0) > 0;
  }

  async fetchCrossChannelSummary(params: {
    dateFrom: string;
    dateTo: string;
    clientId?: string;
  }): Promise<CrossChannelChannelSummary[]> {
    const clauses = [`dp.performance_date BETWEEN $1::date AND $2::date`, `dp.channel IN ('meta', 'google')`];
    const values: unknown[] = [params.dateFrom, params.dateTo];
    if (params.clientId) {
      clauses.push(`dp.client_id = $3::uuid`);
      values.push(params.clientId);
    }
    const result = await this.db.query(
      `SELECT dp.channel,
              COALESCE(SUM(dp.spend), 0) AS spend,
              COALESCE(SUM(dp.leads_crm), 0) AS leads_crm,
              COALESCE(SUM(dp.leads_platform), 0) AS leads_platform,
              COUNT(DISTINCT dp.external_campaign_id)::int AS campaigns,
              COUNT(*) FILTER (WHERE dp.hub_campaign_map_id IS NULL)::int AS unmapped_rows
       FROM daily_performance dp
       WHERE ${clauses.join(' AND ')}
       GROUP BY dp.channel
       ORDER BY dp.channel`,
      values,
    );
    return result.rows.map((row) => {
      const spend = Number(row.spend ?? 0);
      const leads = Number(row.leads_crm ?? 0);
      return {
        channel: String(row.channel),
        spend,
        leads_crm: leads,
        leads_platform: Number(row.leads_platform ?? 0),
        cpl: leads > 0 ? Math.round(spend / leads) : null,
        campaigns: Number(row.campaigns ?? 0),
        unmapped_rows: Number(row.unmapped_rows ?? 0),
      };
    });
  }
}
