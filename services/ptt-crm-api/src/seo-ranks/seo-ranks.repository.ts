import { BadRequestException, Injectable, OnModuleDestroy } from '@nestjs/common';
import { Pool } from 'pg';
import { AppConfigService } from '../config/app-config.service';
import { SEO_RANKS_SCHEMA } from './seo-ranks.constants';
import { SeoRankCaptureResult, SeoRankKeywordRow, SeoRankSovSummary } from './seo-ranks.types';
import { fetchSerpResults, positionForDomain } from './seo-serp.util';

const SCHEMA = SEO_RANKS_SCHEMA;

@Injectable()
export class SeoRanksRepository implements OnModuleDestroy {
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

  async domainHint(customerId: number): Promise<string> {
    const result = await this.db.query(
      `SELECT domains_json FROM ${SCHEMA}.seo_client_settings WHERE customer_id = $1`,
      [customerId],
    );
    const raw = result.rows[0]?.domains_json;
    let domains: string[] = [];
    if (Array.isArray(raw)) domains = raw.map(String);
    else if (raw) {
      try {
        const parsed = JSON.parse(String(raw));
        if (Array.isArray(parsed)) domains = parsed.map(String);
      } catch {
        domains = [];
      }
    }
    const first = domains[0] ?? '';
    return first.replace(/^https?:\/\//, '').split('/')[0] ?? '';
  }

  async listKeywords(customerId: number): Promise<SeoRankKeywordRow[]> {
    const result = await this.db.query(
      `SELECT t.*,
              (
                SELECT s.position FROM ${SCHEMA}.seo_rank_snapshots s
                WHERE s.tracked_keyword_id = t.id
                ORDER BY s.snapshot_date DESC, s.id DESC LIMIT 1
              ) AS latest_position,
              (
                SELECT s.snapshot_date::text FROM ${SCHEMA}.seo_rank_snapshots s
                WHERE s.tracked_keyword_id = t.id
                ORDER BY s.snapshot_date DESC, s.id DESC LIMIT 1
              ) AS latest_date
       FROM ${SCHEMA}.seo_rank_tracked_keywords t
       WHERE t.customer_id = $1 AND t.status = 'active'
       ORDER BY t.phrase ASC`,
      [customerId],
    );
    return result.rows.map((row) => ({
      id: Number(row.id),
      customer_id: Number(row.customer_id),
      keyword_id: row.keyword_id != null ? Number(row.keyword_id) : null,
      phrase: String(row.phrase ?? ''),
      target_url: String(row.target_url ?? ''),
      locale: String(row.locale ?? 'vi-VN'),
      status: String(row.status ?? 'active'),
      latest_position: row.latest_position != null ? Number(row.latest_position) : null,
      latest_date: row.latest_date != null ? String(row.latest_date) : null,
      created_at: row.created_at != null ? String(row.created_at) : null,
    }));
  }

  async addKeyword(customerId: number, body: Record<string, unknown>): Promise<SeoRankKeywordRow> {
    const phrase = String(body.phrase ?? '').trim();
    if (!phrase) throw new BadRequestException({ error: 'missing_phrase' });
    const locale = String(body.locale ?? 'vi-VN');
    const result = await this.db.query(
      `INSERT INTO ${SCHEMA}.seo_rank_tracked_keywords (
         customer_id, keyword_id, phrase, target_url, locale, status
       ) VALUES ($1, $2, $3, $4, $5, 'active')
       ON CONFLICT (customer_id, phrase, locale) DO UPDATE SET status = 'active', target_url = EXCLUDED.target_url
       RETURNING *`,
      [
        customerId,
        body.keyword_id != null ? Number(body.keyword_id) : null,
        phrase,
        String(body.target_url ?? ''),
        locale,
      ],
    );
    const row = result.rows[0];
    return {
      id: Number(row.id),
      customer_id: Number(row.customer_id),
      keyword_id: row.keyword_id != null ? Number(row.keyword_id) : null,
      phrase: String(row.phrase),
      target_url: String(row.target_url),
      locale: String(row.locale),
      status: String(row.status),
      latest_position: null,
      latest_date: null,
      created_at: row.created_at != null ? String(row.created_at) : null,
    };
  }

  async recordSnapshot(input: {
    trackedKeywordId: number;
    snapshotDate: string;
    position: number | null;
    urlFound: string;
    source: string;
  }): Promise<void> {
    await this.db.query(
      `INSERT INTO ${SCHEMA}.seo_rank_snapshots (
         tracked_keyword_id, snapshot_date, position, url_found, source
       ) VALUES ($1, $2, $3, $4, $5)
       ON CONFLICT (tracked_keyword_id, snapshot_date, source)
       DO UPDATE SET position = EXCLUDED.position, url_found = EXCLUDED.url_found`,
      [input.trackedKeywordId, input.snapshotDate, input.position, input.urlFound, input.source],
    );
  }

  async importCsv(customerId: number, csvText: string): Promise<{ tracked_added: number; snapshots: number }> {
    const lines = csvText.trim().split(/\r?\n/);
    if (lines.length < 2) return { tracked_added: 0, snapshots: 0 };
    const headers = lines[0].split(',').map((h) => h.trim().replace(/^"|"$/g, '').toLowerCase());
    let trackedAdded = 0;
    let snapshots = 0;
    for (let i = 1; i < lines.length; i += 1) {
      const cols = lines[i].split(',').map((c) => c.trim().replace(/^"|"$/g, ''));
      const row: Record<string, string> = {};
      headers.forEach((h, idx) => {
        row[h] = cols[idx] ?? '';
      });
      const phrase = (row.phrase || row.keyword || '').trim();
      if (!phrase) continue;
      const existing = await this.db.query(
        `SELECT id FROM ${SCHEMA}.seo_rank_tracked_keywords
         WHERE customer_id = $1 AND phrase = $2 AND locale = 'vi-VN'`,
        [customerId, phrase],
      );
      let tid: number;
      if (existing.rows[0]) {
        tid = Number(existing.rows[0].id);
      } else {
        const kw = await this.addKeyword(customerId, { phrase });
        tid = kw.id;
        trackedAdded += 1;
      }
      const snapDate = (row.date || row.snapshot_date || new Date().toISOString().slice(0, 10)).trim();
      const posRaw = row.position || row.rank;
      const position = posRaw ? Number.parseFloat(posRaw) : null;
      await this.recordSnapshot({
        trackedKeywordId: tid,
        snapshotDate: snapDate,
        position: position != null && Number.isFinite(position) ? position : null,
        urlFound: row.url || row.url_found || '',
        source: row.source || 'import',
      });
      snapshots += 1;
    }
    return { tracked_added: trackedAdded, snapshots };
  }

  async captureRanks(customerId: number): Promise<SeoRankCaptureResult> {
    const domainHint = await this.domainHint(customerId);
    const keywords = await this.listKeywords(customerId);
    const snapDate = new Date().toISOString().slice(0, 10);
    let captured = 0;
    const errors: string[] = [];
    for (const kw of keywords) {
      const phrase = kw.phrase.trim();
      if (!phrase) continue;
      try {
        const { results, source } = await fetchSerpResults(phrase, domainHint);
        const { position, url } = positionForDomain(results, domainHint);
        await this.recordSnapshot({
          trackedKeywordId: kw.id,
          snapshotDate: snapDate,
          position,
          urlFound: url,
          source,
        });
        captured += 1;
      } catch (err) {
        errors.push(`${phrase}: ${err instanceof Error ? err.message : String(err)}`);
      }
    }
    return { customer_id: customerId, captured, domain_hint: domainHint, errors };
  }

  async shareOfVoice(customerId: number, topN = 10): Promise<SeoRankSovSummary> {
    const domainHint = await this.domainHint(customerId);
    const keywords = await this.listKeywords(customerId);
    if (!keywords.length) {
      return { customer_id: customerId, domain_hint: domainHint, tracked: 0, in_top_n: 0, sov_pct: 0, top_n: topN };
    }
    let inTop = 0;
    for (const kw of keywords) {
      if (kw.latest_position != null && kw.latest_position <= topN) inTop += 1;
    }
    return {
      customer_id: customerId,
      domain_hint: domainHint,
      tracked: keywords.length,
      in_top_n: inTop,
      sov_pct: Math.round((inTop * 10000) / keywords.length) / 100,
      top_n: topN,
    };
  }
}
