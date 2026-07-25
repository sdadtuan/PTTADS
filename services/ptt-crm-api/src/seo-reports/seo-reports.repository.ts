import { BadRequestException, Injectable, OnModuleDestroy } from '@nestjs/common';
import { Pool } from 'pg';
import { AppConfigService } from '../config/app-config.service';
import { notifySeoAlert } from './seo-alert-notify.util';
import { DASHBOARD_TYPES, SEO_REPORTS_SCHEMA } from './seo-reports.constants';
import { SeoAlertRow, SeoDashboardResponse, SeoReportScheduleRow } from './seo-reports.types';

const SCHEMA = SEO_REPORTS_SCHEMA;

function tsUtc(): string {
  return new Date().toISOString().replace('T', ' ').slice(0, 19);
}

function parseEmails(raw: unknown): string[] {
  if (Array.isArray(raw)) return raw.map(String).filter(Boolean);
  if (raw == null) return [];
  try {
    const parsed = JSON.parse(String(raw));
    return Array.isArray(parsed) ? parsed.map(String).filter(Boolean) : [];
  } catch {
    return [];
  }
}

@Injectable()
export class SeoReportsRepository implements OnModuleDestroy {
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

  private async gscSummary(customerId: number | null): Promise<Record<string, unknown>> {
    const values: unknown[] = [];
    let sql = `SELECT COALESCE(SUM(clicks),0) AS clicks, COALESCE(SUM(impressions),0) AS impressions
               FROM ${SCHEMA}.seo_gsc_daily_stats WHERE stat_date >= CURRENT_DATE - INTERVAL '28 days'`;
    if (customerId != null) {
      values.push(customerId);
      sql += ` AND customer_id = $${values.length}`;
    }
    const result = await this.db.query(sql, values);
    const row = result.rows[0] ?? {};
    const clicks = Number(row.clicks ?? 0);
    const impressions = Number(row.impressions ?? 0);
    return {
      clicks,
      impressions,
      avg_ctr: impressions ? Math.round((clicks / impressions) * 10000) / 10000 : 0,
    };
  }

  private async gscTrend(customerId: number | null, days = 28) {
    const values: unknown[] = [days];
    let sql = `SELECT stat_date::text, COALESCE(SUM(clicks),0)::int AS clicks, COALESCE(SUM(impressions),0)::int AS impressions
               FROM ${SCHEMA}.seo_gsc_daily_stats WHERE stat_date >= CURRENT_DATE - ($1::int || ' days')::interval`;
    if (customerId != null) {
      values.push(customerId);
      sql += ` AND customer_id = $${values.length}`;
    }
    sql += ' GROUP BY stat_date ORDER BY stat_date ASC';
    const result = await this.db.query(sql, values);
    return result.rows.map((r) => ({
      stat_date: String(r.stat_date),
      clicks: Number(r.clicks),
      impressions: Number(r.impressions),
    }));
  }

  private async contentByStatus(customerId: number | null): Promise<Record<string, number>> {
    const values: unknown[] = [];
    let sql = `SELECT workflow_status, COUNT(*) AS c FROM ${SCHEMA}.seo_content WHERE workflow_status != 'archived'`;
    if (customerId != null) {
      values.push(customerId);
      sql += ` AND customer_id = $${values.length}`;
    }
    sql += ' GROUP BY workflow_status';
    const result = await this.db.query(sql, values);
    const out: Record<string, number> = {};
    for (const row of result.rows) out[String(row.workflow_status)] = Number(row.c);
    return out;
  }

  private async countOpenCritical(customerId: number | null): Promise<number> {
    const values: unknown[] = [];
    let sql = `SELECT COUNT(*) AS c FROM ${SCHEMA}.seo_technical_issues
               WHERE severity = 'critical' AND status NOT IN ('closed','verified')`;
    if (customerId != null) {
      values.push(customerId);
      sql += ` AND customer_id = $${values.length}`;
    }
    const result = await this.db.query(sql, values);
    return Number(result.rows[0]?.c ?? 0);
  }

  private async aeoCoverage(customerId: number): Promise<Record<string, unknown>> {
    const result = await this.db.query(
      `SELECT COUNT(*) AS total,
              SUM(CASE WHEN COALESCE(m.brand_visible, 0) = 1 THEN 1 ELSE 0 END) AS visible
       FROM ${SCHEMA}.seo_questions q
       LEFT JOIN LATERAL (
         SELECT brand_visible FROM ${SCHEMA}.seo_ai_mentions
         WHERE question_id = q.id ORDER BY id DESC LIMIT 1
       ) m ON true
       WHERE q.customer_id = $1 AND q.status = 'active'`,
      [customerId],
    );
    const total = Number(result.rows[0]?.total ?? 0);
    const visible = Number(result.rows[0]?.visible ?? 0);
    return {
      total,
      visible,
      coverage_pct: total ? Math.round((1000 * visible) / total) / 10 : 0,
    };
  }

  private async listSyncRuns(customerId: number | null, limit: number) {
    const values: unknown[] = [limit];
    let sql = `SELECT id, customer_id, source, status, started_at, finished_at, rows_imported, error_message
               FROM ${SCHEMA}.seo_sync_runs`;
    if (customerId != null) {
      values.unshift(customerId);
      sql += ` WHERE customer_id = $1 ORDER BY id DESC LIMIT $2`;
    } else {
      sql += ' ORDER BY id DESC LIMIT $1';
    }
    const result = await this.db.query(sql, values);
    return result.rows;
  }

  async dashboard(customerId: number | null, dashboardType: string): Promise<SeoDashboardResponse> {
    const type = dashboardType.trim().toLowerCase();
    if (!DASHBOARD_TYPES.includes(type as (typeof DASHBOARD_TYPES)[number])) {
      throw new BadRequestException({ error: 'invalid_dashboard_type', type });
    }
    const base: SeoDashboardResponse = { type, customer_id: customerId };

    if (type === 'executive') {
      return {
        ...base,
        days: 28,
        gsc: await this.gscSummary(customerId),
        gsc_trend: customerId != null ? await this.gscTrend(customerId) : [],
        critical_issues: await this.countOpenCritical(customerId),
        content_by_status: await this.contentByStatus(customerId),
        aeo: customerId != null ? await this.aeoCoverage(customerId) : { coverage_pct: 0 },
        sync_runs_recent: await this.listSyncRuns(customerId, 5),
      };
    }
    if (type === 'seo') {
      return {
        ...base,
        days: 28,
        gsc: await this.gscSummary(customerId),
        gsc_trend: customerId != null ? await this.gscTrend(customerId) : [],
      };
    }
    if (type === 'content') {
      const byStatus = await this.contentByStatus(customerId);
      return {
        ...base,
        content_by_status: byStatus,
        content_chart: Object.entries(byStatus).map(([label, value]) => ({ label, value })),
      };
    }
    if (type === 'technical') {
      if (!customerId) {
        return { ...base, severity: { critical: await this.countOpenCritical(null) }, issues: [] };
      }
      const sevResult = await this.db.query(
        `SELECT severity, COUNT(*) AS c FROM ${SCHEMA}.seo_technical_issues
         WHERE customer_id = $1 AND status NOT IN ('closed','verified') GROUP BY severity`,
        [customerId],
      );
      const severity: Record<string, number> = { critical: 0, high: 0, medium: 0, low: 0 };
      for (const row of sevResult.rows) severity[String(row.severity)] = Number(row.c);
      const issues = await this.db.query(
        `SELECT id, url, issue_type, severity, status FROM ${SCHEMA}.seo_technical_issues
         WHERE customer_id = $1 AND status NOT IN ('closed','verified') ORDER BY id DESC LIMIT 20`,
        [customerId],
      );
      return {
        ...base,
        severity,
        severity_chart: ['critical', 'high', 'medium', 'low'].map((label) => ({
          label,
          value: severity[label] ?? 0,
        })),
        issues: issues.rows,
      };
    }
    if (type === 'aeo') {
      return {
        ...base,
        aeo: customerId != null ? await this.aeoCoverage(customerId) : { coverage_pct: 0 },
      };
    }
    const openAlerts = await this.db.query(
      `SELECT COUNT(*) AS c FROM ${SCHEMA}.seo_alerts WHERE status = 'open'`,
    );
    return {
      ...base,
      content_by_status: await this.contentByStatus(customerId),
      sync_runs: await this.listSyncRuns(customerId, 10),
      open_alerts: Number(openAlerts.rows[0]?.c ?? 0),
    };
  }

  buildCsvExport(data: SeoDashboardResponse): string {
    const lines = ['metric,value'];
    const gsc = data.gsc ?? {};
    if (gsc.clicks != null) lines.push(`gsc_clicks,${gsc.clicks}`);
    if (gsc.impressions != null) lines.push(`gsc_impressions,${gsc.impressions}`);
    if (data.critical_issues != null) lines.push(`critical_issues,${data.critical_issues}`);
    const aeo = data.aeo ?? {};
    if (aeo.coverage_pct != null) lines.push(`aeo_coverage_pct,${aeo.coverage_pct}`);
    for (const [k, v] of Object.entries(data.content_by_status ?? {})) {
      lines.push(`content_${k},${v}`);
    }
    for (const [k, v] of Object.entries(data.severity ?? {})) {
      lines.push(`severity_${k},${v}`);
    }
    return lines.join('\n') + '\n';
  }

  buildHtmlExport(data: SeoDashboardResponse, customerLabel = ''): string {
    const gsc = data.gsc ?? {};
    return `<!DOCTYPE html><html><body style="font-family:system-ui;padding:24px">
<h1>SEO/AEO Report — ${data.type}</h1>
<p>${customerLabel ? `Client: ${customerLabel}<br/>` : ''}Generated: ${new Date().toISOString()}</p>
<table border="1" cellpadding="8" cellspacing="0">
<tr><th>Metric</th><th>Value</th></tr>
${gsc.clicks != null ? `<tr><td>GSC Clicks</td><td>${gsc.clicks}</td></tr>` : ''}
${gsc.impressions != null ? `<tr><td>GSC Impressions</td><td>${gsc.impressions}</td></tr>` : ''}
${data.critical_issues != null ? `<tr><td>Critical issues</td><td>${data.critical_issues}</td></tr>` : ''}
</table></body></html>`;
  }

  async listSchedules(customerId?: number): Promise<SeoReportScheduleRow[]> {
    const values: unknown[] = [];
    let sql = `SELECT * FROM ${SCHEMA}.seo_report_schedules`;
    if (customerId != null) {
      values.push(customerId);
      sql += ` WHERE customer_id = $${values.length}`;
    }
    sql += ' ORDER BY id DESC';
    const result = await this.db.query(sql, values);
    return result.rows.map((row) => ({
      id: Number(row.id),
      customer_id: Number(row.customer_id),
      dashboard_type: String(row.dashboard_type ?? 'executive'),
      cadence: String(row.cadence ?? 'weekly'),
      day_of_week: Number(row.day_of_week ?? 0),
      day_of_month: Number(row.day_of_month ?? 1),
      recipient_emails: parseEmails(row.recipient_emails_json),
      cc_emails: parseEmails(row.cc_emails_json),
      bcc_emails: parseEmails(row.bcc_emails_json),
      active: Boolean(row.active),
      next_run_at: row.next_run_at != null ? String(row.next_run_at) : null,
      last_run_at: row.last_run_at != null ? String(row.last_run_at) : null,
      created_at: row.created_at != null ? String(row.created_at) : null,
    }));
  }

  async createSchedule(customerId: number, payload: Record<string, unknown>): Promise<SeoReportScheduleRow> {
    const dashboardType = String(payload.dashboard_type ?? 'executive');
    const cadence = String(payload.cadence ?? 'weekly');
    const result = await this.db.query<{ id: string }>(
      `INSERT INTO ${SCHEMA}.seo_report_schedules (
         customer_id, dashboard_type, cadence, day_of_week, day_of_month,
         recipient_emails_json, cc_emails_json, bcc_emails_json, active, created_at
       ) VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9,NOW()) RETURNING id`,
      [
        customerId,
        dashboardType,
        cadence,
        Number(payload.day_of_week ?? 0),
        Number(payload.day_of_month ?? 1),
        JSON.stringify(payload.recipient_emails ?? []),
        JSON.stringify(payload.cc_emails ?? []),
        JSON.stringify(payload.bcc_emails ?? []),
        payload.active !== false,
      ],
    );
    const schedules = await this.listSchedules(customerId);
    const created = schedules.find((s) => s.id === Number(result.rows[0].id));
    if (!created) throw new BadRequestException({ error: 'schedule_create_failed' });
    return created;
  }

  async listAlerts(status = 'open', limit = 50): Promise<SeoAlertRow[]> {
    const result = await this.db.query(
      `SELECT * FROM ${SCHEMA}.seo_alerts WHERE status = $1 ORDER BY id DESC LIMIT $2`,
      [status, limit],
    );
    return result.rows.map((row) => ({
      id: Number(row.id),
      customer_id: row.customer_id != null ? Number(row.customer_id) : null,
      alert_type: String(row.alert_type ?? ''),
      severity: String(row.severity ?? 'warn'),
      message: String(row.message ?? ''),
      link: String(row.link ?? ''),
      status: String(row.status ?? 'open'),
      created_at: row.created_at != null ? String(row.created_at) : null,
      resolved_at: row.resolved_at != null ? String(row.resolved_at) : null,
    }));
  }

  async createAlert(params: {
    customerId?: number | null;
    alertType: string;
    message: string;
    severity?: string;
    link?: string;
  }): Promise<number | null> {
    const existing = await this.db.query(
      `SELECT id FROM ${SCHEMA}.seo_alerts
       WHERE alert_type = $1 AND message = $2 AND status = 'open'
         AND created_at >= NOW() - INTERVAL '1 day' LIMIT 1`,
      [params.alertType, params.message],
    );
    if (existing.rows[0]) return null;
    const result = await this.db.query<{ id: string }>(
      `INSERT INTO ${SCHEMA}.seo_alerts (customer_id, alert_type, severity, message, link, status, created_at)
       VALUES ($1,$2,$3,$4,$5,'open',NOW()) RETURNING id`,
      [
        params.customerId ?? null,
        params.alertType,
        params.severity ?? 'warn',
        params.message,
        params.link ?? '',
      ],
    );
    const alertId = Number(result.rows[0].id);
    void notifySeoAlert({
      alertType: params.alertType,
      message: params.message,
      link: params.link,
    });
    return alertId;
  }

  async resolveAlert(alertId: number): Promise<void> {
    await this.db.query(
      `UPDATE ${SCHEMA}.seo_alerts SET status = 'resolved', resolved_at = $2 WHERE id = $1`,
      [alertId, tsUtc()],
    );
  }

  async runAlertChecks(): Promise<Array<{ id: number; type: string }>> {
    const created: Array<{ id: number; type: string }> = [];
    const crit = await this.countOpenCritical(null);
    if (crit > 0) {
      const id = await this.createAlert({
        alertType: 'critical_issues',
        severity: 'danger',
        message: `Có ${crit} issue kỹ thuật nghiêm trọng cần xử lý.`,
        link: '/seo/technical',
      });
      if (id) created.push({ id, type: 'critical_issues' });
    }
    const failed = await this.db.query(
      `SELECT customer_id, source, error_message FROM ${SCHEMA}.seo_sync_runs
       WHERE status = 'failed' AND started_at >= NOW() - INTERVAL '7 days'
       ORDER BY id DESC LIMIT 5`,
    );
    for (const row of failed.rows) {
      const msg = `Sync ${row.source} thất bại: ${String(row.error_message ?? '').slice(0, 120)}`;
      const id = await this.createAlert({
        customerId: Number(row.customer_id),
        alertType: 'sync_failed',
        severity: 'warn',
        message: msg,
        link: '/seo/reports',
      });
      if (id) created.push({ id, type: 'sync_failed' });
    }
    return created;
  }
}
