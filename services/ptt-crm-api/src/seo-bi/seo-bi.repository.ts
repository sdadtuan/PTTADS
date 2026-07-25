import { Injectable, OnModuleDestroy } from '@nestjs/common';
import { Pool } from 'pg';
import { AppConfigService } from '../config/app-config.service';
import { clickhouseConfigured, SEO_BI_SCHEMA } from './seo-bi.constants';
import {
  SeoAttributionLandingPage,
  SeoAttributionSummary,
  SeoBiDashboardResponse,
  SeoBiFactRow,
  SeoBiParityResponse,
} from './seo-bi.types';

const SCHEMA = SEO_BI_SCHEMA;

const BI_METRICS = [
  'content_published',
  'gsc_clicks',
  'gsc_impressions',
  'critical_issues_open',
  'aeo_coverage_pct',
  'organic_revenue',
] as const;

@Injectable()
export class SeoBiRepository implements OnModuleDestroy {
  private pool: Pool | null = null;

  constructor(private readonly config: AppConfigService) {}

  private get db(): Pool {
    if (!this.pool) this.pool = new Pool({ connectionString: this.config.databaseUrl });
    return this.pool;
  }

  onModuleDestroy(): void {
    void this.pool?.end();
    this.pool = null;
  }

  async biDashboard(customerId: number | null, days = 28): Promise<SeoBiDashboardResponse> {
    const safeDays = Math.max(1, Math.min(days, 365));
    const values: unknown[] = [safeDays];
    let sql = `SELECT stat_date::text, COALESCE(SUM(clicks),0)::int AS clicks,
                      COALESCE(SUM(impressions),0)::int AS impressions
               FROM ${SCHEMA}.seo_gsc_daily_stats
               WHERE stat_date >= CURRENT_DATE - ($1::int || ' days')::interval`;
    if (customerId != null) {
      values.push(customerId);
      sql += ` AND customer_id = $${values.length}`;
    }
    sql += ' GROUP BY stat_date ORDER BY stat_date ASC';
    const result = await this.db.query(sql, values);
    const gscSeries = result.rows.map((r) => ({
      stat_date: String(r.stat_date),
      clicks: Number(r.clicks),
      impressions: Number(r.impressions),
    }));
    const totals = {
      clicks: gscSeries.reduce((sum, r) => sum + r.clicks, 0),
      impressions: gscSeries.reduce((sum, r) => sum + r.impressions, 0),
    };
    return {
      type: 'bi',
      customer_id: customerId,
      days: safeDays,
      gsc_series: gscSeries,
      totals,
      clickhouse_configured: clickhouseConfigured(),
    };
  }

  private async listActiveCustomerIds(limit?: number): Promise<number[]> {
    const lim = limit != null ? Math.max(1, limit) : null;
    const sql = `
      SELECT DISTINCT customer_id FROM (
        SELECT customer_id FROM ${SCHEMA}.seo_content WHERE workflow_status != 'archived'
        UNION SELECT customer_id FROM ${SCHEMA}.seo_keywords WHERE status = 'active'
        UNION SELECT customer_id FROM ${SCHEMA}.seo_questions WHERE status = 'active'
        UNION SELECT customer_id FROM ${SCHEMA}.seo_client_settings
      ) t
      ORDER BY customer_id ASC
      ${lim != null ? `LIMIT ${lim}` : ''}`;
    const result = await this.db.query<{ customer_id: string }>(sql);
    return result.rows.map((r) => Number(r.customer_id));
  }

  async collectDailyFacts(factDate?: string): Promise<SeoBiFactRow[]> {
    const d = factDate ?? new Date().toISOString().slice(0, 10);
    const facts: SeoBiFactRow[] = [];
    const customerIds = await this.listActiveCustomerIds();
    for (const cid of customerIds) {
      const published = await this.db.query<{ c: string }>(
        `SELECT COUNT(*) AS c FROM ${SCHEMA}.seo_content
         WHERE customer_id = $1 AND workflow_status IN ('published', 'monitoring')`,
        [cid],
      );
      facts.push({
        customer_id: cid,
        fact_date: d,
        metric_name: 'content_published',
        metric_value: Number(published.rows[0]?.c ?? 0),
        dimensions: JSON.stringify({ source: 'seo_content' }),
      });

      const gsc = await this.db.query(
        `SELECT COALESCE(SUM(clicks),0) AS clicks, COALESCE(SUM(impressions),0) AS impressions
         FROM ${SCHEMA}.seo_gsc_daily_stats WHERE customer_id = $1 AND stat_date = $2::date`,
        [cid, d],
      );
      const gscRow = gsc.rows[0];
      if (gscRow) {
        facts.push({
          customer_id: cid,
          fact_date: d,
          metric_name: 'gsc_clicks',
          metric_value: Number(gscRow.clicks ?? 0),
          dimensions: JSON.stringify({ stat_date: d }),
        });
        facts.push({
          customer_id: cid,
          fact_date: d,
          metric_name: 'gsc_impressions',
          metric_value: Number(gscRow.impressions ?? 0),
          dimensions: JSON.stringify({ stat_date: d }),
        });
      }

      const crit = await this.db.query<{ c: string }>(
        `SELECT COUNT(*) AS c FROM ${SCHEMA}.seo_technical_issues
         WHERE customer_id = $1 AND severity = 'critical'
           AND status NOT IN ('closed', 'verified')`,
        [cid],
      );
      facts.push({
        customer_id: cid,
        fact_date: d,
        metric_name: 'critical_issues_open',
        metric_value: Number(crit.rows[0]?.c ?? 0),
        dimensions: '{}',
      });

      const aeo = await this.db.query(
        `SELECT COUNT(*) AS t,
                SUM(CASE WHEN COALESCE(m.brand_visible, 0) = 1 THEN 1 ELSE 0 END) AS v
         FROM ${SCHEMA}.seo_questions q
         LEFT JOIN LATERAL (
           SELECT brand_visible FROM ${SCHEMA}.seo_ai_mentions
           WHERE question_id = q.id ORDER BY id DESC LIMIT 1
         ) m ON TRUE
         WHERE q.customer_id = $1 AND q.status = 'active'`,
        [cid],
      );
      const aeoRow = aeo.rows[0];
      const total = Number(aeoRow?.t ?? 0);
      if (total > 0) {
        const visible = Number(aeoRow?.v ?? 0);
        facts.push({
          customer_id: cid,
          fact_date: d,
          metric_name: 'aeo_coverage_pct',
          metric_value: Math.round((100 * visible) / total * 100) / 100,
          dimensions: JSON.stringify({ visible, total }),
        });
      }

      const rev = await this.organicRevenueTotal(cid, 28);
      if (rev > 0) {
        facts.push({
          customer_id: cid,
          fact_date: d,
          metric_name: 'organic_revenue',
          metric_value: rev,
          dimensions: '{}',
        });
      }
    }
    return facts;
  }

  async paritySample(days = 7): Promise<SeoBiParityResponse> {
    const safeDays = Math.max(1, Math.min(days, 30));
    const factDate = new Date().toISOString().slice(0, 10);
    const sampleFacts = await this.collectDailyFacts(factDate);
    const totalsByMetric: Record<string, number> = {};
    for (const fact of sampleFacts) {
      totalsByMetric[fact.metric_name] = (totalsByMetric[fact.metric_name] ?? 0) + fact.metric_value;
    }
    const presentMetrics = BI_METRICS.filter((m) => sampleFacts.some((f) => f.metric_name === m));
    return {
      ok: presentMetrics.length >= 3,
      days: safeDays,
      fact_date: factDate,
      metrics: presentMetrics,
      sample_facts: sampleFacts.slice(0, 50),
      totals_by_metric: totalsByMetric,
    };
  }

  private organicFilterSql(): string {
    return `(
      LOWER(source_medium) LIKE '%organic%'
      OR LOWER(source_medium) = 'google / organic'
      OR LOWER(source_medium) LIKE 'google / organic%'
    )`;
  }

  async organicRevenueTotal(customerId: number, days = 28): Promise<number> {
    const safeDays = Math.max(1, Math.min(days, 365));
    const result = await this.db.query(
      `SELECT COALESCE(SUM(revenue), 0) AS total
       FROM ${SCHEMA}.seo_ga4_daily_stats
       WHERE customer_id = $1
         AND stat_date >= CURRENT_DATE - ($2::int || ' days')::interval
         AND ${this.organicFilterSql()}`,
      [customerId, safeDays],
    );
    return Number(result.rows[0]?.total ?? 0);
  }

  async attributionSummary(customerId: number, days = 28): Promise<SeoAttributionSummary> {
    const safeDays = Math.max(1, Math.min(days, 365));
    const result = await this.db.query(
      `SELECT
         COALESCE(SUM(sessions), 0) AS sessions,
         COALESCE(SUM(users), 0) AS users,
         COALESCE(SUM(conversions), 0) AS conversions,
         COALESCE(SUM(revenue), 0) AS revenue,
         COUNT(DISTINCT landing_page) AS landing_pages
       FROM ${SCHEMA}.seo_ga4_daily_stats
       WHERE customer_id = $1
         AND stat_date >= CURRENT_DATE - ($2::int || ' days')::interval
         AND ${this.organicFilterSql()}`,
      [customerId, safeDays],
    );
    const row = result.rows[0] ?? {};
    const sessions = Number(row.sessions ?? 0);
    const revenue = Number(row.revenue ?? 0);
    const conversions = Number(row.conversions ?? 0);
    return {
      customer_id: customerId,
      days: safeDays,
      sessions,
      users: Number(row.users ?? 0),
      conversions: Math.round(conversions * 100) / 100,
      revenue: Math.round(revenue * 100) / 100,
      landing_pages: Number(row.landing_pages ?? 0),
      revenue_per_session: sessions ? Math.round((revenue / sessions) * 10000) / 10000 : 0,
      conversion_rate: sessions ? Math.round((conversions / sessions) * 10000) / 10000 : 0,
    };
  }

  async topOrganicLandingPages(
    customerId: number,
    days = 28,
    limit = 10,
  ): Promise<SeoAttributionLandingPage[]> {
    const safeDays = Math.max(1, Math.min(days, 365));
    const safeLimit = Math.max(1, Math.min(limit, 50));
    const result = await this.db.query(
      `SELECT landing_page,
              COALESCE(SUM(sessions), 0) AS sessions,
              COALESCE(SUM(revenue), 0) AS revenue,
              COALESCE(SUM(conversions), 0) AS conversions
       FROM ${SCHEMA}.seo_ga4_daily_stats
       WHERE customer_id = $1
         AND stat_date >= CURRENT_DATE - ($2::int || ' days')::interval
         AND ${this.organicFilterSql()}
         AND landing_page != ''
       GROUP BY landing_page
       ORDER BY revenue DESC, sessions DESC
       LIMIT $3`,
      [customerId, safeDays, safeLimit],
    );
    return result.rows.map((r) => {
      const sessions = Number(r.sessions ?? 0);
      const revenue = Number(r.revenue ?? 0);
      const conversions = Number(r.conversions ?? 0);
      return {
        landing_page: String(r.landing_page ?? ''),
        sessions,
        revenue: Math.round(revenue * 100) / 100,
        conversions: Math.round(conversions * 100) / 100,
        revenue_per_session: sessions ? Math.round((revenue / sessions) * 10000) / 10000 : 0,
      };
    });
  }
}
