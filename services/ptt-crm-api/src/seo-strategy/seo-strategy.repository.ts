import { BadRequestException, Injectable, NotFoundException, OnModuleDestroy } from '@nestjs/common';
import { Pool } from 'pg';
import { AppConfigService } from '../config/app-config.service';

const SCHEMA = 'seo_aeo';

function tsUtc(): string {
  return new Date().toISOString().replace('T', ' ').slice(0, 19);
}

@Injectable()
export class SeoStrategyRepository implements OnModuleDestroy {
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

  async okrTree(customerId: number) {
    const goals = await this.db.query(
      `SELECT * FROM ${SCHEMA}.seo_strategy_goals WHERE customer_id = $1 ORDER BY sort_order ASC, id ASC`,
      [customerId],
    );
    const kpis = await this.db.query(
      `SELECT * FROM ${SCHEMA}.seo_strategy_kpis WHERE customer_id = $1 ORDER BY id ASC`,
      [customerId],
    );
    const kpisByGoal = new Map<number, Record<string, unknown>[]>();
    for (const row of kpis.rows) {
      const gid = Number(row.goal_id);
      const list = kpisByGoal.get(gid) ?? [];
      list.push(row);
      kpisByGoal.set(gid, list);
    }
    const tree = [];
    for (const goal of goals.rows) {
      const gid = Number(goal.id);
      const initiatives = await this.db.query(
        `SELECT * FROM ${SCHEMA}.seo_initiatives WHERE customer_id = $1 AND goal_id = $2 ORDER BY id DESC`,
        [customerId, gid],
      );
      tree.push({
        ...goal,
        id: gid,
        kpis: kpisByGoal.get(gid) ?? [],
        initiatives: initiatives.rows,
      });
    }
    const unlinked = await this.db.query(
      `SELECT * FROM ${SCHEMA}.seo_initiatives
       WHERE customer_id = $1 AND (goal_id IS NULL OR goal_id = 0) ORDER BY id DESC`,
      [customerId],
    );
    return { customer_id: customerId, goals: tree, unlinked_initiatives: unlinked.rows };
  }

  async createGoal(customerId: number, payload: Record<string, unknown>) {
    const title = String(payload.title ?? '').trim();
    if (!title) throw new BadRequestException({ error: 'missing_title' });
    const result = await this.db.query<{ id: string }>(
      `INSERT INTO ${SCHEMA}.seo_strategy_goals (customer_id, title, description, period, status, sort_order, created_at)
       VALUES ($1,$2,$3,$4,$5,$6,NOW()) RETURNING id`,
      [
        customerId,
        title,
        String(payload.description ?? ''),
        String(payload.period ?? ''),
        String(payload.status ?? 'active'),
        Number(payload.sort_order ?? 0),
      ],
    );
    return { id: Number(result.rows[0].id), title };
  }

  async createKpi(customerId: number, payload: Record<string, unknown>) {
    const goalId = Number(payload.goal_id);
    const goal = await this.db.query(
      `SELECT id FROM ${SCHEMA}.seo_strategy_goals WHERE id = $1 AND customer_id = $2`,
      [goalId, customerId],
    );
    if (!goal.rows[0]) throw new BadRequestException({ error: 'goal_not_found' });
    const label = String(payload.metric_label ?? payload.metric_key ?? '').trim();
    if (!label) throw new BadRequestException({ error: 'missing_metric_label' });
    const result = await this.db.query<{ id: string }>(
      `INSERT INTO ${SCHEMA}.seo_strategy_kpis (
         customer_id, goal_id, initiative_id, metric_key, metric_label, target_value, current_value, unit, updated_at
       ) VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9) RETURNING id`,
      [
        customerId,
        goalId,
        payload.initiative_id ?? null,
        String(payload.metric_key ?? label.toLowerCase().replace(/\s+/g, '_')),
        label,
        payload.target_value ?? null,
        payload.current_value ?? null,
        String(payload.unit ?? ''),
        tsUtc(),
      ],
    );
    return { id: Number(result.rows[0].id), metric_label: label };
  }

  async updateKpi(customerId: number, kpiId: number, payload: Record<string, unknown>) {
    const existing = await this.db.query(
      `SELECT id FROM ${SCHEMA}.seo_strategy_kpis WHERE id = $1 AND customer_id = $2`,
      [kpiId, customerId],
    );
    if (!existing.rows[0]) throw new NotFoundException({ error: 'kpi_not_found' });

    if (payload.goal_id != null) {
      const goalId = Number(payload.goal_id);
      const g = await this.db.query(
        `SELECT id FROM ${SCHEMA}.seo_strategy_goals WHERE id = $1 AND customer_id = $2`,
        [goalId, customerId],
      );
      if (!g.rows[0]) throw new BadRequestException({ error: 'goal_not_found' });
    }

    const updates: string[] = [];
    const params: unknown[] = [kpiId, customerId];
    let p = 3;

    const setField = (col: string, val: unknown) => {
      updates.push(`${col} = $${p}`);
      params.push(val);
      p += 1;
    };

    if (payload.goal_id != null) setField('goal_id', Number(payload.goal_id));
    if (payload.metric_label != null) setField('metric_label', String(payload.metric_label).trim());
    if (payload.metric_key != null) setField('metric_key', String(payload.metric_key).trim());
    if (payload.target_value !== undefined) setField('target_value', payload.target_value);
    if (payload.current_value !== undefined) setField('current_value', payload.current_value);
    if (payload.unit != null) setField('unit', String(payload.unit));
    if (payload.initiative_id !== undefined) setField('initiative_id', payload.initiative_id ?? null);

    if (updates.length === 0) throw new BadRequestException({ error: 'no_fields' });

    updates.push(`updated_at = $${p}`);
    params.push(tsUtc());

    await this.db.query(
      `UPDATE ${SCHEMA}.seo_strategy_kpis SET ${updates.join(', ')} WHERE id = $1 AND customer_id = $2`,
      params,
    );

    const row = await this.db.query(`SELECT * FROM ${SCHEMA}.seo_strategy_kpis WHERE id = $1`, [kpiId]);
    return row.rows[0];
  }

  async linkInitiative(customerId: number, initiativeId: number, goalId: number | null) {
    const row = await this.db.query(
      `SELECT id FROM ${SCHEMA}.seo_initiatives WHERE id = $1 AND customer_id = $2`,
      [initiativeId, customerId],
    );
    if (!row.rows[0]) throw new NotFoundException({ error: 'initiative_not_found' });
    if (goalId != null) {
      const g = await this.db.query(
        `SELECT id FROM ${SCHEMA}.seo_strategy_goals WHERE id = $1 AND customer_id = $2`,
        [goalId, customerId],
      );
      if (!g.rows[0]) throw new BadRequestException({ error: 'goal_not_found' });
    }
    await this.db.query(
      `UPDATE ${SCHEMA}.seo_initiatives SET goal_id = $1 WHERE id = $2 AND customer_id = $3`,
      [goalId, initiativeId, customerId],
    );
    return { ok: true };
  }

  private async metricValue(customerId: number, metricKey: string): Promise<number | null> {
    const key = metricKey.trim().toLowerCase();
    if (key === 'gsc_clicks' || key === 'organic_clicks') {
      const r = await this.db.query(
        `SELECT COALESCE(SUM(clicks), 0) AS v FROM ${SCHEMA}.seo_gsc_daily_stats
         WHERE customer_id = $1 AND stat_date >= CURRENT_DATE - INTERVAL '28 days'`,
        [customerId],
      );
      return Number(r.rows[0]?.v ?? 0);
    }
    if (key === 'content_published' || key === 'published_count') {
      const r = await this.db.query(
        `SELECT COUNT(*) AS v FROM ${SCHEMA}.seo_content WHERE customer_id = $1 AND workflow_status = 'published'`,
        [customerId],
      );
      return Number(r.rows[0]?.v ?? 0);
    }
    if (key === 'cwv_pass_rate') {
      const r = await this.db.query(
        `SELECT SUM(CASE WHEN cwv_rating = 'pass' THEN 1 ELSE 0 END) * 100.0 / NULLIF(COUNT(*), 0) AS v
         FROM ${SCHEMA}.seo_cwv_snapshots
         WHERE customer_id = $1 AND checked_at >= NOW() - INTERVAL '30 days'`,
        [customerId],
      );
      return r.rows[0]?.v != null ? Number(r.rows[0].v) : null;
    }
    return null;
  }

  async refreshKpiMetrics(customerId: number): Promise<number> {
    const kpis = await this.db.query(
      `SELECT id, metric_key FROM ${SCHEMA}.seo_strategy_kpis WHERE customer_id = $1`,
      [customerId],
    );
    let updated = 0;
    for (const kpi of kpis.rows) {
      const val = await this.metricValue(customerId, String(kpi.metric_key ?? ''));
      if (val == null) continue;
      await this.db.query(
        `UPDATE ${SCHEMA}.seo_strategy_kpis SET current_value = $2, updated_at = $3 WHERE id = $1`,
        [kpi.id, val, tsUtc()],
      );
      updated += 1;
    }
    return updated;
  }
}
