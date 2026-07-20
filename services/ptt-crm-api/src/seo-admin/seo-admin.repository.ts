import { Injectable, OnModuleDestroy } from '@nestjs/common';
import { Pool } from 'pg';
import { AppConfigService } from '../config/app-config.service';
import {
  SeoHubAlert,
  SeoHubClientRow,
  SeoHubResponse,
  SeoHubSummaryBlock,
} from './seo-admin.types';

const SCHEMA = 'seo_aeo';

function parseJsonArray(raw: unknown): string[] {
  if (Array.isArray(raw)) return raw.map(String);
  if (raw == null) return [];
  try {
    const parsed = JSON.parse(String(raw));
    return Array.isArray(parsed) ? parsed.map(String) : [];
  } catch {
    return [];
  }
}

function healthTier(score: number): 'good' | 'warn' | 'bad' {
  if (score >= 75) return 'good';
  if (score >= 50) return 'warn';
  return 'bad';
}

function computeHealthScore(params: {
  settingsOk: boolean;
  aeoCoveragePct: number;
  aeoQueries: number;
  criticalIssues: number;
  contentOverdue: number;
}): number {
  let score = 50;
  if (params.settingsOk) score += 15;
  else score -= 20;
  if (params.aeoQueries > 0) score += Math.min(25, Math.floor(params.aeoCoveragePct * 0.25));
  else score += 10;
  score -= Math.min(30, params.criticalIssues * 10);
  score -= Math.min(15, params.contentOverdue * 3);
  return Math.max(0, Math.min(100, score));
}

@Injectable()
export class SeoAdminRepository implements OnModuleDestroy {
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

  async hubSummary(params: {
    customerId?: number;
    days: number;
    market?: string;
  }): Promise<SeoHubResponse> {
    const settingsRows = await this.db.query<{
      customer_id: number;
      domains_json: unknown;
      markets_json: unknown;
      industry: string;
      contract_tier: string;
    }>(
      `SELECT customer_id, domains_json, markets_json, industry, contract_tier
       FROM ${SCHEMA}.seo_client_settings
       ORDER BY customer_id ASC`,
    );

    let baseClients = settingsRows.rows;
    if (baseClients.length === 0) {
      const fallback = await this.db.query<{ customer_id: number }>(
        `SELECT DISTINCT customer_id FROM ${SCHEMA}.seo_projects ORDER BY customer_id`,
      );
      baseClients = fallback.rows.map((row) => ({
        customer_id: row.customer_id,
        domains_json: [],
        markets_json: [],
        industry: '',
        contract_tier: 'standard',
      }));
    }

    const clients: SeoHubClientRow[] = [];
    for (const row of baseClients) {
      if (params.customerId != null && row.customer_id !== params.customerId) continue;
      const domains = parseJsonArray(row.domains_json);
      const markets = parseJsonArray(row.markets_json);
      if (params.market) {
        const m = params.market.toUpperCase();
        if (!markets.some((x) => x.toUpperCase() === m)) continue;
      }
      const settingsOk = domains.length > 0 || Boolean((row.industry ?? '').trim());
      const [aeo, critical, overdue, projects, initiatives] = await Promise.all([
        this.aeoTotals(row.customer_id),
        this.criticalCount(row.customer_id),
        this.contentOverdue(row.customer_id),
        this.activeProjects(row.customer_id),
        this.activeInitiatives(row.customer_id),
      ]);
      const coverage =
        aeo.total > 0 ? Math.round((1000 * aeo.visible) / aeo.total) / 10 : 0;
      const health = computeHealthScore({
        settingsOk,
        aeoCoveragePct: coverage,
        aeoQueries: aeo.total,
        criticalIssues: critical,
        contentOverdue: overdue,
      });
      clients.push({
        customer_id: row.customer_id,
        customer_name: domains[0] ? `SEO #${row.customer_id} · ${domains[0]}` : `SEO Client #${row.customer_id}`,
        customer_company: (row.industry ?? '').trim() || '—',
        settings_ok: settingsOk,
        domains,
        markets,
        contract_tier: row.contract_tier ?? 'standard',
        active_projects: projects,
        active_initiatives: initiatives,
        aeo_queries: aeo.total,
        aeo_visible: aeo.visible,
        aeo_coverage_pct: coverage,
        critical_issues: critical,
        content_overdue: overdue,
        health_score: health,
        health_tier: healthTier(health),
      });
    }

    const [openAlerts, failedSync, globalCritical, delivery, gscTotals] = await Promise.all([
      this.openAlertsCount(),
      this.failedSyncRuns(),
      this.criticalCount(null),
      this.contentDelivery(params.customerId),
      this.gscTotals(params.customerId, Math.min(params.days, 28)),
    ]);

    const summary: SeoHubSummaryBlock = {
      seo_clients: clients.length,
      active_lifecycles: clients.length,
      aeo_queries_total: clients.reduce((s, c) => s + c.aeo_queries, 0),
      aeo_visible_total: clients.reduce((s, c) => s + c.aeo_visible, 0),
      aeo_coverage_pct:
        clients.reduce((s, c) => s + c.aeo_queries, 0) > 0
          ? Math.round(
              (1000 * clients.reduce((s, c) => s + c.aeo_visible, 0)) /
                clients.reduce((s, c) => s + c.aeo_queries, 0),
            ) / 10
          : 0,
      settings_missing: clients.filter((c) => !c.settings_ok).length,
      active_initiatives: clients.reduce((s, c) => s + c.active_initiatives, 0),
      critical_issues: globalCritical,
      open_alerts: openAlerts,
      failed_sync_runs: failedSync,
      organic_growth_pct: 0,
      publish_sla_pct: Math.round(
        (1000 * delivery.published) /
          Math.max(1, delivery.published + delivery.overdue + delivery.in_review),
      ) / 10,
    };

    const alerts: SeoHubAlert[] = [];
    if (summary.settings_missing > 0) {
      alerts.push({
        severity: 'warn',
        message: `${summary.settings_missing} client SEO chưa cấu hình domain/industry.`,
        link: '/seo/clients',
        link_label: 'Xem client',
      });
    }
    if (globalCritical > 0) {
      alerts.push({
        severity: 'danger',
        message: `${globalCritical} issue kỹ thuật critical đang mở.`,
        link: '/seo/technical',
        link_label: 'Technical Console',
      });
    }
    if (openAlerts > 0) {
      alerts.push({
        severity: 'warn',
        message: `${openAlerts} cảnh báo automation đang mở.`,
        link: '/seo/automations',
        link_label: 'Automations',
      });
    }
    for (const c of clients) {
      if (c.aeo_queries > 0 && c.aeo_coverage_pct < 50) {
        alerts.push({
          severity: 'warn',
          message: `AEO coverage thấp (${c.aeo_coverage_pct}%) — ${c.customer_name}.`,
          link: `/seo/clients/${c.customer_id}`,
          link_label: 'Mở client',
        });
      }
    }

    return {
      ok: true,
      summary,
      clients,
      alerts,
      executive: {
        gsc_totals: gscTotals,
        content_delivery: delivery,
        filters: {
          customer_id: params.customerId ?? null,
          days: params.days,
          market: params.market ?? null,
        },
      },
    };
  }

  private async aeoTotals(customerId: number): Promise<{ total: number; visible: number }> {
    const result = await this.db.query<{ total: string; visible: string }>(
      `SELECT COUNT(*) AS total,
              COALESCE(SUM(CASE WHEN brand_visible THEN 1 ELSE 0 END), 0) AS visible
       FROM ${SCHEMA}.seo_questions WHERE customer_id = $1`,
      [customerId],
    );
    return {
      total: Number(result.rows[0]?.total ?? 0),
      visible: Number(result.rows[0]?.visible ?? 0),
    };
  }

  private async criticalCount(customerId: number | null): Promise<number> {
    const params: unknown[] = [];
    let sql = `SELECT COUNT(*) AS c FROM ${SCHEMA}.seo_technical_issues
               WHERE severity = 'critical' AND status NOT IN ('closed', 'verified')`;
    if (customerId != null) {
      sql += ' AND customer_id = $1';
      params.push(customerId);
    }
    const result = await this.db.query<{ c: string }>(sql, params);
    return Number(result.rows[0]?.c ?? 0);
  }

  private async contentOverdue(customerId: number): Promise<number> {
    const result = await this.db.query<{ c: string }>(
      `SELECT COUNT(*) AS c FROM ${SCHEMA}.seo_content
       WHERE customer_id = $1
         AND workflow_status NOT IN ('published', 'monitoring', 'archived')
         AND due_date IS NOT NULL
         AND due_date < CURRENT_DATE`,
      [customerId],
    );
    return Number(result.rows[0]?.c ?? 0);
  }

  private async activeProjects(customerId: number): Promise<number> {
    const result = await this.db.query<{ c: string }>(
      `SELECT COUNT(*) AS c FROM ${SCHEMA}.seo_projects
       WHERE customer_id = $1 AND status = 'active'`,
      [customerId],
    );
    return Number(result.rows[0]?.c ?? 0);
  }

  private async activeInitiatives(customerId: number): Promise<number> {
    const result = await this.db.query<{ c: string }>(
      `SELECT COUNT(*) AS c FROM ${SCHEMA}.seo_initiatives
       WHERE customer_id = $1 AND status IN ('planned', 'in_progress')`,
      [customerId],
    );
    return Number(result.rows[0]?.c ?? 0);
  }

  private async openAlertsCount(): Promise<number> {
    const result = await this.db.query<{ c: string }>(
      `SELECT COUNT(*) AS c FROM ${SCHEMA}.seo_alerts WHERE status = 'open'`,
    );
    return Number(result.rows[0]?.c ?? 0);
  }

  private async failedSyncRuns(): Promise<number> {
    const result = await this.db.query<{ c: string }>(
      `SELECT COUNT(*) AS c FROM ${SCHEMA}.seo_sync_runs
       WHERE status IN ('failed', 'error')
         AND started_at >= NOW() - INTERVAL '7 days'`,
    );
    return Number(result.rows[0]?.c ?? 0);
  }

  private async contentDelivery(customerId?: number): Promise<Record<string, number>> {
    const params: unknown[] = [];
    let sql = `SELECT workflow_status, COUNT(*) AS c FROM ${SCHEMA}.seo_content
               WHERE workflow_status != 'archived'`;
    if (customerId != null) {
      sql += ' AND customer_id = $1';
      params.push(customerId);
    }
    sql += ' GROUP BY workflow_status';
    const result = await this.db.query<{ workflow_status: string; c: string }>(sql, params);
    const byStatus: Record<string, number> = {};
    for (const row of result.rows) {
      byStatus[row.workflow_status] = Number(row.c);
    }
    const inReview = ['seo_review', 'aeo_review', 'technical_review', 'client_review'].reduce(
      (s, st) => s + (byStatus[st] ?? 0),
      0,
    );
    const overdueResult = await this.db.query<{ c: string }>(
      customerId != null
        ? `SELECT COUNT(*) AS c FROM ${SCHEMA}.seo_content
           WHERE customer_id = $1
             AND workflow_status NOT IN ('published', 'monitoring', 'archived')
             AND due_date IS NOT NULL AND due_date < CURRENT_DATE`
        : `SELECT COUNT(*) AS c FROM ${SCHEMA}.seo_content
           WHERE workflow_status NOT IN ('published', 'monitoring', 'archived')
             AND due_date IS NOT NULL AND due_date < CURRENT_DATE`,
      customerId != null ? [customerId] : [],
    );
    return {
      in_writing: byStatus.in_writing ?? 0,
      in_review: inReview,
      overdue: Number(overdueResult.rows[0]?.c ?? 0),
      published: (byStatus.published ?? 0) + (byStatus.monitoring ?? 0),
    };
  }

  private async gscTotals(
    customerId: number | undefined,
    days: number,
  ): Promise<Record<string, unknown>> {
    const params: unknown[] = [Math.max(1, days)];
    let sql = `SELECT COALESCE(SUM(clicks), 0) AS clicks,
                      COALESCE(SUM(impressions), 0) AS impressions
               FROM ${SCHEMA}.seo_gsc_daily_stats
               WHERE stat_date >= CURRENT_DATE - ($1::int * INTERVAL '1 day')`;
    if (customerId != null) {
      sql += ' AND customer_id = $2';
      params.push(customerId);
    }
    const result = await this.db.query<{ clicks: string; impressions: string }>(sql, params);
    const clicks = Number(result.rows[0]?.clicks ?? 0);
    const impressions = Number(result.rows[0]?.impressions ?? 0);
    return {
      clicks,
      impressions,
      avg_ctr: impressions > 0 ? Math.round((clicks / impressions) * 10000) / 10000 : 0,
    };
  }
}
