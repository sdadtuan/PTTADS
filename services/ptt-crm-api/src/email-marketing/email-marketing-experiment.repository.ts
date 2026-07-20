import {
  BadRequestException,
  Injectable,
  NotFoundException,
  OnModuleDestroy,
} from '@nestjs/common';
import { Pool } from 'pg';
import { AppConfigService } from '../config/app-config.service';
import {
  EmailExperimentDecisionRow,
  EmailExperimentObservationRow,
  EmailExperimentRow,
  EmailExperimentVariantRow,
  EmailListResponse,
} from './email-marketing.types';
import { clampLimit, clampOffset, iso } from './email-marketing.util';

const SCHEMA = 'email_mkt';

type VariantInput = {
  variant_key: string;
  label: string;
  subject?: string;
  split_pct?: number;
};

@Injectable()
export class EmailMarketingExperimentRepository implements OnModuleDestroy {
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

  static pagination(limit?: number, offset?: number) {
    return { limit: clampLimit(limit), offset: clampOffset(offset) };
  }

  private async audit(params: {
    clientId: string;
    actor: string;
    action: string;
    entityType: string;
    entityId: string;
    after?: Record<string, unknown>;
  }): Promise<void> {
    await this.db.query(
      `INSERT INTO ${SCHEMA}.audit_log (client_id, actor, action, entity_type, entity_id, after_json)
       VALUES ($1::uuid, $2, $3, $4, $5::uuid, $6::jsonb)`,
      [
        params.clientId,
        params.actor,
        params.action,
        params.entityType,
        params.entityId,
        JSON.stringify(params.after ?? {}),
      ],
    );
  }

  async listExperiments(params: {
    clientId?: string;
    campaignId?: string;
    status?: string;
    limit: number;
    offset: number;
  }): Promise<EmailListResponse<EmailExperimentRow>> {
    const values: unknown[] = [];
    const clauses: string[] = ['1=1'];
    let idx = 1;
    if (params.clientId) {
      clauses.push(`e.client_id = $${idx++}::uuid`);
      values.push(params.clientId);
    }
    if (params.campaignId) {
      clauses.push(`e.campaign_id = $${idx++}::uuid`);
      values.push(params.campaignId);
    }
    if (params.status) {
      clauses.push(`e.status = $${idx++}`);
      values.push(params.status);
    }
    const where = clauses.join(' AND ');
    const count = await this.db.query<{ c: string }>(
      `SELECT COUNT(*) AS c FROM ${SCHEMA}.experiments e WHERE ${where}`,
      values,
    );
    values.push(params.limit, params.offset);
    const result = await this.db.query(
      `SELECT e.id, e.client_id, cl.name AS client_name, e.campaign_id, cam.name AS campaign_name,
              e.name, e.experiment_type, e.hypothesis, e.status, e.winner_variant_key,
              e.config_json, e.started_at, e.ended_at, e.created_by, e.created_at, e.updated_at
       FROM ${SCHEMA}.experiments e
       JOIN clients cl ON cl.id = e.client_id
       LEFT JOIN ${SCHEMA}.campaigns cam ON cam.id = e.campaign_id
       WHERE ${where}
       ORDER BY e.updated_at DESC
       LIMIT $${idx++} OFFSET $${idx}`,
      values,
    );
    return {
      ok: true,
      items: result.rows.map((r) => this.mapExperiment(r)),
      total: Number(count.rows[0]?.c ?? 0),
      limit: params.limit,
      offset: params.offset,
    };
  }

  async getExperiment(id: string): Promise<EmailExperimentRow | null> {
    const result = await this.db.query(
      `SELECT e.id, e.client_id, cl.name AS client_name, e.campaign_id, cam.name AS campaign_name,
              e.name, e.experiment_type, e.hypothesis, e.status, e.winner_variant_key,
              e.config_json, e.started_at, e.ended_at, e.created_by, e.created_at, e.updated_at
       FROM ${SCHEMA}.experiments e
       JOIN clients cl ON cl.id = e.client_id
       LEFT JOIN ${SCHEMA}.campaigns cam ON cam.id = e.campaign_id
       WHERE e.id = $1::uuid`,
      [id],
    );
    if (!result.rowCount) return null;
    const row = this.mapExperiment(result.rows[0]);
    row.variants = await this.listVariants(id);
    row.observations = await this.listObservations(id);
    row.decisions = await this.listDecisions(id);
    return row;
  }

  async getRunningExperimentForCampaign(campaignId: string): Promise<EmailExperimentRow | null> {
    const result = await this.db.query(
      `SELECT e.id FROM ${SCHEMA}.experiments e
       WHERE e.campaign_id = $1::uuid AND e.status = 'running'
       ORDER BY e.started_at DESC NULLS LAST
       LIMIT 1`,
      [campaignId],
    );
    if (!result.rowCount) return null;
    return this.getExperiment(String(result.rows[0].id));
  }

  async createExperiment(params: {
    clientId: string;
    campaignId: string;
    name: string;
    hypothesis?: string;
    experimentType?: string;
    winnerMetric?: string;
    minSample?: number;
    variants: VariantInput[];
    actor: string;
  }): Promise<EmailExperimentRow> {
    if (!params.variants.length) {
      throw new BadRequestException({ error: 'variants_required' });
    }
    const config = {
      winner_metric: params.winnerMetric?.trim() || 'open_rate',
      min_sample: params.minSample ?? 100,
    };
    const result = await this.db.query<{ id: string }>(
      `INSERT INTO ${SCHEMA}.experiments (
         client_id, campaign_id, name, experiment_type, hypothesis, config_json, created_by, status
       ) VALUES ($1::uuid, $2::uuid, $3, $4, $5, $6::jsonb, $7, 'draft')
       RETURNING id::text`,
      [
        params.clientId,
        params.campaignId,
        params.name.trim(),
        params.experimentType?.trim() || 'subject',
        params.hypothesis?.trim() || null,
        JSON.stringify(config),
        params.actor,
      ],
    );
    const id = String(result.rows[0].id);
    for (const variant of params.variants) {
      await this.db.query(
        `INSERT INTO ${SCHEMA}.experiment_variants (experiment_id, variant_key, label, config_json, split_pct)
         VALUES ($1::uuid, $2, $3, $4::jsonb, $5)`,
        [
          id,
          variant.variant_key.trim(),
          variant.label.trim(),
          JSON.stringify({ subject: variant.subject?.trim() || '' }),
          variant.split_pct ?? 50,
        ],
      );
    }
    await this.audit({
      clientId: params.clientId,
      actor: params.actor,
      action: 'experiment_created',
      entityType: 'experiment',
      entityId: id,
    });
    const row = await this.getExperiment(id);
    if (!row) throw new NotFoundException({ error: 'experiment_not_found' });
    return row;
  }

  async startExperiment(id: string, actor: string): Promise<EmailExperimentRow> {
    const existing = await this.getExperiment(id);
    if (!existing) throw new NotFoundException({ error: 'experiment_not_found' });
    if (existing.status !== 'draft' && existing.status !== 'running') {
      throw new BadRequestException({ error: 'invalid_status', status: existing.status });
    }
    await this.db.query(
      `UPDATE ${SCHEMA}.experiments
       SET status = 'running', started_at = COALESCE(started_at, NOW()), updated_at = NOW()
       WHERE id = $1::uuid`,
      [id],
    );
    if (existing.campaign_id) {
      await this.db.query(
        `UPDATE ${SCHEMA}.campaigns
         SET experiment_config = jsonb_set(COALESCE(experiment_config, '{}'::jsonb), '{enabled}', 'true'::jsonb, true),
             updated_at = NOW()
         WHERE id = $1::uuid`,
        [existing.campaign_id],
      );
    }
    await this.audit({
      clientId: existing.client_id,
      actor,
      action: 'experiment_started',
      entityType: 'experiment',
      entityId: id,
    });
    const row = await this.getExperiment(id);
    if (!row) throw new NotFoundException({ error: 'experiment_not_found' });
    return row;
  }

  async declareWinner(id: string, variantKey: string, actor: string, rationale?: string): Promise<EmailExperimentRow> {
    const existing = await this.getExperiment(id);
    if (!existing) throw new NotFoundException({ error: 'experiment_not_found' });
    const result = await this.db.query(
      `UPDATE ${SCHEMA}.experiments
       SET status = 'completed', winner_variant_key = $2, ended_at = NOW(), updated_at = NOW()
       WHERE id = $1::uuid AND status = 'running'`,
      [id, variantKey.trim()],
    );
    if (!result.rowCount) {
      throw new BadRequestException({ error: 'invalid_status_or_not_found' });
    }
    await this.db.query(
      `INSERT INTO ${SCHEMA}.experiment_decisions (experiment_id, decision, rationale, decided_by)
       VALUES ($1::uuid, $2, $3, $4)`,
      [id, `winner:${variantKey.trim()}`, rationale?.trim() || '', actor],
    );
    await this.audit({
      clientId: existing.client_id,
      actor,
      action: 'experiment_winner_declared',
      entityType: 'experiment',
      entityId: id,
      after: { winner_variant_key: variantKey },
    });
    const row = await this.getExperiment(id);
    if (!row) throw new NotFoundException({ error: 'experiment_not_found' });
    return row;
  }

  private async listVariants(experimentId: string): Promise<EmailExperimentVariantRow[]> {
    const result = await this.db.query(
      `SELECT id, experiment_id, variant_key, label, config_json, split_pct, created_at
       FROM ${SCHEMA}.experiment_variants
       WHERE experiment_id = $1::uuid
       ORDER BY variant_key ASC`,
      [experimentId],
    );
    return result.rows.map((r) => ({
      id: String(r.id),
      experiment_id: String(r.experiment_id),
      variant_key: String(r.variant_key),
      label: String(r.label),
      config_json: (r.config_json ?? {}) as Record<string, unknown>,
      split_pct: Number(r.split_pct ?? 0),
      created_at: iso(r.created_at) ?? '',
    }));
  }

  private async listObservations(experimentId: string): Promise<EmailExperimentObservationRow[]> {
    const result = await this.db.query(
      `SELECT id, experiment_id, variant_key, metric_name, metric_value, sample_size, observed_at, source
       FROM ${SCHEMA}.experiment_observations
       WHERE experiment_id = $1::uuid
       ORDER BY observed_at DESC
       LIMIT 100`,
      [experimentId],
    );
    return result.rows.map((r) => ({
      id: String(r.id),
      experiment_id: String(r.experiment_id),
      variant_key: String(r.variant_key),
      metric_name: String(r.metric_name),
      metric_value: Number(r.metric_value ?? 0),
      sample_size: Number(r.sample_size ?? 0),
      observed_at: iso(r.observed_at) ?? '',
      source: String(r.source ?? 'rollup'),
    }));
  }

  private async listDecisions(experimentId: string): Promise<EmailExperimentDecisionRow[]> {
    const result = await this.db.query(
      `SELECT id, experiment_id, decision, rationale, decided_by, decided_at
       FROM ${SCHEMA}.experiment_decisions
       WHERE experiment_id = $1::uuid
       ORDER BY decided_at DESC`,
      [experimentId],
    );
    return result.rows.map((r) => ({
      id: String(r.id),
      experiment_id: String(r.experiment_id),
      decision: String(r.decision),
      rationale: r.rationale ? String(r.rationale) : null,
      decided_by: r.decided_by ? String(r.decided_by) : null,
      decided_at: iso(r.decided_at) ?? '',
    }));
  }

  private mapExperiment(r: Record<string, unknown>): EmailExperimentRow {
    return {
      id: String(r.id),
      client_id: String(r.client_id),
      client_name: String(r.client_name ?? ''),
      campaign_id: r.campaign_id ? String(r.campaign_id) : null,
      campaign_name: r.campaign_name ? String(r.campaign_name) : null,
      name: String(r.name ?? ''),
      experiment_type: String(r.experiment_type ?? 'subject'),
      hypothesis: r.hypothesis ? String(r.hypothesis) : null,
      status: String(r.status ?? 'draft'),
      winner_variant_key: r.winner_variant_key ? String(r.winner_variant_key) : null,
      config_json: (r.config_json ?? {}) as Record<string, unknown>,
      started_at: iso(r.started_at),
      ended_at: iso(r.ended_at),
      created_by: r.created_by ? String(r.created_by) : null,
      created_at: iso(r.created_at) ?? '',
      updated_at: iso(r.updated_at) ?? '',
      variants: [],
      observations: [],
      decisions: [],
    };
  }
}
