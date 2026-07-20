import { Injectable, OnModuleDestroy } from '@nestjs/common';
import { Pool } from 'pg';
import { AppConfigService } from '../config/app-config.service';
import { revenueAttributedQuery } from './email-marketing-attribution.util';
import {
  EmailGovernanceAuditRow,
  EmailGovernanceResponse,
  EmailGovernanceRule,
  EmailHubAlert,
  EmailHubClientRow,
  EmailHubPendingApproval,
  EmailHubResponse,
  EmailHubSendCalendarItem,
  EmailHubSummary,
} from './email-marketing.types';

const SCHEMA = 'email_mkt';

function iso(value: unknown): string | null {
  if (value == null) return null;
  if (value instanceof Date) return value.toISOString();
  return String(value);
}

function pct(numerator: number, denominator: number): number {
  if (denominator <= 0) return 0;
  return Math.round((10000 * numerator) / denominator) / 100;
}

function domainHealth(params: {
  spf: string | null;
  dkim: string | null;
  dmarc: string | null;
  complaintPct: number;
}): 'healthy' | 'at_risk' | 'unknown' {
  const badDns =
    [params.spf, params.dkim, params.dmarc].filter(
      (s) => s && !['pass', 'valid', 'ok', 'unknown'].includes(String(s).toLowerCase()),
    ).length > 0;
  if (params.complaintPct >= 0.1 || badDns) return 'at_risk';
  if (!params.spf && !params.dkim && !params.dmarc) return 'unknown';
  return 'healthy';
}

@Injectable()
export class EmailMarketingRepository implements OnModuleDestroy {
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

  async schemaReady(): Promise<boolean> {
    try {
      await this.db.query(`SELECT 1 FROM ${SCHEMA}.workspaces LIMIT 1`);
      return true;
    } catch {
      return false;
    }
  }

  async hubSummary(params: {
    clientId?: string;
    days: number;
    domain?: string;
  }): Promise<EmailHubResponse> {
    const ready = await this.schemaReady();
    const emptySummary: EmailHubSummary = {
      workspaces: 0,
      contacts: 0,
      emails_sent: 0,
      open_rate_pct: 0,
      complaint_rate_pct: 0,
      pending_approvals: 0,
      send_queue_lag_minutes: 0,
      revenue_attrib: 0,
    };
    if (!ready) {
      return {
        ok: true,
        schema_ready: false,
        summary: emptySummary,
        clients: [],
        pending_approvals: [],
        send_calendar: [],
        alerts: [
          {
            severity: 'warn',
            message: 'Schema email_mkt chưa apply — chạy ./scripts/apply_pg_ddl_email_mkt.sh',
            link: '/email/governance',
            link_label: 'Governance',
          },
        ],
        filters: {
          client_id: params.clientId ?? null,
          days: params.days,
          domain: params.domain ?? null,
        },
      };
    }

    const summaryValues: unknown[] = [params.days];
    const clientClause = params.clientId ? ` AND client_id = $2::uuid` : '';
    if (params.clientId) {
      summaryValues.push(params.clientId);
    }

    const summaryResult = await this.db.query<{
      workspaces: string;
      contacts: string;
      emails_sent: string;
      opens: string;
      complaints: string;
      pending_approvals: string;
      queue_lag_minutes: string;
    }>(
      `SELECT
         (SELECT COUNT(*) FROM ${SCHEMA}.workspaces WHERE 1=1${clientClause}) AS workspaces,
         (SELECT COUNT(*) FROM ${SCHEMA}.contacts WHERE 1=1${clientClause}) AS contacts,
         (SELECT COUNT(*) FROM ${SCHEMA}.send_queue sq
          WHERE sq.status IN ('sent', 'delivered')
            AND COALESCE(sq.sent_at, sq.scheduled_at) >= NOW() - ($1::int || ' days')::interval${clientClause.replace(/client_id/g, 'sq.client_id')}) AS emails_sent,
         (SELECT COUNT(*) FROM ${SCHEMA}.engagement_events ee
          WHERE ee.event_type = 'open'
            AND ee.occurred_at >= NOW() - ($1::int || ' days')::interval${clientClause.replace(/client_id/g, 'ee.client_id')}) AS opens,
         (SELECT COUNT(*) FROM ${SCHEMA}.engagement_events ee
          WHERE ee.event_type = 'complaint'
            AND ee.occurred_at >= NOW() - ($1::int || ' days')::interval${clientClause.replace(/client_id/g, 'ee.client_id')}) AS complaints,
         (SELECT COUNT(*) FROM ${SCHEMA}.campaigns cam
          WHERE cam.status = 'pending_approval'${clientClause.replace(/client_id/g, 'cam.client_id')}) AS pending_approvals,
         (SELECT COALESCE(
            EXTRACT(EPOCH FROM (NOW() - MIN(sq.scheduled_at))) / 60, 0
          ) FROM ${SCHEMA}.send_queue sq
          WHERE sq.status = 'processing'${clientClause.replace(/client_id/g, 'sq.client_id')}) AS queue_lag_minutes`,
      summaryValues,
    );

    const row = summaryResult.rows[0];
    const emailsSent = Number(row?.emails_sent ?? 0);
    const opens = Number(row?.opens ?? 0);
    const complaints = Number(row?.complaints ?? 0);

    const revenueValues: unknown[] = [params.days];
    let revenueClientClause = '';
    if (params.clientId) {
      revenueValues.push(params.clientId);
      revenueClientClause = '2';
    }
    const { sql: revenueSql } = revenueAttributedQuery(revenueClientClause ? 2 : undefined);
    let revenueAttrib = 0;
    try {
      const revResult = await this.db.query<{ total: string }>(revenueSql, revenueValues);
      revenueAttrib = Math.round(Number(revResult.rows[0]?.total ?? 0) * 100) / 100;
    } catch {
      revenueAttrib = 0;
    }

    const summary: EmailHubSummary = {
      workspaces: Number(row?.workspaces ?? 0),
      contacts: Number(row?.contacts ?? 0),
      emails_sent: emailsSent,
      open_rate_pct: pct(opens, emailsSent),
      complaint_rate_pct: pct(complaints, emailsSent),
      pending_approvals: Number(row?.pending_approvals ?? 0),
      send_queue_lag_minutes: Math.round(Number(row?.queue_lag_minutes ?? 0)),
      revenue_attrib: revenueAttrib,
    };

    const clientValues: unknown[] = [params.days];
    let domainJoin = '';
    let paramIdx = 2;
    if (params.domain) {
      clientValues.push(`%${params.domain.trim()}%`);
      domainJoin = ` AND d.domain ILIKE $${paramIdx++}`;
    }
    let clientWhere = '';
    if (params.clientId) {
      clientValues.push(params.clientId);
      clientWhere = ` AND w.client_id = $${paramIdx}::uuid`;
    }

    const clientsResult = await this.db.query(
      `SELECT
         c.id::text AS client_id,
         c.code AS client_code,
         c.name AS client_name,
         w.name AS workspace_name,
         d.domain AS primary_domain,
         d.spf_status,
         d.dkim_status,
         d.dmarc_status,
         (
           SELECT MAX(COALESCE(sq.sent_at, sq.scheduled_at))
           FROM ${SCHEMA}.send_queue sq
           WHERE sq.client_id = c.id
             AND sq.status IN ('sent', 'delivered')
         ) AS last_send_at,
         (
           SELECT COUNT(*) FROM ${SCHEMA}.campaigns cam
           WHERE cam.client_id = c.id AND cam.status = 'pending_approval'
         ) AS pending_campaigns,
         (
           SELECT COUNT(*)::float FROM ${SCHEMA}.engagement_events ee
           WHERE ee.client_id = c.id
             AND ee.event_type = 'complaint'
             AND ee.occurred_at >= NOW() - ($1::int || ' days')::interval
         ) AS complaints,
         (
           SELECT COUNT(*)::float FROM ${SCHEMA}.send_queue sq
           WHERE sq.client_id = c.id
             AND sq.status IN ('sent', 'delivered')
             AND COALESCE(sq.sent_at, sq.scheduled_at) >= NOW() - ($1::int || ' days')::interval
         ) AS sends
       FROM ${SCHEMA}.workspaces w
       JOIN clients c ON c.id = w.client_id
       LEFT JOIN LATERAL (
         SELECT domain, spf_status, dkim_status, dmarc_status
         FROM ${SCHEMA}.domains d
         WHERE d.client_id = c.id${domainJoin}
         ORDER BY d.created_at ASC
         LIMIT 1
       ) d ON TRUE
       WHERE 1=1${clientWhere}
       ORDER BY c.name ASC`,
      clientValues,
    );

    const clients: EmailHubClientRow[] = clientsResult.rows.map((r) => {
      const sends = Number(r.sends ?? 0);
      const complaintPct = pct(Number(r.complaints ?? 0), sends);
      return {
        client_id: String(r.client_id),
        client_code: String(r.client_code ?? ''),
        client_name: String(r.client_name ?? ''),
        workspace_name: r.workspace_name ? String(r.workspace_name) : null,
        primary_domain: r.primary_domain ? String(r.primary_domain) : null,
        domain_health: domainHealth({
          spf: r.spf_status ? String(r.spf_status) : null,
          dkim: r.dkim_status ? String(r.dkim_status) : null,
          dmarc: r.dmarc_status ? String(r.dmarc_status) : null,
          complaintPct,
        }),
        complaint_rate_pct: complaintPct,
        last_send_at: iso(r.last_send_at),
        pending_campaigns: Number(r.pending_campaigns ?? 0),
      };
    });

    const pendingValues: unknown[] = [];
    let pendingFilter = '';
    if (params.clientId) {
      pendingValues.push(params.clientId);
      pendingFilter = ` AND cam.client_id = $${pendingValues.length}::uuid`;
    }
    const pendingResult = await this.db.query(
      `SELECT cam.id::text AS campaign_id, cam.client_id::text, c.name AS client_name,
              cam.name AS campaign_name, cam.scheduled_at, cam.audience_count
       FROM ${SCHEMA}.campaigns cam
       JOIN clients c ON c.id = cam.client_id
       WHERE cam.status = 'pending_approval'${pendingFilter}
       ORDER BY cam.scheduled_at NULLS LAST, cam.created_at DESC
       LIMIT 20`,
      pendingValues,
    );
    const pending_approvals: EmailHubPendingApproval[] = pendingResult.rows.map((r) => ({
      campaign_id: String(r.campaign_id),
      client_id: String(r.client_id),
      client_name: String(r.client_name),
      campaign_name: String(r.campaign_name),
      scheduled_at: iso(r.scheduled_at),
      audience_count: r.audience_count == null ? null : Number(r.audience_count),
    }));

    const calendarValues: unknown[] = [];
    let calendarFilter = '';
    if (params.clientId) {
      calendarValues.push(params.clientId);
      calendarFilter = ` AND cam.client_id = $${calendarValues.length}::uuid`;
    }
    const calendarResult = await this.db.query(
      `SELECT cam.id::text AS campaign_id, c.name AS client_name, cam.name AS campaign_name,
              cam.scheduled_at, cam.status
       FROM ${SCHEMA}.campaigns cam
       JOIN clients c ON c.id = cam.client_id
       WHERE cam.scheduled_at IS NOT NULL
         AND cam.scheduled_at >= NOW()
         AND cam.scheduled_at < NOW() + INTERVAL '7 days'
         AND cam.status IN ('scheduled', 'approved', 'sending')${calendarFilter}
       ORDER BY cam.scheduled_at ASC
       LIMIT 20`,
      calendarValues,
    );
    const send_calendar: EmailHubSendCalendarItem[] = calendarResult.rows.map((r) => ({
      campaign_id: String(r.campaign_id),
      client_name: String(r.client_name),
      campaign_name: String(r.campaign_name),
      scheduled_at: iso(r.scheduled_at) ?? '',
      status: String(r.status),
    }));

    const alerts: EmailHubAlert[] = [];
    if (summary.workspaces === 0) {
      alerts.push({
        severity: 'info',
        message: 'Chưa có workspace email — tạo workspace khi EM-1.',
        link: '/email/governance',
        link_label: 'Governance',
      });
    }
    if (summary.complaint_rate_pct >= 0.1) {
      alerts.push({
        severity: 'danger',
        message: `Complaint rate ${summary.complaint_rate_pct}% vượt ngưỡng cảnh báo.`,
        link: '/email/governance',
        link_label: 'Xem rules',
      });
    }
    if (summary.send_queue_lag_minutes >= 5) {
      alerts.push({
        severity: 'warn',
        message: `Send queue lag ~${summary.send_queue_lag_minutes} phút.`,
        link: '/email/hub',
        link_label: 'Hub',
      });
    }
    for (const c of clients) {
      if (c.domain_health === 'at_risk' && c.primary_domain) {
        alerts.push({
          severity: 'warn',
          message: `Domain ${c.primary_domain} — deliverability at risk (${c.client_name}).`,
          link: '/email/governance',
          link_label: 'Deliverability',
        });
      }
    }
    if (summary.pending_approvals > 0) {
      alerts.push({
        severity: 'warn',
        message: `${summary.pending_approvals} chiến dịch chờ duyệt.`,
        link: '/email/hub',
        link_label: 'Xem pending',
      });
    }

    return {
      ok: true,
      schema_ready: true,
      summary,
      clients,
      pending_approvals,
      send_calendar,
      alerts,
      filters: {
        client_id: params.clientId ?? null,
        days: params.days,
        domain: params.domain ?? null,
      },
    };
  }

  async governance(params: { scope?: string }): Promise<EmailGovernanceResponse> {
    const ready = await this.schemaReady();
    if (!ready) {
      return {
        ok: true,
        read_only: true,
        schema_ready: false,
        rules: [],
        audit_log: [],
        filters: { scope: params.scope ?? null },
      };
    }

    const values: unknown[] = [];
    let scopeFilter = '';
    if (params.scope) {
      values.push(params.scope);
      scopeFilter = ` WHERE scope = $${values.length}`;
    }

    const rulesResult = await this.db.query(
      `SELECT id::text, scope, client_id::text, rule_type, config_json, priority, enabled, created_at
       FROM ${SCHEMA}.rules${scopeFilter}
       ORDER BY priority ASC, created_at ASC`,
      values,
    );
    const rules: EmailGovernanceRule[] = rulesResult.rows.map((r) => ({
      id: String(r.id),
      scope: String(r.scope),
      client_id: r.client_id ? String(r.client_id) : null,
      rule_type: String(r.rule_type),
      config_json: (r.config_json ?? {}) as Record<string, unknown>,
      priority: Number(r.priority),
      enabled: Boolean(r.enabled),
      created_at: iso(r.created_at) ?? '',
    }));

    const auditResult = await this.db.query(
      `SELECT id, client_id::text, actor, action, entity_type, entity_id::text, created_at
       FROM ${SCHEMA}.audit_log
       ORDER BY created_at DESC
       LIMIT 50`,
    );
    const audit_log: EmailGovernanceAuditRow[] = auditResult.rows.map((r) => ({
      id: Number(r.id),
      client_id: r.client_id ? String(r.client_id) : null,
      actor: String(r.actor),
      action: String(r.action),
      entity_type: String(r.entity_type),
      entity_id: r.entity_id ? String(r.entity_id) : null,
      created_at: iso(r.created_at) ?? '',
    }));

    return {
      ok: true,
      read_only: true,
      schema_ready: true,
      rules,
      audit_log,
      filters: { scope: params.scope ?? null },
    };
  }
}
