import { BadRequestException, Injectable, OnModuleDestroy } from '@nestjs/common';
import { Pool, PoolClient } from 'pg';
import { AppConfigService } from '../config/app-config.service';
import {
  PortalSeoContentDetail,
  PortalSeoContentRow,
  PortalSeoReportType,
} from './portal-seo.types';

const SCHEMA = 'seo_aeo';
const APPROVAL_STAGES = ['seo_review', 'aeo_review', 'technical_review', 'client_review'] as const;
const PORTAL_REPORT_TYPES = new Set<PortalSeoReportType>([
  'executive',
  'seo',
  'aeo',
  'technical',
  'content',
]);

const CONTENT_TRANSITIONS: Record<string, readonly string[]> = {
  idea: ['researching', 'brief_ready', 'archived'],
  researching: ['brief_ready', 'idea', 'archived'],
  brief_ready: ['in_writing', 'researching', 'archived'],
  in_writing: ['seo_review', 'brief_ready', 'archived'],
  seo_review: ['aeo_review', 'in_writing', 'archived'],
  aeo_review: ['approved', 'technical_review', 'in_writing', 'archived'],
  technical_review: ['client_review', 'approved', 'in_writing', 'archived'],
  client_review: ['approved', 'in_writing', 'archived'],
  approved: ['published', 'in_writing', 'archived'],
  published: ['monitoring', 'refresh_required', 'archived'],
  monitoring: ['refresh_required', 'archived'],
  refresh_required: ['in_writing', 'researching', 'archived'],
  archived: ['idea'],
};

function canTransition(current: string, target: string): boolean {
  return (CONTENT_TRANSITIONS[current] ?? []).includes(target);
}

function tsUtc(): string {
  return new Date().toISOString().replace('T', ' ').slice(0, 19);
}

function parseJson(raw: unknown): Record<string, unknown> {
  if (raw == null) return {};
  if (typeof raw === 'object' && !Array.isArray(raw)) return raw as Record<string, unknown>;
  try {
    return JSON.parse(String(raw)) as Record<string, unknown>;
  } catch {
    return {};
  }
}

function governanceEnabled(): boolean {
  const flag = (process.env.PTT_SEO_GOVERNANCE_ENABLED ?? '1').trim().toLowerCase();
  return !['0', 'false', 'no', 'off'].includes(flag);
}

interface GovernancePolicy {
  policy_key: string;
  name: string;
  rule_type: string;
  rule_config: Record<string, unknown>;
  severity: string;
  active: boolean;
}

interface ContentRow {
  id: number;
  customer_id: number;
  title: string;
  content_type: string;
  workflow_status: string;
  body_html: string;
  brief: Record<string, unknown>;
  outline: Record<string, unknown>;
  target_keyword_id: number | null;
}

@Injectable()
export class PortalSeoRepository implements OnModuleDestroy {
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

  async customerIdForPortalClient(clientId: string): Promise<number | null> {
    const result = await this.db.query<{ customer_id: number }>(
      `SELECT customer_id FROM ${SCHEMA}.seo_portal_client_map
       WHERE client_id = $1 AND active = TRUE`,
      [clientId.trim()],
    );
    if (!result.rows[0]) return null;
    return Number(result.rows[0].customer_id);
  }

  async buildDashboard(customerId: number, dashboardType: PortalSeoReportType): Promise<Record<string, unknown>> {
    const dtype = PORTAL_REPORT_TYPES.has(dashboardType) ? dashboardType : 'executive';
    const base: Record<string, unknown> = { type: dtype, customer_id: customerId };

    if (dtype === 'executive') {
      const [gsc, gscTrend, criticalIssues, contentByStatus, aeo, syncRuns] = await Promise.all([
        this.gscSummary(customerId, 28),
        this.gscDailyTrend(customerId, 28),
        this.countOpenCritical(customerId),
        this.countByStatus(customerId),
        this.aeoCoverage(customerId),
        this.listSyncRuns(customerId, 5),
      ]);
      return {
        ...base,
        days: 28,
        gsc,
        gsc_trend: gscTrend,
        authority: {},
        attribution: {},
        critical_issues: criticalIssues,
        content_by_status: contentByStatus,
        aeo,
        sync_runs_recent: syncRuns,
      };
    }

    if (dtype === 'seo') {
      const [gsc, trend] = await Promise.all([
        this.gscSummary(customerId, 28),
        this.gscDailyTrend(customerId, 28),
      ]);
      return { ...base, days: 28, gsc, gsc_trend: trend, attribution: {} };
    }

    if (dtype === 'content') {
      const byStatus = await this.countByStatus(customerId);
      return {
        ...base,
        content_by_status: byStatus,
        content_chart: Object.entries(byStatus).map(([label, value]) => ({ label, value })),
      };
    }

    if (dtype === 'technical') {
      const [severity, issues] = await Promise.all([
        this.severityMatrix(customerId),
        this.listOpenTechnicalIssues(customerId, 20),
      ]);
      return {
        ...base,
        severity,
        severity_chart: ['critical', 'high', 'medium', 'low'].map((label) => ({
          label,
          value: Number(severity[label] ?? 0),
        })),
        issues,
      };
    }

    if (dtype === 'aeo') {
      const aeo = await this.aeoCoverage(customerId);
      return { ...base, aeo, mentions_recent: [] };
    }

    return base;
  }

  async listPendingContent(customerId: number): Promise<PortalSeoContentRow[]> {
    const result = await this.db.query<{
      id: number;
      title: string;
      content_type: string;
      due_date: string | null;
      updated_at: string | null;
    }>(
      `SELECT id, title, content_type, due_date, updated_at
       FROM ${SCHEMA}.seo_content
       WHERE customer_id = $1 AND workflow_status = 'client_review'
       ORDER BY updated_at DESC NULLS LAST, id DESC`,
      [customerId],
    );
    return result.rows.map((row) => ({
      id: row.id,
      title: row.title,
      content_type: row.content_type,
      due_date: row.due_date,
      updated_at: row.updated_at,
    }));
  }

  async getContentDetail(customerId: number, contentId: number): Promise<PortalSeoContentDetail | null> {
    const content = await this.loadContent(contentId);
    if (!content || content.customer_id !== customerId) return null;
    const approvals = await this.approvalTimeline(contentId);
    return {
      id: content.id,
      title: content.title,
      content_type: content.content_type,
      workflow_status: content.workflow_status,
      body_html: content.body_html ?? '',
      brief: content.brief,
      approvals,
    };
  }

  async reviewContent(params: {
    customerId: number;
    contentId: number;
    approved: boolean;
    actorId: string;
    notes: string;
  }): Promise<PortalSeoContentDetail> {
    const client = await this.db.connect();
    try {
      await client.query('BEGIN');
      const content = await this.loadContent(params.contentId, client);
      if (!content || content.customer_id !== params.customerId) {
        throw new BadRequestException({ ok: false, error: 'Content không tồn tại' });
      }
      if (content.workflow_status !== 'client_review') {
        throw new BadRequestException({ ok: false, error: 'Content không ở giai đoạn client_review' });
      }
      if (params.approved) {
        const evalResult = await this.evaluateContentPublish(client, params.contentId, content, 'approve');
        if (!evalResult.ok) {
          const keys = evalResult.violations.map((v) => v.policy_key).join(', ');
          throw new BadRequestException({ ok: false, error: `Governance block: ${keys}` });
        }
      }
      const status = params.approved ? 'approved' : 'rejected';
      await this.recordApproval(client, {
        contentId: params.contentId,
        stage: 'client_review',
        status,
        actorId: params.actorId,
        notes: params.notes,
      });
      if (params.approved) {
        if (canTransition(content.workflow_status, 'approved')) {
          await client.query(
            `UPDATE ${SCHEMA}.seo_content SET workflow_status = 'approved', updated_at = $2 WHERE id = $1`,
            [params.contentId, tsUtc()],
          );
        }
      } else if (canTransition(content.workflow_status, 'in_writing')) {
        await client.query(
          `UPDATE ${SCHEMA}.seo_content SET workflow_status = 'in_writing', updated_at = $2 WHERE id = $1`,
          [params.contentId, tsUtc()],
        );
      }
      await this.logAudit(client, {
        customerId: content.customer_id,
        entityType: 'content',
        entityId: params.contentId,
        action: `approval:client_review:${status}`,
        actorId: params.actorId,
        payload: { notes: params.notes },
      });
      await client.query('COMMIT');
    } catch (err) {
      await client.query('ROLLBACK');
      throw err;
    } finally {
      client.release();
    }
    const detail = await this.getContentDetail(params.customerId, params.contentId);
    if (!detail) {
      throw new BadRequestException({ ok: false, error: 'content_not_found' });
    }
    return detail;
  }

  private async loadContent(contentId: number, client: Pool | PoolClient = this.db): Promise<ContentRow | null> {
    const result = await client.query<{
      id: number;
      customer_id: number;
      title: string;
      content_type: string;
      workflow_status: string;
      body_html: string;
      brief_json: unknown;
      outline_json: unknown;
      target_keyword_id: number | null;
    }>(`SELECT * FROM ${SCHEMA}.seo_content WHERE id = $1`, [contentId]);
    const row = result.rows[0];
    if (!row) return null;
    return {
      id: row.id,
      customer_id: Number(row.customer_id),
      title: row.title,
      content_type: row.content_type,
      workflow_status: row.workflow_status,
      body_html: row.body_html ?? '',
      brief: parseJson(row.brief_json),
      outline: parseJson(row.outline_json),
      target_keyword_id: row.target_keyword_id,
    };
  }

  private async gscSummary(customerId: number, days: number): Promise<Record<string, unknown>> {
    const result = await this.db.query<{
      clicks: string;
      impressions: string;
      queries: string;
      pages: string;
    }>(
      `SELECT
         COALESCE(SUM(clicks), 0) AS clicks,
         COALESCE(SUM(impressions), 0) AS impressions,
         COUNT(DISTINCT query) AS queries,
         COUNT(DISTINCT page) AS pages
       FROM ${SCHEMA}.seo_gsc_daily_stats
       WHERE customer_id = $1
         AND stat_date >= CURRENT_DATE - ($2::int * INTERVAL '1 day')`,
      [customerId, Math.max(1, days)],
    );
    const row = result.rows[0];
    const clicks = Number(row?.clicks ?? 0);
    const impressions = Number(row?.impressions ?? 0);
    return {
      clicks,
      impressions,
      queries: Number(row?.queries ?? 0),
      pages: Number(row?.pages ?? 0),
      avg_ctr: impressions > 0 ? Math.round((clicks / impressions) * 10000) / 10000 : 0,
    };
  }

  private async gscDailyTrend(customerId: number, days: number): Promise<Array<Record<string, unknown>>> {
    const result = await this.db.query<{
      date: string;
      clicks: string;
      impressions: string;
    }>(
      `SELECT stat_date AS date,
              COALESCE(SUM(clicks), 0) AS clicks,
              COALESCE(SUM(impressions), 0) AS impressions
       FROM ${SCHEMA}.seo_gsc_daily_stats
       WHERE customer_id = $1
         AND stat_date >= CURRENT_DATE - ($2::int * INTERVAL '1 day')
       GROUP BY stat_date
       ORDER BY stat_date ASC`,
      [customerId, Math.max(1, days)],
    );
    return result.rows.map((row) => ({
      date: String(row.date),
      clicks: Number(row.clicks ?? 0),
      impressions: Number(row.impressions ?? 0),
    }));
  }

  private async countOpenCritical(customerId: number): Promise<number> {
    const result = await this.db.query<{ c: string }>(
      `SELECT COUNT(*) AS c FROM ${SCHEMA}.seo_technical_issues
       WHERE severity = 'critical'
         AND status NOT IN ('closed', 'verified')
         AND customer_id = $1`,
      [customerId],
    );
    return Number(result.rows[0]?.c ?? 0);
  }

  private async countByStatus(customerId: number): Promise<Record<string, number>> {
    const result = await this.db.query<{ workflow_status: string; c: string }>(
      `SELECT workflow_status, COUNT(*) AS c
       FROM ${SCHEMA}.seo_content
       WHERE customer_id = $1 AND workflow_status != 'archived'
       GROUP BY workflow_status`,
      [customerId],
    );
    const out: Record<string, number> = {};
    for (const row of result.rows) {
      out[row.workflow_status] = Number(row.c);
    }
    return out;
  }

  private async aeoCoverage(customerId: number): Promise<Record<string, unknown>> {
    const result = await this.db.query<{ total: string; visible: string }>(
      `SELECT COUNT(*) AS total,
              COALESCE(SUM(CASE WHEN brand_visible THEN 1 ELSE 0 END), 0) AS visible
       FROM ${SCHEMA}.seo_questions
       WHERE customer_id = $1`,
      [customerId],
    );
    const total = Number(result.rows[0]?.total ?? 0);
    const visible = Number(result.rows[0]?.visible ?? 0);
    return {
      total,
      visible,
      coverage_pct: total > 0 ? Math.round((1000 * visible) / total) / 10 : 0,
    };
  }

  private async listSyncRuns(customerId: number, limit: number): Promise<Array<Record<string, unknown>>> {
    const result = await this.db.query<Record<string, unknown>>(
      `SELECT * FROM ${SCHEMA}.seo_sync_runs
       WHERE customer_id = $1
       ORDER BY id DESC
       LIMIT $2`,
      [customerId, limit],
    );
    return result.rows.map((row) => ({
      source: String(row.source ?? row.connector ?? ''),
      status: String(row.status ?? ''),
      finished_at: row.finished_at ?? row.created_at ?? null,
    }));
  }

  private async severityMatrix(customerId: number): Promise<Record<string, number>> {
    const result = await this.db.query<{ severity: string; c: string }>(
      `SELECT severity, COUNT(*) AS c
       FROM ${SCHEMA}.seo_technical_issues
       WHERE customer_id = $1 AND status NOT IN ('closed', 'verified')
       GROUP BY severity`,
      [customerId],
    );
    const out: Record<string, number> = { critical: 0, high: 0, medium: 0, low: 0 };
    for (const row of result.rows) {
      out[row.severity] = Number(row.c);
    }
    return out;
  }

  private async listOpenTechnicalIssues(
    customerId: number,
    limit: number,
  ): Promise<Array<Record<string, unknown>>> {
    const result = await this.db.query<{
      url: string;
      issue_type: string;
      severity: string;
      status: string;
    }>(
      `SELECT url, issue_type, severity, status
       FROM ${SCHEMA}.seo_technical_issues
       WHERE customer_id = $1 AND status NOT IN ('closed', 'verified')
       ORDER BY id DESC
       LIMIT $2`,
      [customerId, limit],
    );
    return result.rows.map((row) => ({
      url: row.url ?? '',
      issue_type: row.issue_type ?? '',
      severity: row.severity ?? '',
      status: row.status ?? '',
    }));
  }

  private async approvalTimeline(contentId: number): Promise<Array<Record<string, unknown>>> {
    const timeline: Array<Record<string, unknown>> = [];
    for (const stage of APPROVAL_STAGES) {
      const result = await this.db.query<{
        status: string;
        notes: string;
        actor_id: string;
        created_at: string | null;
      }>(
        `SELECT status, notes, actor_id, created_at
         FROM ${SCHEMA}.seo_content_approvals
         WHERE content_id = $1 AND stage = $2
         ORDER BY id DESC
         LIMIT 1`,
        [contentId, stage],
      );
      const row = result.rows[0];
      timeline.push({
        stage,
        status: row?.status ?? 'pending',
        notes: row?.notes ?? '',
        actor_id: row?.actor_id ?? '',
        created_at: row?.created_at ?? null,
      });
    }
    return timeline;
  }

  private async recordApproval(
    client: PoolClient,
    params: {
      contentId: number;
      stage: string;
      status: string;
      actorId: string;
      notes: string;
    },
  ): Promise<void> {
    await client.query(
      `INSERT INTO ${SCHEMA}.seo_content_approvals
         (content_id, stage, status, actor_id, notes, created_at)
       VALUES ($1, $2, $3, $4, $5, $6)`,
      [params.contentId, params.stage, params.status, params.actorId, params.notes, tsUtc()],
    );
  }

  private async logAudit(
    client: PoolClient,
    params: {
      customerId: number;
      entityType: string;
      entityId: number;
      action: string;
      actorId: string;
      payload: Record<string, unknown>;
    },
  ): Promise<void> {
    await client.query(
      `INSERT INTO ${SCHEMA}.seo_audit_log
         (customer_id, entity_type, entity_id, action, actor_id, payload_json, created_at)
       VALUES ($1, $2, $3, $4, $5, $6, $7)`,
      [
        params.customerId,
        params.entityType,
        params.entityId,
        params.action,
        params.actorId,
        JSON.stringify(params.payload),
        tsUtc(),
      ],
    );
  }

  private async evaluateContentPublish(
    client: PoolClient,
    contentId: number,
    content: ContentRow,
    action: string,
  ): Promise<{ ok: boolean; violations: Array<{ policy_key: string }> }> {
    if (!governanceEnabled()) {
      return { ok: true, violations: [] };
    }
    const policies = await this.listPolicies(client, content.customer_id);
    const overrides = await this.listContentOverrideKeys(client, contentId);
    const violations: Array<{ policy_key: string; name: string; severity: string; details: string[] }> = [];
    for (const policy of policies) {
      if (!policy.active || overrides.has(policy.policy_key)) continue;
      const hit = await this.evaluatePolicy(client, policy, content, contentId);
      if (hit && hit.severity === 'block') violations.push(hit);
    }
    const passed = violations.length === 0;
    await client.query(
      `INSERT INTO ${SCHEMA}.seo_governance_evaluations
         (customer_id, entity_type, entity_id, action, passed, violations_json, evaluated_at)
       VALUES ($1, 'content', $2, $3, $4, $5, $6)`,
      [content.customer_id, contentId, action, passed, JSON.stringify(violations), tsUtc()],
    );
    return { ok: passed, violations };
  }

  private async listPolicies(client: PoolClient, customerId: number): Promise<GovernancePolicy[]> {
    await this.seedDefaultPolicies(client, null);
    await this.seedDefaultPolicies(client, customerId);
    const result = await client.query<{
      policy_key: string;
      name: string;
      rule_type: string;
      rule_config: unknown;
      severity: string;
      active: boolean;
      customer_id: number | null;
    }>(
      `SELECT policy_key, name, rule_type, rule_config, severity, active, customer_id
       FROM ${SCHEMA}.seo_governance_policies
       WHERE customer_id IS NULL OR customer_id = $1
       ORDER BY CASE WHEN customer_id IS NULL THEN 1 ELSE 0 END, policy_key`,
      [customerId],
    );
    const seen = new Set<string>();
    const out: GovernancePolicy[] = [];
    for (const row of result.rows) {
      if (seen.has(row.policy_key)) continue;
      seen.add(row.policy_key);
      out.push({
        policy_key: row.policy_key,
        name: row.name,
        rule_type: row.rule_type,
        rule_config: parseJson(row.rule_config),
        severity: row.severity,
        active: Boolean(row.active),
      });
    }
    return out;
  }

  private async seedDefaultPolicies(client: PoolClient, customerId: number | null): Promise<void> {
    const defaults = [
      {
        policy_key: 'metadata_required',
        name: 'Metadata bắt buộc',
        description: 'Title, keyword/topic, meta title & description trong brief',
        rule_type: 'required_fields',
        rule_config: { fields: ['title', 'target_keyword', 'meta_title', 'meta_description'] },
        severity: 'block',
      },
      {
        policy_key: 'qa_complete',
        name: 'QA stages hoàn tất',
        description: 'SEO, AEO, Technical review đã approved',
        rule_type: 'approval_complete',
        rule_config: { stages: ['seo_review', 'aeo_review', 'technical_review'] },
        severity: 'block',
      },
      {
        policy_key: 'no_critical_technical',
        name: 'Không issue critical mở',
        description: 'Zero critical technical issues cho client',
        rule_type: 'technical_critical',
        rule_config: { max_open: 0 },
        severity: 'block',
      },
      {
        policy_key: 'schema_valid',
        name: 'Schema checklist',
        description: 'Brief checklist có mục schema',
        rule_type: 'schema_valid',
        rule_config: { require_schema_checklist: true },
        severity: 'block',
      },
    ];
    for (const pol of defaults) {
      const existing = await client.query<{ id: number }>(
        `SELECT id FROM ${SCHEMA}.seo_governance_policies
         WHERE policy_key = $1 AND customer_id IS NOT DISTINCT FROM $2`,
        [pol.policy_key, customerId],
      );
      if (existing.rows[0]) continue;
      await client.query(
        `INSERT INTO ${SCHEMA}.seo_governance_policies
           (customer_id, policy_key, name, description, rule_type, rule_config, severity, active, created_at, updated_at)
         VALUES ($1, $2, $3, $4, $5, $6, $7, TRUE, $8, $8)`,
        [
          customerId,
          pol.policy_key,
          pol.name,
          pol.description,
          pol.rule_type,
          JSON.stringify(pol.rule_config),
          pol.severity,
          tsUtc(),
        ],
      );
    }
  }

  private async listContentOverrideKeys(client: PoolClient, contentId: number): Promise<Set<string>> {
    const result = await client.query<{ policy_key: string }>(
      `SELECT DISTINCT o.policy_key
       FROM ${SCHEMA}.seo_governance_overrides o
       INNER JOIN ${SCHEMA}.seo_governance_evaluations e ON e.id = o.evaluation_id
       WHERE e.entity_type = 'content' AND e.entity_id = $1`,
      [contentId],
    );
    return new Set(result.rows.map((row) => row.policy_key));
  }

  private fieldValue(content: ContentRow, field: string): unknown {
    if (field === 'title') return (content.title ?? '').trim();
    if (field === 'target_keyword') {
      if (content.target_keyword_id) return true;
      const brief = content.brief ?? {};
      return String(brief.primary_topic ?? '').trim();
    }
    const brief = content.brief ?? {};
    if (field === 'meta_title') return String(brief.meta_title ?? '').trim();
    if (field === 'meta_description') return String(brief.meta_description ?? '').trim();
    return undefined;
  }

  private async evaluatePolicy(
    client: PoolClient,
    policy: GovernancePolicy,
    content: ContentRow,
    contentId: number,
  ): Promise<{ policy_key: string; name: string; severity: string; details: string[] } | null> {
    const config = policy.rule_config ?? {};
    let details: string[] = [];
    if (policy.rule_type === 'required_fields') {
      for (const field of (config.fields as string[] | undefined) ?? []) {
        if (!this.fieldValue(content, field)) details.push(field);
      }
    } else if (policy.rule_type === 'approval_complete') {
      const timeline = await this.approvalTimeline(contentId);
      const byStage = Object.fromEntries(timeline.map((t) => [t.stage, t.status]));
      for (const stage of (config.stages as string[] | undefined) ?? []) {
        if (byStage[stage] !== 'approved') details.push(stage);
      }
    } else if (policy.rule_type === 'technical_critical') {
      const maxOpen = Number(config.max_open ?? 0);
      const openCount = await this.countOpenCritical(content.customer_id);
      if (openCount > maxOpen) details.push(`critical_open:${openCount}`);
    } else if (policy.rule_type === 'schema_valid') {
      if (config.require_schema_checklist !== false) {
        const checklist = (content.brief?.checklist as unknown[] | undefined) ?? [];
        const hasSchemaItem = checklist.some((item) => String(item).toLowerCase().includes('schema'));
        const outline = content.outline ?? {};
        if (!hasSchemaItem && !outline.schema && !outline.schema_json) {
          details.push('schema_checklist_missing');
        }
      }
    }
    if (details.length === 0) return null;
    return {
      policy_key: policy.policy_key,
      name: policy.name || policy.policy_key,
      severity: policy.severity || 'block',
      details,
    };
  }
}
