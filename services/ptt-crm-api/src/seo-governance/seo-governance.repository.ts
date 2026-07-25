import {
  BadRequestException,
  ForbiddenException,
  Injectable,
  NotFoundException,
  OnModuleDestroy,
} from '@nestjs/common';
import { Pool } from 'pg';
import { AppConfigService } from '../config/app-config.service';
import { APPROVAL_STAGES } from '../seo-content/seo-content.constants';
import {
  DEFAULT_POLICIES,
  SEO_GOV_SCHEMA,
  governanceEnabled,
} from './seo-governance.constants';
import {
  SeoGovernanceComplianceSummary,
  SeoGovernanceEvaluateResult,
  SeoGovernancePolicyRow,
  SeoGovernanceViolation,
} from './seo-governance.types';

const SCHEMA = SEO_GOV_SCHEMA;

function tsUtc(): string {
  return new Date().toISOString().replace('T', ' ').slice(0, 19);
}

function parseJson(raw: unknown): Record<string, unknown> {
  if (raw && typeof raw === 'object' && !Array.isArray(raw)) return raw as Record<string, unknown>;
  if (raw == null) return {};
  try {
    return JSON.parse(String(raw)) as Record<string, unknown>;
  } catch {
    return {};
  }
}

@Injectable()
export class SeoGovernanceRepository implements OnModuleDestroy {
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

  async seedDefaultPolicies(customerId?: number | null): Promise<void> {
    for (const pol of DEFAULT_POLICIES) {
      const existing = await this.db.query(
        `SELECT id FROM ${SCHEMA}.seo_governance_policies
         WHERE policy_key = $1 AND customer_id IS NOT DISTINCT FROM $2`,
        [pol.policy_key, customerId ?? null],
      );
      if (existing.rows[0]) continue;
      await this.db.query(
        `INSERT INTO ${SCHEMA}.seo_governance_policies (
           customer_id, policy_key, name, description, rule_type, rule_config, severity, active, created_at, updated_at
         ) VALUES ($1,$2,$3,$4,$5,$6,$7,true,NOW(),NOW())`,
        [
          customerId ?? null,
          pol.policy_key,
          pol.name,
          pol.description,
          pol.rule_type,
          JSON.stringify(pol.rule_config),
          pol.severity,
        ],
      );
    }
  }

  async listPolicies(customerId?: number | null): Promise<SeoGovernancePolicyRow[]> {
    await this.seedDefaultPolicies(null);
    if (customerId != null) await this.seedDefaultPolicies(customerId);
    const values: unknown[] = [];
    let sql = `SELECT * FROM ${SCHEMA}.seo_governance_policies`;
    if (customerId != null) {
      values.push(customerId);
      sql += ` WHERE customer_id IS NULL OR customer_id = $${values.length}`;
    } else {
      sql += ' WHERE customer_id IS NULL';
    }
    sql += ' ORDER BY policy_key ASC';
    const result = await this.db.query(sql, values);
    const seen = new Set<string>();
    const out: SeoGovernancePolicyRow[] = [];
    for (const row of result.rows) {
      const key = String(row.policy_key);
      if (seen.has(key)) continue;
      seen.add(key);
      out.push({
        id: Number(row.id),
        customer_id: row.customer_id != null ? Number(row.customer_id) : null,
        policy_key: key,
        name: String(row.name ?? ''),
        description: String(row.description ?? ''),
        rule_type: String(row.rule_type ?? ''),
        rule_config: parseJson(row.rule_config),
        severity: String(row.severity ?? 'block'),
        active: Boolean(row.active),
        created_at: row.created_at != null ? String(row.created_at) : null,
        updated_at: row.updated_at != null ? String(row.updated_at) : null,
      });
    }
    return out;
  }

  async upsertPolicy(payload: Record<string, unknown>): Promise<SeoGovernancePolicyRow> {
    const policyKey = String(payload.policy_key ?? '').trim();
    if (!policyKey) throw new BadRequestException({ error: 'missing_policy_key' });
    const customerId = payload.customer_id ?? null;
    const existing = await this.db.query(
      `SELECT id FROM ${SCHEMA}.seo_governance_policies
       WHERE policy_key = $1 AND customer_id IS NOT DISTINCT FROM $2`,
      [policyKey, customerId],
    );
    const cfg = JSON.stringify(payload.rule_config ?? {});
    if (existing.rows[0]) {
      await this.db.query(
        `UPDATE ${SCHEMA}.seo_governance_policies SET
           name = $2, description = $3, rule_type = $4, rule_config = $5, severity = $6, active = $7, updated_at = NOW()
         WHERE id = $1`,
        [
          existing.rows[0].id,
          String(payload.name ?? policyKey),
          String(payload.description ?? ''),
          String(payload.rule_type ?? 'custom'),
          cfg,
          String(payload.severity ?? 'block'),
          payload.active !== false,
        ],
      );
    } else {
      await this.db.query(
        `INSERT INTO ${SCHEMA}.seo_governance_policies (
           customer_id, policy_key, name, description, rule_type, rule_config, severity, active, created_at, updated_at
         ) VALUES ($1,$2,$3,$4,$5,$6,$7,$8,NOW(),NOW())`,
        [
          customerId,
          policyKey,
          String(payload.name ?? policyKey),
          String(payload.description ?? ''),
          String(payload.rule_type ?? 'custom'),
          cfg,
          String(payload.severity ?? 'block'),
          payload.active !== false,
        ],
      );
    }
    const policies = await this.listPolicies(customerId != null ? Number(customerId) : null);
    const found = policies.find((p) => p.policy_key === policyKey);
    if (!found) throw new BadRequestException({ error: 'upsert_failed' });
    return found;
  }

  private async getContentForEval(contentId: number) {
    const result = await this.db.query(`SELECT * FROM ${SCHEMA}.seo_content WHERE id = $1`, [contentId]);
    const row = result.rows[0];
    if (!row) return null;
    const brief = parseJson(row.brief_json);
    const outline = parseJson(row.outline_json);
    return {
      id: Number(row.id),
      customer_id: Number(row.customer_id),
      title: String(row.title ?? ''),
      target_keyword_id: row.target_keyword_id != null ? Number(row.target_keyword_id) : null,
      brief,
      outline,
    };
  }

  private async approvalMap(contentId: number): Promise<Record<string, string>> {
    const map: Record<string, string> = {};
    for (const stage of APPROVAL_STAGES) {
      const result = await this.db.query(
        `SELECT status FROM ${SCHEMA}.seo_content_approvals
         WHERE content_id = $1 AND stage = $2 ORDER BY id DESC LIMIT 1`,
        [contentId, stage],
      );
      map[stage] = result.rows[0]?.status != null ? String(result.rows[0].status) : 'pending';
    }
    return map;
  }

  private fieldValue(content: Record<string, unknown>, field: string): unknown {
    if (field === 'title') return String(content.title ?? '').trim();
    if (field === 'target_keyword') {
      if (content.target_keyword_id) return true;
      const brief = (content.brief ?? {}) as Record<string, unknown>;
      return String(brief.primary_topic ?? '').trim();
    }
    const brief = (content.brief ?? {}) as Record<string, unknown>;
    if (field === 'meta_title') return String(brief.meta_title ?? '').trim();
    if (field === 'meta_description') return String(brief.meta_description ?? '').trim();
    return content[field];
  }

  private async evaluatePolicy(
    policy: SeoGovernancePolicyRow,
    content: Record<string, unknown>,
    contentId: number,
    customerId: number,
  ): Promise<SeoGovernanceViolation | null> {
    const config = policy.rule_config ?? {};
    let details: string[] = [];
    if (policy.rule_type === 'required_fields') {
      for (const field of (config.fields as string[]) ?? []) {
        if (!this.fieldValue(content, field)) details.push(field);
      }
    } else if (policy.rule_type === 'approval_complete') {
      const timeline = await this.approvalMap(contentId);
      details = ((config.stages as string[]) ?? []).filter((s) => timeline[s] !== 'approved');
    } else if (policy.rule_type === 'technical_critical') {
      const maxOpen = Number(config.max_open ?? 0);
      const result = await this.db.query(
        `SELECT COUNT(*) AS c FROM ${SCHEMA}.seo_technical_issues
         WHERE customer_id = $1 AND severity = 'critical' AND status NOT IN ('closed','verified')`,
        [customerId],
      );
      const open = Number(result.rows[0]?.c ?? 0);
      if (open > maxOpen) details = [`critical_open:${open}`];
    } else if (policy.rule_type === 'schema_valid') {
      const brief = (content.brief ?? {}) as Record<string, unknown>;
      const checklist = Array.isArray(brief.checklist) ? brief.checklist : [];
      const hasSchemaItem = checklist.some((item) => String(item).toLowerCase().includes('schema'));
      const outline = (content.outline ?? {}) as Record<string, unknown>;
      if (!hasSchemaItem && !outline.schema && !outline.schema_json) {
        details = ['schema_checklist_missing'];
      }
    }
    if (!details.length) return null;
    return {
      policy_key: policy.policy_key,
      name: policy.name,
      severity: policy.severity,
      details,
    };
  }

  async evaluateContentPublish(contentId: number, action = 'publish'): Promise<SeoGovernanceEvaluateResult> {
    if (!governanceEnabled()) {
      return { ok: true, violations: [], evaluation_id: null };
    }
    const content = await this.getContentForEval(contentId);
    if (!content) throw new NotFoundException({ error: 'content_not_found' });
    const policies = (await this.listPolicies(content.customer_id)).filter((p) => p.active);
    const overrideKeys = await this.listContentOverrideKeys(contentId);
    const violations: SeoGovernanceViolation[] = [];
    for (const policy of policies) {
      if (overrideKeys.has(policy.policy_key)) continue;
      const hit = await this.evaluatePolicy(policy, content, contentId, content.customer_id);
      if (hit && hit.severity === 'block') violations.push(hit);
    }
    const passed = violations.length === 0;
    const result = await this.db.query<{ id: string }>(
      `INSERT INTO ${SCHEMA}.seo_governance_evaluations (
         customer_id, entity_type, entity_id, action, passed, violations_json, evaluated_at
       ) VALUES ($1,'content',$2,$3,$4,$5,NOW()) RETURNING id`,
      [content.customer_id, contentId, action, passed, JSON.stringify(violations)],
    );
    return {
      ok: passed,
      violations,
      evaluation_id: Number(result.rows[0].id),
    };
  }

  async assertPublishAllowed(contentId: number, action = 'publish'): Promise<void> {
    const result = await this.evaluateContentPublish(contentId, action);
    if (!result.ok) {
      throw new ForbiddenException({
        error: 'governance_block',
        violations: result.violations,
        evaluation_id: result.evaluation_id,
      });
    }
  }

  private async listContentOverrideKeys(contentId: number): Promise<Set<string>> {
    const result = await this.db.query(
      `SELECT DISTINCT o.policy_key
       FROM ${SCHEMA}.seo_governance_overrides o
       INNER JOIN ${SCHEMA}.seo_governance_evaluations e ON e.id = o.evaluation_id
       WHERE e.entity_type = 'content' AND e.entity_id = $1`,
      [contentId],
    );
    return new Set(result.rows.map((r) => String(r.policy_key)));
  }

  async recordOverride(params: {
    evaluationId: number;
    policyKey: string;
    actorId: string;
    reason: string;
  }): Promise<{ ok: boolean; override_id: number }> {
    const result = await this.db.query<{ id: string }>(
      `INSERT INTO ${SCHEMA}.seo_governance_overrides (evaluation_id, policy_key, actor_id, reason, created_at)
       VALUES ($1,$2,$3,$4,NOW()) RETURNING id`,
      [params.evaluationId, params.policyKey, params.actorId, params.reason],
    );
    return { ok: true, override_id: Number(result.rows[0].id) };
  }

  async complianceSummary(customerId: number | null, days = 7): Promise<SeoGovernanceComplianceSummary> {
    const values: unknown[] = [days];
    let sql = `SELECT COUNT(*) AS total,
                      SUM(CASE WHEN passed THEN 1 ELSE 0 END) AS passed
               FROM ${SCHEMA}.seo_governance_evaluations
               WHERE evaluated_at >= NOW() - ($1::int || ' days')::interval`;
    if (customerId != null) {
      values.push(customerId);
      sql += ` AND customer_id = $${values.length}`;
    }
    const result = await this.db.query(sql, values);
    const total = Number(result.rows[0]?.total ?? 0);
    const passed = Number(result.rows[0]?.passed ?? 0);
    const failed = total - passed;
    return {
      customer_id: customerId,
      days,
      evaluations: total,
      passed,
      failed,
      pass_rate_pct: total ? Math.round((1000 * passed) / total) / 10 : 100,
    };
  }
}
