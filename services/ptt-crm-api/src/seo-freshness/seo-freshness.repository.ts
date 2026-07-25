import { Injectable, NotFoundException, OnModuleDestroy } from '@nestjs/common';
import { Pool } from 'pg';
import { AppConfigService } from '../config/app-config.service';
import { computeDecayScore, refreshPriority, SEO_FRESHNESS_SCHEMA } from './seo-freshness.constants';
import { SeoFreshnessRow } from './seo-freshness.types';

const SCHEMA = SEO_FRESHNESS_SCHEMA;

@Injectable()
export class SeoFreshnessRepository implements OnModuleDestroy {
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

  private mapRow(row: Record<string, unknown>): SeoFreshnessRow {
    let signals: Record<string, unknown> = {};
    const raw = row.signals_json;
    if (raw && typeof raw === 'object') signals = raw as Record<string, unknown>;
    else if (raw) {
      try {
        signals = JSON.parse(String(raw)) as Record<string, unknown>;
      } catch {
        signals = {};
      }
    }
    return {
      id: Number(row.id),
      customer_id: Number(row.customer_id),
      content_id: Number(row.content_id),
      title: String(row.title ?? ''),
      slug: String(row.slug ?? ''),
      workflow_status: String(row.workflow_status ?? ''),
      decay_score: Number(row.decay_score ?? 0),
      traffic_delta_pct: row.traffic_delta_pct != null ? Number(row.traffic_delta_pct) : null,
      age_days: Number(row.age_days ?? 0),
      refresh_priority: String(row.refresh_priority ?? 'low'),
      last_scored_at: row.last_scored_at != null ? String(row.last_scored_at) : null,
      signals,
    };
  }

  async listQueue(
    customerId: number,
    params?: { min_priority?: string; limit?: number },
  ): Promise<SeoFreshnessRow[]> {
    const limit = Math.min(params?.limit ?? 100, 500);
    const priorityOrder: Record<string, number> = { urgent: 4, high: 3, medium: 2, low: 1 };
    const values: unknown[] = [customerId];
    let sql = `SELECT f.*, c.title, c.slug, c.workflow_status
               FROM ${SCHEMA}.seo_content_freshness f
               JOIN ${SCHEMA}.seo_content c ON c.id = f.content_id
               WHERE f.customer_id = $1`;
    if (params?.min_priority && priorityOrder[params.min_priority]) {
      const allowed = Object.entries(priorityOrder)
        .filter(([, v]) => v >= priorityOrder[params.min_priority!])
        .map(([k]) => k);
      values.push(allowed);
      sql += ` AND f.refresh_priority = ANY($${values.length}::text[])`;
    }
    sql += ` ORDER BY f.decay_score DESC, f.last_scored_at DESC LIMIT $${values.length + 1}`;
    values.push(limit);
    const result = await this.db.query(sql, values);
    return result.rows.map((r) => this.mapRow(r));
  }

  private parseDate(raw: unknown): Date | null {
    if (!raw) return null;
    const text = String(raw).slice(0, 10);
    const d = new Date(text);
    return Number.isNaN(d.getTime()) ? null : d;
  }

  private ageDays(item: Record<string, unknown>): number {
    const anchor =
      this.parseDate(item.publish_date) ??
      this.parseDate(item.updated_at) ??
      this.parseDate(item.created_at);
    if (!anchor) return 0;
    const today = new Date();
    today.setHours(0, 0, 0, 0);
    anchor.setHours(0, 0, 0, 0);
    return Math.max(0, Math.floor((today.getTime() - anchor.getTime()) / 86400000));
  }

  private async gscClicks(customerId: number, slug: string): Promise<{ current: number; previous: number }> {
    const path = slug ? `/${slug.replace(/^\//, '')}` : '';
    const result = await this.db.query(
      `SELECT COALESCE(SUM(clicks),0) AS clicks
       FROM ${SCHEMA}.seo_gsc_daily_stats
       WHERE customer_id = $1 AND stat_date >= CURRENT_DATE - INTERVAL '28 days'
         AND ($2 = '' OR page LIKE '%' || $2 || '%')`,
      [customerId, path],
    );
    const current = Number(result.rows[0]?.clicks ?? 0);
    const prev = await this.db.query(
      `SELECT COALESCE(SUM(clicks),0) AS clicks
       FROM ${SCHEMA}.seo_gsc_daily_stats
       WHERE customer_id = $1
         AND stat_date >= CURRENT_DATE - INTERVAL '56 days'
         AND stat_date < CURRENT_DATE - INTERVAL '28 days'
         AND ($2 = '' OR page LIKE '%' || $2 || '%')`,
      [customerId, path],
    );
    return { current, previous: Number(prev.rows[0]?.clicks ?? 0) };
  }

  async scoreContent(customerId: number, contentId: number): Promise<SeoFreshnessRow> {
    const content = await this.db.query(
      `SELECT * FROM ${SCHEMA}.seo_content WHERE id = $1`,
      [contentId],
    );
    const item = content.rows[0];
    if (!item) throw new NotFoundException({ error: 'content_not_found' });
    if (Number(item.customer_id) !== customerId) {
      throw new NotFoundException({ error: 'customer_mismatch' });
    }
    const age = this.ageDays(item);
    const slug = String(item.slug ?? '');
    const gsc = await this.gscClicks(customerId, slug);
    const trafficDelta =
      gsc.previous > 0 ? Math.round(((gsc.current - gsc.previous) / gsc.previous) * 1000) / 10 : null;
    const decay = computeDecayScore({
      ageDays: age,
      trafficDeltaPct: trafficDelta,
      gscClicksCurrent: gsc.current,
      gscClicksPrevious: gsc.previous,
      workflowStatus: String(item.workflow_status ?? ''),
    });
    const priority = refreshPriority(decay);
    const signals = { gsc_clicks_current: gsc.current, gsc_clicks_previous: gsc.previous, traffic_delta_pct: trafficDelta };
    const result = await this.db.query(
      `INSERT INTO ${SCHEMA}.seo_content_freshness (
         customer_id, content_id, decay_score, traffic_delta_pct, age_days,
         signals_json, refresh_priority, last_scored_at
       ) VALUES ($1,$2,$3,$4,$5,$6::jsonb,$7,NOW())
       ON CONFLICT (customer_id, content_id) DO UPDATE SET
         decay_score = EXCLUDED.decay_score,
         traffic_delta_pct = EXCLUDED.traffic_delta_pct,
         age_days = EXCLUDED.age_days,
         signals_json = EXCLUDED.signals_json,
         refresh_priority = EXCLUDED.refresh_priority,
         last_scored_at = NOW()
       RETURNING *, (SELECT title FROM ${SCHEMA}.seo_content WHERE id = $2) AS title,
                   (SELECT slug FROM ${SCHEMA}.seo_content WHERE id = $2) AS slug,
                   (SELECT workflow_status FROM ${SCHEMA}.seo_content WHERE id = $2) AS workflow_status`,
      [customerId, contentId, decay, trafficDelta, age, JSON.stringify(signals), priority],
    );
    return this.mapRow(result.rows[0]);
  }

  async scoreAll(customerId: number): Promise<{ scored: number }> {
    const rows = await this.db.query(
      `SELECT id FROM ${SCHEMA}.seo_content
       WHERE customer_id = $1 AND workflow_status IN ('published', 'monitoring')`,
      [customerId],
    );
    let scored = 0;
    for (const row of rows.rows) {
      await this.scoreContent(customerId, Number(row.id));
      scored += 1;
    }
    return { scored };
  }

  async flagRefresh(contentId: number): Promise<{ ok: boolean }> {
    const result = await this.db.query(
      `UPDATE ${SCHEMA}.seo_content
       SET workflow_status = 'refresh_required', updated_at = NOW()
       WHERE id = $1 AND workflow_status IN ('published', 'monitoring')
       RETURNING id`,
      [contentId],
    );
    if ((result.rowCount ?? 0) === 0) {
      throw new NotFoundException({ error: 'content_not_eligible' });
    }
    return { ok: true };
  }
}
