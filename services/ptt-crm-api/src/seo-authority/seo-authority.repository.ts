import { BadRequestException, Injectable, OnModuleDestroy } from '@nestjs/common';
import { Pool } from 'pg';
import { AppConfigService } from '../config/app-config.service';
import { AUTHORITY_SIGNAL_TYPES, SEO_AUTHORITY_SCHEMA } from './seo-authority.constants';
import { parseAuthorityCsv } from './seo-authority-csv.util';
import { SeoAuthoritySignalRow, SeoAuthoritySummary } from './seo-authority.types';

const SCHEMA = SEO_AUTHORITY_SCHEMA;

@Injectable()
export class SeoAuthorityRepository implements OnModuleDestroy {
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

  private mapSignal(row: Record<string, unknown>): SeoAuthoritySignalRow {
    return {
      id: Number(row.id),
      customer_id: Number(row.customer_id),
      signal_type: String(row.signal_type ?? 'backlink'),
      source_domain: String(row.source_domain ?? ''),
      source_url: String(row.source_url ?? ''),
      target_url: String(row.target_url ?? ''),
      anchor_text: String(row.anchor_text ?? ''),
      domain_rating: row.domain_rating != null ? Number(row.domain_rating) : null,
      status: String(row.status ?? 'active'),
      first_seen_at: row.first_seen_at != null ? String(row.first_seen_at) : null,
      last_seen_at: row.last_seen_at != null ? String(row.last_seen_at) : null,
      notes: String(row.notes ?? ''),
      created_at: row.created_at != null ? String(row.created_at) : null,
    };
  }

  async listSignals(
    customerId: number,
    params?: { signal_type?: string; status?: string; limit?: number },
  ): Promise<SeoAuthoritySignalRow[]> {
    const limit = Math.min(params?.limit ?? 500, 1000);
    const values: unknown[] = [customerId];
    let sql = `SELECT * FROM ${SCHEMA}.seo_authority_signals WHERE customer_id = $1`;
    if (params?.signal_type) {
      values.push(params.signal_type);
      sql += ` AND signal_type = $${values.length}`;
    }
    if (params?.status) {
      values.push(params.status);
      sql += ` AND status = $${values.length}`;
    }
    sql += ` ORDER BY last_seen_at DESC NULLS LAST, id DESC LIMIT $${values.length + 1}`;
    values.push(limit);
    const result = await this.db.query(sql, values);
    return result.rows.map((r) => this.mapSignal(r));
  }

  async addSignal(customerId: number, body: Record<string, unknown>): Promise<SeoAuthoritySignalRow> {
    const signalType = String(body.signal_type ?? 'backlink').trim().toLowerCase();
    if (!AUTHORITY_SIGNAL_TYPES.includes(signalType as (typeof AUTHORITY_SIGNAL_TYPES)[number])) {
      throw new BadRequestException({ error: 'invalid_signal_type' });
    }
    const today = new Date().toISOString().slice(0, 10);
    const result = await this.db.query(
      `INSERT INTO ${SCHEMA}.seo_authority_signals (
         customer_id, signal_type, source_domain, source_url, target_url,
         anchor_text, domain_rating, status, first_seen_at, last_seen_at, notes
       ) VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9,$10,$11)
       ON CONFLICT (customer_id, signal_type, source_url, target_url)
       DO UPDATE SET
         domain_rating = EXCLUDED.domain_rating,
         status = EXCLUDED.status,
         last_seen_at = EXCLUDED.last_seen_at,
         anchor_text = EXCLUDED.anchor_text
       RETURNING *`,
      [
        customerId,
        signalType,
        String(body.source_domain ?? ''),
        String(body.source_url ?? ''),
        String(body.target_url ?? ''),
        String(body.anchor_text ?? ''),
        body.domain_rating != null ? Number(body.domain_rating) : null,
        String(body.status ?? 'active'),
        body.first_seen_at ?? today,
        body.last_seen_at ?? today,
        String(body.notes ?? ''),
      ],
    );
    return this.mapSignal(result.rows[0]);
  }

  async importCsv(
    customerId: number,
    csvText: string,
    signalType: string,
  ): Promise<{ imported: number; skipped: number }> {
    const { rows, skipped } = parseAuthorityCsv(csvText, signalType);
    let imported = 0;
    for (const row of rows) {
      await this.addSignal(customerId, row);
      imported += 1;
    }
    return { imported, skipped };
  }

  async summary(customerId: number): Promise<SeoAuthoritySummary> {
    const result = await this.db.query(
      `SELECT signal_type, status, COUNT(*) AS c, AVG(domain_rating) AS avg_dr
       FROM ${SCHEMA}.seo_authority_signals
       WHERE customer_id = $1
       GROUP BY signal_type, status`,
      [customerId],
    );
    const summary: SeoAuthoritySummary = {
      backlinks_active: 0,
      backlinks_lost: 0,
      citations: 0,
      brand_mentions: 0,
      pr_signals: 0,
      avg_dr: 0,
      total_signals: 0,
    };
    let drSum = 0;
    let drCount = 0;
    for (const row of result.rows) {
      const st = String(row.signal_type ?? '');
      const status = String(row.status ?? '');
      const count = Number(row.c ?? 0);
      const avgDr = row.avg_dr != null ? Number(row.avg_dr) : null;
      if (avgDr != null) {
        drSum += avgDr * count;
        drCount += count;
      }
      if (st === 'backlink') {
        if (status === 'lost') summary.backlinks_lost += count;
        else summary.backlinks_active += count;
      } else if (st === 'citation') summary.citations += count;
      else if (st === 'brand_mention') summary.brand_mentions += count;
      else if (st === 'pr') summary.pr_signals += count;
    }
    summary.avg_dr = drCount ? Math.round((drSum / drCount) * 100) / 100 : 0;
    summary.total_signals =
      summary.backlinks_active +
      summary.backlinks_lost +
      summary.citations +
      summary.brand_mentions +
      summary.pr_signals;
    return summary;
  }
}
