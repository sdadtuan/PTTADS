import { Injectable, NotFoundException, OnModuleDestroy } from '@nestjs/common';
import { DatabaseSync } from 'node:sqlite';
import { Pool } from 'pg';
import { AppConfigService } from '../config/app-config.service';
import {
  SeoClientSettings,
  SeoClientTaskServiceRow,
  SeoClientTaskTechnicalRow,
  SeoClientTasksResponse,
  SeoClientWorkspaceResponse,
  SeoHubAlert,
  SeoHubClientRow,
  SeoHubResponse,
  SeoHubSummaryBlock,
  SeoIntegrationPublicStatus,
  SeoSettingsUpdateBody,
  SeoSyncRunRow,
  SEO_AEO_SERVICE_SLUGS,
} from './seo-admin.types';

const SCHEMA = 'seo_aeo';

function parseJsonObject(raw: unknown): Record<string, unknown> {
  if (raw && typeof raw === 'object' && !Array.isArray(raw)) {
    return raw as Record<string, unknown>;
  }
  if (raw == null) return {};
  try {
    const parsed = JSON.parse(String(raw));
    return parsed && typeof parsed === 'object' && !Array.isArray(parsed)
      ? (parsed as Record<string, unknown>)
      : {};
  } catch {
    return {};
  }
}

function integrationPublic(gscOrGa4: Record<string, unknown>): SeoIntegrationPublicStatus {
  const connected = Boolean(gscOrGa4.refresh_token_encrypted || gscOrGa4.refresh_token);
  return {
    connected,
    site_url: String(gscOrGa4.site_url ?? ''),
    property_id: String(gscOrGa4.property_id ?? ''),
    status: String(gscOrGa4.status ?? (connected ? 'connected' : 'disconnected')),
    connected_at: gscOrGa4.connected_at != null ? String(gscOrGa4.connected_at) : null,
    last_sync_at: gscOrGa4.last_sync_at != null ? String(gscOrGa4.last_sync_at) : null,
    last_sync_status: gscOrGa4.last_sync_status != null ? String(gscOrGa4.last_sync_status) : null,
  };
}

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
  private sqlite: DatabaseSync | null = null;

  constructor(private readonly config: AppConfigService) {}

  private get db(): Pool {
    if (!this.pool) {
      this.pool = new Pool({ connectionString: this.config.databaseUrl });
    }
    return this.pool;
  }

  private get sqliteDb(): DatabaseSync | null {
    if (!this.config.sqliteAvailable()) return null;
    if (!this.sqlite) {
      this.sqlite = new DatabaseSync(this.config.sqlitePath);
      this.sqlite.exec('PRAGMA foreign_keys = ON');
    }
    return this.sqlite;
  }

  onModuleDestroy(): void {
    void this.pool?.end();
    this.pool = null;
    if (this.sqlite) {
      this.sqlite.close();
      this.sqlite = null;
    }
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

  async getClientWorkspace(customerId: number): Promise<SeoClientWorkspaceResponse> {
    const hub = await this.hubSummary({ customerId, days: 28 });
    const client = hub.clients.find((c) => c.customer_id === customerId);
    if (!client) {
      throw new NotFoundException({ error: 'seo_client_not_found', customer_id: customerId });
    }
    const [settings, syncRuns, delivery, gscTotals] = await Promise.all([
      this.getSettings(customerId),
      this.listSyncRuns(customerId, 8),
      this.contentDelivery(customerId),
      this.gscTotals(customerId, 28),
    ]);
    const integrations = settings.integrations;
    const gsc = parseJsonObject(integrations.gsc);
    const ga4 = parseJsonObject(integrations.ga4);
    return {
      ok: true,
      client,
      settings,
      integrations: {
        gsc: integrationPublic(gsc),
        ga4: integrationPublic(ga4),
      },
      sync_runs: syncRuns,
      gsc_totals: gscTotals,
      content_delivery: delivery,
    };
  }

  async getSettings(customerId: number): Promise<SeoClientSettings> {
    const result = await this.db.query<{
      customer_id: number;
      domains_json: unknown;
      markets_json: unknown;
      languages_json: unknown;
      industry: string;
      brand_guidelines_json: unknown;
      seo_guidelines_json: unknown;
      aeo_guidelines_json: unknown;
      contract_tier: string;
      notes: string;
      integrations_json: unknown;
      updated_at: Date | null;
    }>(
      `SELECT customer_id, domains_json, markets_json, languages_json, industry,
              brand_guidelines_json, seo_guidelines_json, aeo_guidelines_json,
              contract_tier, notes, integrations_json, updated_at
       FROM ${SCHEMA}.seo_client_settings WHERE customer_id = $1`,
      [customerId],
    );
    const row = result.rows[0];
    if (!row) {
      return {
        customer_id: customerId,
        domains: [],
        markets: [],
        languages: ['vi'],
        industry: '',
        brand_guidelines: {},
        seo_guidelines: {},
        aeo_guidelines: {},
        contract_tier: 'standard',
        notes: '',
        integrations: {},
        updated_at: null,
      };
    }
    return {
      customer_id: row.customer_id,
      domains: parseJsonArray(row.domains_json),
      markets: parseJsonArray(row.markets_json),
      languages: parseJsonArray(row.languages_json).length
        ? parseJsonArray(row.languages_json)
        : ['vi'],
      industry: row.industry ?? '',
      brand_guidelines: parseJsonObject(row.brand_guidelines_json),
      seo_guidelines: parseJsonObject(row.seo_guidelines_json),
      aeo_guidelines: parseJsonObject(row.aeo_guidelines_json),
      contract_tier: row.contract_tier ?? 'standard',
      notes: row.notes ?? '',
      integrations: parseJsonObject(row.integrations_json),
      updated_at: row.updated_at ? row.updated_at.toISOString() : null,
    };
  }

  async upsertSettings(customerId: number, body: SeoSettingsUpdateBody): Promise<SeoClientSettings> {
    const existing = await this.getSettings(customerId);
    const merged: SeoClientSettings = {
      ...existing,
      domains: body.domains ?? existing.domains,
      markets: body.markets ?? existing.markets,
      languages: body.languages ?? existing.languages,
      industry: body.industry ?? existing.industry,
      brand_guidelines: body.brand_guidelines ?? existing.brand_guidelines,
      seo_guidelines: body.seo_guidelines ?? existing.seo_guidelines,
      aeo_guidelines: body.aeo_guidelines ?? existing.aeo_guidelines,
      contract_tier: body.contract_tier ?? existing.contract_tier,
      notes: body.notes ?? existing.notes,
      integrations: body.integrations
        ? { ...existing.integrations, ...body.integrations }
        : existing.integrations,
      updated_at: new Date().toISOString(),
    };
    await this.db.query(
      `INSERT INTO ${SCHEMA}.seo_client_settings (
         customer_id, domains_json, markets_json, languages_json, industry,
         brand_guidelines_json, seo_guidelines_json, aeo_guidelines_json,
         contract_tier, notes, integrations_json, updated_at
       ) VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9,$10,$11,NOW())
       ON CONFLICT (customer_id) DO UPDATE SET
         domains_json = EXCLUDED.domains_json,
         markets_json = EXCLUDED.markets_json,
         languages_json = EXCLUDED.languages_json,
         industry = EXCLUDED.industry,
         brand_guidelines_json = EXCLUDED.brand_guidelines_json,
         seo_guidelines_json = EXCLUDED.seo_guidelines_json,
         aeo_guidelines_json = EXCLUDED.aeo_guidelines_json,
         contract_tier = EXCLUDED.contract_tier,
         notes = EXCLUDED.notes,
         integrations_json = EXCLUDED.integrations_json,
         updated_at = NOW()`,
      [
        customerId,
        JSON.stringify(merged.domains),
        JSON.stringify(merged.markets),
        JSON.stringify(merged.languages),
        merged.industry,
        JSON.stringify(merged.brand_guidelines),
        JSON.stringify(merged.seo_guidelines),
        JSON.stringify(merged.aeo_guidelines),
        merged.contract_tier,
        merged.notes,
        JSON.stringify(merged.integrations),
      ],
    );
    return this.getSettings(customerId);
  }

  async listSyncRuns(customerId: number, limit = 10): Promise<SeoSyncRunRow[]> {
    const result = await this.db.query<{
      id: number;
      customer_id: number;
      source: string;
      status: string;
      started_at: Date | null;
      finished_at: Date | null;
      rows_imported: number;
      error_message: string;
    }>(
      `SELECT id, customer_id, source, status, started_at, finished_at, rows_imported, error_message
       FROM ${SCHEMA}.seo_sync_runs
       WHERE customer_id = $1
       ORDER BY COALESCE(started_at, finished_at) DESC NULLS LAST, id DESC
       LIMIT $2`,
      [customerId, limit],
    );
    return result.rows.map((row) => ({
      id: row.id,
      customer_id: row.customer_id,
      source: row.source,
      status: row.status,
      started_at: row.started_at ? row.started_at.toISOString() : null,
      finished_at: row.finished_at ? row.finished_at.toISOString() : null,
      rows_imported: row.rows_imported,
      error_message: row.error_message ?? '',
    }));
  }

  async createSyncRun(customerId: number, source: string): Promise<number> {
    const result = await this.db.query<{ id: string }>(
      `INSERT INTO ${SCHEMA}.seo_sync_runs (customer_id, source, status, started_at)
       VALUES ($1, $2, 'pending', NOW())
       RETURNING id`,
      [customerId, source],
    );
    return Number(result.rows[0]?.id ?? 0);
  }

  async listClientTasks(customerId: number): Promise<SeoClientTasksResponse> {
    const serviceTasks = this.listServiceTasksFromSqlite(customerId);
    const technicalIssues = await this.listTechnicalIssues(customerId);
    return {
      ok: true,
      customer_id: customerId,
      service_tasks: serviceTasks,
      technical_issues: technicalIssues,
      open_count: serviceTasks.length + technicalIssues.length,
    };
  }

  private listServiceTasksFromSqlite(customerId: number): SeoClientTaskServiceRow[] {
    const db = this.sqliteDb;
    if (!db) return [];
    try {
      const table = db
        .prepare("SELECT 1 FROM sqlite_master WHERE type='table' AND name='crm_service_lifecycle'")
        .get();
      if (!table) return [];
      const placeholders = SEO_AEO_SERVICE_SLUGS.map(() => '?').join(',');
      const lifecycles = db
        .prepare(
          `SELECT id, service_slug FROM crm_service_lifecycle
           WHERE customer_id = ? AND service_slug IN (${placeholders})
           ORDER BY id DESC`,
        )
        .all(customerId, ...SEO_AEO_SERVICE_SLUGS) as Array<{ id: number; service_slug: string }>;
      const tasks: SeoClientTaskServiceRow[] = [];
      for (const lc of lifecycles) {
        const taskTable = db
          .prepare("SELECT 1 FROM sqlite_master WHERE type='table' AND name='crm_svc_tasks'")
          .get();
        if (!taskTable) continue;
        const rows = db
          .prepare(
            `SELECT id, lifecycle_id, stage, title, due_on, is_done
             FROM crm_svc_tasks WHERE lifecycle_id = ? AND is_done = 0
             ORDER BY stage, step_index ASC, id ASC`,
          )
          .all(lc.id) as Array<{
          id: number;
          lifecycle_id: number;
          stage: string;
          title: string;
          due_on: string | null;
          is_done: number;
        }>;
        for (const row of rows) {
          tasks.push({
            kind: 'service',
            task_id: row.id,
            lifecycle_id: row.lifecycle_id,
            service_slug: lc.service_slug,
            stage: row.stage,
            title: row.title || `Task #${row.id}`,
            due_on: row.due_on ?? '',
            url: `/crm/service-delivery/${row.lifecycle_id}#task-card-${row.id}`,
          });
        }
      }
      return tasks;
    } catch {
      return [];
    }
  }

  private async listTechnicalIssues(customerId: number): Promise<SeoClientTaskTechnicalRow[]> {
    const result = await this.db.query<{
      id: number;
      issue_type: string;
      url: string;
      severity: string;
      status: string;
      crm_task_id: number | null;
      lifecycle_id: number | null;
    }>(
      `SELECT id, issue_type, url, severity, status, crm_task_id, lifecycle_id
       FROM ${SCHEMA}.seo_technical_issues
       WHERE customer_id = $1 AND status NOT IN ('closed', 'verified')
       ORDER BY CASE severity WHEN 'critical' THEN 0 WHEN 'high' THEN 1 ELSE 2 END, id DESC`,
      [customerId],
    );
    return result.rows.map((issue) => {
      const taskId = issue.crm_task_id;
      const lifecycleId = issue.lifecycle_id;
      let url = `/seo/technical?customer_id=${customerId}`;
      if (taskId && lifecycleId) {
        url = `/crm/service-delivery/${lifecycleId}#task-card-${taskId}`;
      }
      return {
        kind: 'technical',
        issue_id: issue.id,
        crm_task_id: taskId,
        lifecycle_id: lifecycleId,
        title: `${issue.issue_type || 'issue'} — ${issue.url || ''}`.slice(0, 120),
        severity: issue.severity ?? '',
        status: issue.status ?? '',
        url,
      };
    });
  }
}
