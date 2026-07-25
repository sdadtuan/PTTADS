import { BadRequestException, Injectable, NotFoundException, OnModuleDestroy } from '@nestjs/common';
import { Pool } from 'pg';
import { AppConfigService } from '../config/app-config.service';
import { AEO_QUESTION_SOURCE, SEO_AEO_SCHEMA } from './seo-aeo.constants';
import { citationStatus } from './seo-aeo-scan.util';
import {
  SeoAeoCoverageSummary,
  SeoAeoMentionRow,
  SeoAeoQueryRow,
} from './seo-aeo.types';

const SCHEMA = SEO_AEO_SCHEMA;

function rowBool(value: unknown): boolean {
  return value === true || value === 1 || value === '1' || value === 't' || value === 'true';
}

@Injectable()
export class SeoAeoRepository implements OnModuleDestroy {
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

  async listQueries(customerId: number): Promise<SeoAeoQueryRow[]> {
    const result = await this.db.query(
      `SELECT q.id, q.customer_id, q.question_text AS query_text, q.brand_name, q.notes,
              q.lifecycle_id, q.created_at::text,
              m.detected_at::text AS last_scan_date, m.brand_visible, m.gap_notes
       FROM ${SCHEMA}.seo_questions q
       LEFT JOIN LATERAL (
         SELECT brand_visible, gap_notes, detected_at
         FROM ${SCHEMA}.seo_ai_mentions
         WHERE question_id = q.id ORDER BY id DESC LIMIT 1
       ) m ON true
       WHERE q.customer_id = $1 AND q.source = $2 AND q.status = 'active'
       ORDER BY q.id`,
      [customerId, AEO_QUESTION_SOURCE],
    );
    return result.rows.map((row) => {
      const visible = rowBool(row.brand_visible);
      const gap = String(row.gap_notes ?? '');
      return {
        id: Number(row.id),
        customer_id: Number(row.customer_id),
        query_text: String(row.query_text ?? ''),
        brand_name: String(row.brand_name ?? ''),
        notes: String(row.notes ?? ''),
        lifecycle_id: row.lifecycle_id != null ? Number(row.lifecycle_id) : null,
        created_at: row.created_at != null ? String(row.created_at) : null,
        last_scan_date: row.last_scan_date != null ? String(row.last_scan_date) : null,
        brand_visible: visible,
        citation_status: citationStatus(visible, gap),
      };
    });
  }

  async getQuery(questionId: number): Promise<SeoAeoQueryRow | null> {
    const result = await this.db.query(
      `SELECT id, customer_id, question_text AS query_text, brand_name, notes, lifecycle_id, created_at::text
       FROM ${SCHEMA}.seo_questions
       WHERE id = $1 AND source = $2 AND status = 'active'`,
      [questionId, AEO_QUESTION_SOURCE],
    );
    const row = result.rows[0];
    if (!row) return null;
    return {
      id: Number(row.id),
      customer_id: Number(row.customer_id),
      query_text: String(row.query_text ?? ''),
      brand_name: String(row.brand_name ?? ''),
      notes: String(row.notes ?? ''),
      lifecycle_id: row.lifecycle_id != null ? Number(row.lifecycle_id) : null,
      created_at: row.created_at != null ? String(row.created_at) : null,
      last_scan_date: null,
      brand_visible: false,
      citation_status: 'absent',
    };
  }

  async addQuery(customerId: number, body: Record<string, unknown>): Promise<SeoAeoQueryRow> {
    const queryText = String(body.query_text ?? body.question_text ?? '').trim();
    const brandName = String(body.brand_name ?? '').trim();
    if (!queryText) throw new BadRequestException({ error: 'missing_query_text' });
    if (!brandName) throw new BadRequestException({ error: 'missing_brand_name' });
    const result = await this.db.query(
      `INSERT INTO ${SCHEMA}.seo_questions (
         customer_id, question_text, intent, funnel_stage, source, brand_name, lifecycle_id, notes
       ) VALUES ($1, $2, 'informational', 'awareness', $3, $4, $5, $6)
       RETURNING id, customer_id, question_text AS query_text, brand_name, notes, lifecycle_id, created_at::text`,
      [
        customerId,
        queryText,
        AEO_QUESTION_SOURCE,
        brandName,
        body.lifecycle_id != null ? Number(body.lifecycle_id) : null,
        String(body.notes ?? ''),
      ],
    );
    const row = result.rows[0];
    return {
      id: Number(row.id),
      customer_id: Number(row.customer_id),
      query_text: String(row.query_text),
      brand_name: String(row.brand_name),
      notes: String(row.notes),
      lifecycle_id: row.lifecycle_id != null ? Number(row.lifecycle_id) : null,
      created_at: row.created_at != null ? String(row.created_at) : null,
      last_scan_date: null,
      brand_visible: false,
      citation_status: 'absent',
    };
  }

  async archiveQuery(questionId: number): Promise<void> {
    const result = await this.db.query(
      `UPDATE ${SCHEMA}.seo_questions SET status = 'archived'
       WHERE id = $1 AND source = $2`,
      [questionId, AEO_QUESTION_SOURCE],
    );
    if ((result.rowCount ?? 0) === 0) {
      throw new NotFoundException({ error: 'query_not_found' });
    }
  }

  async listMentions(questionId: number): Promise<SeoAeoMentionRow[]> {
    const result = await this.db.query(
      `SELECT id, question_id, ai_response, brand_visible, gap_notes, detected_at::text AS created_at
       FROM ${SCHEMA}.seo_ai_mentions
       WHERE question_id = $1
       ORDER BY id DESC`,
      [questionId],
    );
    return result.rows.map((row) => {
      const visible = rowBool(row.brand_visible);
      const gap = String(row.gap_notes ?? '');
      return {
        id: Number(row.id),
        question_id: Number(row.question_id),
        ai_response: String(row.ai_response ?? ''),
        brand_visible: visible,
        gap_notes: gap,
        citation_status: citationStatus(visible, gap),
        created_at: row.created_at != null ? String(row.created_at) : null,
      };
    });
  }

  async coverage(customerId: number): Promise<SeoAeoCoverageSummary> {
    const result = await this.db.query(
      `SELECT COUNT(*) AS total,
              COALESCE(SUM(CASE WHEN COALESCE(m.brand_visible, false) THEN 1 ELSE 0 END), 0) AS visible
       FROM ${SCHEMA}.seo_questions q
       LEFT JOIN LATERAL (
         SELECT brand_visible FROM ${SCHEMA}.seo_ai_mentions
         WHERE question_id = q.id ORDER BY id DESC LIMIT 1
       ) m ON true
       WHERE q.customer_id = $1 AND q.source = $2 AND q.status = 'active'`,
      [customerId, AEO_QUESTION_SOURCE],
    );
    const total = Number(result.rows[0]?.total ?? 0);
    const visible = Number(result.rows[0]?.visible ?? 0);
    return {
      customer_id: customerId,
      total,
      visible,
      coverage_pct: total ? Math.round((1000 * visible) / total) / 10 : 0,
    };
  }

  async insertMention(input: {
    customerId: number;
    questionId: number;
    queryText: string;
    scan: { ai_response: string; brand_visible: boolean; gap_notes: string };
  }): Promise<number> {
    const brandVisible = Boolean(input.scan.brand_visible);
    const gapNotes = String(input.scan.gap_notes ?? '');
    const result = await this.db.query(
      `INSERT INTO ${SCHEMA}.seo_ai_mentions (
         customer_id, question_id, platform, query_text, citation_status,
         brand_visible, gap_notes, ai_response
       ) VALUES ($1, $2, 'anthropic_sim', $3, $4, $5, $6, $7)
       RETURNING id`,
      [
        input.customerId,
        input.questionId,
        input.queryText,
        citationStatus(brandVisible, gapNotes),
        brandVisible,
        gapNotes,
        String(input.scan.ai_response ?? ''),
      ],
    );
    return Number(result.rows[0]?.id ?? 0);
  }
}
