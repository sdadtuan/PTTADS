import { BadRequestException, Injectable, NotFoundException, OnModuleDestroy } from '@nestjs/common';
import { Pool } from 'pg';
import { AppConfigService } from '../config/app-config.service';
import {
  experimentsEnabled,
  SEO_EXPERIMENTS_SCHEMA,
  STATUS_TRANSITIONS,
} from './seo-experiments.constants';
import { SeoExperimentObservationRow, SeoExperimentRow } from './seo-experiments.types';

const SCHEMA = SEO_EXPERIMENTS_SCHEMA;

@Injectable()
export class SeoExperimentsRepository implements OnModuleDestroy {
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

  assertEnabled(): void {
    if (!experimentsEnabled()) {
      throw new NotFoundException({ error: 'experiments_disabled', flag: 'PTT_SEO_EXPERIMENTS_ENABLED' });
    }
  }

  private mapExperiment(row: Record<string, unknown>): SeoExperimentRow {
    return {
      id: Number(row.id),
      customer_id: Number(row.customer_id),
      title: String(row.title ?? ''),
      hypothesis: String(row.hypothesis ?? ''),
      experiment_type: String(row.experiment_type ?? 'content'),
      target_url: String(row.target_url ?? ''),
      content_id: row.content_id != null ? Number(row.content_id) : null,
      status: String(row.status ?? 'draft'),
      started_at: row.started_at != null ? String(row.started_at) : null,
      ended_at: row.ended_at != null ? String(row.ended_at) : null,
      owner_id: String(row.owner_id ?? ''),
      created_at: row.created_at != null ? String(row.created_at) : null,
      updated_at: row.updated_at != null ? String(row.updated_at) : null,
    };
  }

  async listExperiments(customerId: number): Promise<SeoExperimentRow[]> {
    this.assertEnabled();
    const result = await this.db.query(
      `SELECT * FROM ${SCHEMA}.seo_experiments
       WHERE customer_id = $1 AND status != 'archived'
       ORDER BY updated_at DESC, id DESC`,
      [customerId],
    );
    return result.rows.map((r) => this.mapExperiment(r));
  }

  async getExperiment(experimentId: number): Promise<SeoExperimentRow | null> {
    this.assertEnabled();
    const result = await this.db.query(`SELECT * FROM ${SCHEMA}.seo_experiments WHERE id = $1`, [
      experimentId,
    ]);
    const row = result.rows[0];
    return row ? this.mapExperiment(row) : null;
  }

  async createExperiment(customerId: number, body: Record<string, unknown>): Promise<SeoExperimentRow> {
    this.assertEnabled();
    const title = String(body.title ?? '').trim();
    if (!title) throw new BadRequestException({ error: 'missing_title' });
    const result = await this.db.query(
      `INSERT INTO ${SCHEMA}.seo_experiments (
         customer_id, title, hypothesis, experiment_type, target_url, content_id, status, owner_id
       ) VALUES ($1,$2,$3,$4,$5,$6,'draft',$7)
       RETURNING *`,
      [
        customerId,
        title,
        String(body.hypothesis ?? ''),
        String(body.experiment_type ?? 'content'),
        String(body.target_url ?? ''),
        body.content_id != null ? Number(body.content_id) : null,
        String(body.owner_id ?? ''),
      ],
    );
    const exp = this.mapExperiment(result.rows[0]);
    await this.db.query(
      `INSERT INTO ${SCHEMA}.seo_experiment_variants (experiment_id, variant_key, label)
       VALUES ($1, 'control', 'Control'), ($1, 'variant_a', 'Variant A')
       ON CONFLICT (experiment_id, variant_key) DO NOTHING`,
      [exp.id],
    );
    return exp;
  }

  async updateStatus(experimentId: number, nextStatus: string): Promise<SeoExperimentRow> {
    this.assertEnabled();
    const current = await this.getExperiment(experimentId);
    if (!current) throw new NotFoundException({ error: 'experiment_not_found' });
    const allowed = STATUS_TRANSITIONS[current.status] ?? [];
    if (!allowed.includes(nextStatus)) {
      throw new BadRequestException({ error: 'invalid_status_transition', from: current.status, to: nextStatus });
    }
    const result = await this.db.query(
      `UPDATE ${SCHEMA}.seo_experiments
       SET status = $2,
           started_at = CASE WHEN $2 = 'running' AND started_at IS NULL THEN NOW() ELSE started_at END,
           ended_at = CASE WHEN $2 = 'completed' THEN NOW() ELSE ended_at END,
           updated_at = NOW()
       WHERE id = $1
       RETURNING *`,
      [experimentId, nextStatus],
    );
    return this.mapExperiment(result.rows[0]);
  }

  async addObservation(
    experimentId: number,
    body: Record<string, unknown>,
  ): Promise<SeoExperimentObservationRow> {
    this.assertEnabled();
    const exp = await this.getExperiment(experimentId);
    if (!exp) throw new NotFoundException({ error: 'experiment_not_found' });
    const result = await this.db.query(
      `INSERT INTO ${SCHEMA}.seo_experiment_observations (
         experiment_id, variant_key, metric_date, metric_name, metric_value, source
       ) VALUES ($1,$2,$3,$4,$5,$6)
       ON CONFLICT (experiment_id, variant_key, metric_date, metric_name)
       DO UPDATE SET metric_value = EXCLUDED.metric_value, source = EXCLUDED.source
       RETURNING *`,
      [
        experimentId,
        String(body.variant_key ?? 'control'),
        String(body.metric_date ?? new Date().toISOString().slice(0, 10)),
        String(body.metric_name ?? 'clicks'),
        Number(body.metric_value ?? 0),
        String(body.source ?? 'manual'),
      ],
    );
    const row = result.rows[0];
    return {
      id: Number(row.id),
      experiment_id: Number(row.experiment_id),
      variant_key: String(row.variant_key),
      metric_date: String(row.metric_date),
      metric_name: String(row.metric_name),
      metric_value: Number(row.metric_value),
      source: String(row.source),
    };
  }

  async listObservations(experimentId: number): Promise<SeoExperimentObservationRow[]> {
    this.assertEnabled();
    const result = await this.db.query(
      `SELECT * FROM ${SCHEMA}.seo_experiment_observations
       WHERE experiment_id = $1 ORDER BY metric_date DESC, id DESC`,
      [experimentId],
    );
    return result.rows.map((row) => ({
      id: Number(row.id),
      experiment_id: Number(row.experiment_id),
      variant_key: String(row.variant_key),
      metric_date: String(row.metric_date),
      metric_name: String(row.metric_name),
      metric_value: Number(row.metric_value),
      source: String(row.source),
    }));
  }
}
