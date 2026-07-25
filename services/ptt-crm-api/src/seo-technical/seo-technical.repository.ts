import { BadRequestException, Injectable, NotFoundException, OnModuleDestroy } from '@nestjs/common';
import { Pool } from 'pg';
import { AppConfigService } from '../config/app-config.service';
import { effectivePageSpeed } from './seo-cwv.util';
import { ISSUE_SEVERITIES, SEO_TECH_SCHEMA } from './seo-technical.constants';
import {
  SeoCwvCaptureResult,
  SeoCwvSnapshotRow,
  SeoCwvSummary,
  SeoSeverityMatrix,
  SeoTechnicalIssueRow,
} from './seo-technical.types';

const SCHEMA = SEO_TECH_SCHEMA;

function tsUtc(): string {
  return new Date().toISOString().replace('T', ' ').slice(0, 19);
}

@Injectable()
export class SeoTechnicalRepository implements OnModuleDestroy {
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

  private mapIssue(row: Record<string, unknown>): SeoTechnicalIssueRow {
    return {
      id: Number(row.id),
      customer_id: Number(row.customer_id),
      page_id: row.page_id != null ? Number(row.page_id) : null,
      url: String(row.url ?? ''),
      issue_type: String(row.issue_type ?? ''),
      severity: String(row.severity ?? 'medium'),
      status: String(row.status ?? 'detected'),
      description: String(row.description ?? ''),
      impact_notes: String(row.impact_notes ?? ''),
      assignee_id: row.assignee_id != null ? Number(row.assignee_id) : null,
      discovered_at: row.discovered_at != null ? String(row.discovered_at) : null,
      resolved_at: row.resolved_at != null ? String(row.resolved_at) : null,
      crm_task_id: row.crm_task_id != null ? Number(row.crm_task_id) : null,
      lifecycle_id: row.lifecycle_id != null ? Number(row.lifecycle_id) : null,
    };
  }

  async listIssues(
    customerId: number,
    params?: { severity?: string; status?: string; limit?: number },
  ): Promise<SeoTechnicalIssueRow[]> {
    const limit = Math.min(params?.limit ?? 500, 1000);
    const values: unknown[] = [customerId];
    let sql = `SELECT * FROM ${SCHEMA}.seo_technical_issues WHERE customer_id = $1`;
    if (params?.severity) {
      values.push(params.severity);
      sql += ` AND severity = $${values.length}`;
    }
    if (params?.status) {
      values.push(params.status);
      sql += ` AND status = $${values.length}`;
    } else {
      sql += ` AND status NOT IN ('closed', 'verified')`;
    }
    sql += ` ORDER BY CASE severity WHEN 'critical' THEN 0 WHEN 'high' THEN 1 WHEN 'medium' THEN 2 ELSE 3 END, id DESC LIMIT $${values.length + 1}`;
    values.push(limit);
    const result = await this.db.query(sql, values);
    return result.rows.map((r) => this.mapIssue(r));
  }

  async severityMatrix(customerId: number): Promise<SeoSeverityMatrix> {
    const result = await this.db.query<{ severity: string; c: string }>(
      `SELECT severity, COUNT(*) AS c FROM ${SCHEMA}.seo_technical_issues
       WHERE customer_id = $1 AND status NOT IN ('closed', 'verified')
       GROUP BY severity`,
      [customerId],
    );
    const out: SeoSeverityMatrix = { critical: 0, high: 0, medium: 0, low: 0 };
    for (const row of result.rows) {
      const key = row.severity as keyof SeoSeverityMatrix;
      if (ISSUE_SEVERITIES.includes(key)) out[key] = Number(row.c);
    }
    return out;
  }

  async countOpenCritical(customerId?: number): Promise<number> {
    const values: unknown[] = [];
    let sql = `SELECT COUNT(*) AS c FROM ${SCHEMA}.seo_technical_issues
               WHERE severity = 'critical' AND status NOT IN ('closed', 'verified')`;
    if (customerId != null) {
      values.push(customerId);
      sql += ` AND customer_id = $${values.length}`;
    }
    const result = await this.db.query(sql, values);
    return Number(result.rows[0]?.c ?? 0);
  }

  async createIssue(customerId: number, payload: Record<string, unknown>): Promise<SeoTechnicalIssueRow> {
    const url = String(payload.url ?? '').trim();
    if (!url) throw new BadRequestException({ error: 'missing_url' });
    const result = await this.db.query<{ id: string }>(
      `INSERT INTO ${SCHEMA}.seo_technical_issues (
         customer_id, url, issue_type, severity, status, description, impact_notes, assignee_id, discovered_at
       ) VALUES ($1,$2,$3,$4,$5,$6,$7,$8,NOW())
       RETURNING id`,
      [
        customerId,
        url,
        String(payload.issue_type ?? 'unknown'),
        String(payload.severity ?? 'medium'),
        String(payload.status ?? 'detected'),
        String(payload.description ?? ''),
        String(payload.impact_notes ?? ''),
        payload.assignee_id ?? null,
      ],
    );
    const id = Number(result.rows[0].id);
    const detail = await this.getIssue(id);
    if (!detail) throw new BadRequestException({ error: 'create_failed' });
    return detail;
  }

  async getIssue(issueId: number): Promise<SeoTechnicalIssueRow | null> {
    const result = await this.db.query(`SELECT * FROM ${SCHEMA}.seo_technical_issues WHERE id = $1`, [issueId]);
    const row = result.rows[0];
    return row ? this.mapIssue(row) : null;
  }

  async updateIssue(issueId: number, payload: Record<string, unknown>): Promise<SeoTechnicalIssueRow> {
    const existing = await this.getIssue(issueId);
    if (!existing) throw new NotFoundException({ error: 'issue_not_found' });
    const status = String(payload.status ?? existing.status);
    let resolvedAt = existing.resolved_at;
    if (['fixed', 'verified', 'closed'].includes(status) && !resolvedAt) {
      resolvedAt = tsUtc();
    }
    await this.db.query(
      `UPDATE ${SCHEMA}.seo_technical_issues SET
         status = $2, severity = $3, assignee_id = $4, description = $5, impact_notes = $6, resolved_at = $7
       WHERE id = $1`,
      [
        issueId,
        status,
        String(payload.severity ?? existing.severity),
        payload.assignee_id !== undefined ? payload.assignee_id : existing.assignee_id,
        String(payload.description ?? existing.description),
        String(payload.impact_notes ?? existing.impact_notes),
        resolvedAt,
      ],
    );
    const detail = await this.getIssue(issueId);
    if (!detail) throw new NotFoundException({ error: 'issue_not_found' });
    return detail;
  }

  async importCrawlCsv(customerId: number, csvText: string): Promise<number> {
    const lines = csvText.trim().split(/\r?\n/);
    if (lines.length < 2) return 0;
    const headers = lines[0].split(',').map((h) => h.trim().toLowerCase());
    const idx = (name: string, alt?: string) => {
      const i = headers.indexOf(name);
      if (i >= 0) return i;
      return alt ? headers.indexOf(alt) : -1;
    };
    const urlI = idx('url');
    const typeI = idx('issue_type', 'type');
    const sevI = idx('severity');
    const descI = idx('description', 'message');
    let count = 0;
    for (const line of lines.slice(1)) {
      if (!line.trim()) continue;
      const cols = line.split(',');
      const url = (cols[urlI] ?? '').trim();
      if (!url) continue;
      await this.createIssue(customerId, {
        url,
        issue_type: typeI >= 0 ? cols[typeI] : 'crawl',
        severity: sevI >= 0 ? cols[sevI] : 'medium',
        description: descI >= 0 ? cols[descI] : '',
      });
      count += 1;
    }
    return count;
  }

  private async urlsForCustomer(customerId: number, limit = 3): Promise<string[]> {
    const pages = await this.db.query<{ url: string }>(
      `SELECT url FROM ${SCHEMA}.seo_pages
       WHERE customer_id = $1 AND url != ''
       ORDER BY COALESCE(last_crawled_at, created_at) DESC NULLS LAST, id DESC
       LIMIT $2`,
      [customerId, limit],
    );
    const urls = pages.rows.map((r) => r.url).filter(Boolean);
    if (urls.length) return urls;
    const settings = await this.db.query<{ domains: unknown }>(
      `SELECT domains FROM ${SCHEMA}.seo_client_settings WHERE customer_id = $1`,
      [customerId],
    );
    const domainsRaw = settings.rows[0]?.domains;
    let domains: string[] = [];
    if (Array.isArray(domainsRaw)) domains = domainsRaw.map(String);
    else if (domainsRaw) {
      try {
        const parsed = JSON.parse(String(domainsRaw));
        if (Array.isArray(parsed)) domains = parsed.map(String);
      } catch {
        domains = [];
      }
    }
    return domains.slice(0, limit).map((d) => {
      let url = d.trim();
      if (!url.startsWith('http')) url = `https://${url}`;
      return `${url.replace(/\/$/, '')}/`;
    });
  }

  async listCwvSnapshots(customerId: number, limit = 20): Promise<SeoCwvSnapshotRow[]> {
    const result = await this.db.query(
      `SELECT * FROM ${SCHEMA}.seo_cwv_snapshots WHERE customer_id = $1
       ORDER BY checked_at DESC NULLS LAST, id DESC LIMIT $2`,
      [customerId, limit],
    );
    return result.rows.map((row) => ({
      id: Number(row.id),
      customer_id: Number(row.customer_id),
      url: String(row.url ?? ''),
      lcp_ms: row.lcp_ms != null ? Number(row.lcp_ms) : null,
      cls: row.cls != null ? Number(row.cls) : null,
      inp_ms: row.inp_ms != null ? Number(row.inp_ms) : null,
      performance_score: row.performance_score != null ? Number(row.performance_score) : null,
      cwv_rating: String(row.cwv_rating ?? 'unknown'),
      source: String(row.source ?? ''),
      checked_at: row.checked_at != null ? String(row.checked_at) : null,
    }));
  }

  async cwvSummary(customerId: number, days = 30): Promise<SeoCwvSummary> {
    const result = await this.db.query(
      `SELECT
         COUNT(*) AS snapshot_count,
         AVG(lcp_ms) AS avg_lcp_ms,
         AVG(cls) AS avg_cls,
         AVG(performance_score) AS avg_performance_score,
         SUM(CASE WHEN cwv_rating = 'pass' THEN 1 ELSE 0 END) * 100.0 / NULLIF(COUNT(*), 0) AS pass_rate_pct
       FROM ${SCHEMA}.seo_cwv_snapshots
       WHERE customer_id = $1 AND checked_at >= NOW() - ($2 || ' days')::interval`,
      [customerId, String(days)],
    );
    const row = result.rows[0] ?? {};
    return {
      pass_rate_pct: Math.round(Number(row.pass_rate_pct ?? 0) * 10) / 10,
      avg_lcp_ms: row.avg_lcp_ms != null ? Math.round(Number(row.avg_lcp_ms)) : null,
      avg_cls: row.avg_cls != null ? Math.round(Number(row.avg_cls) * 1000) / 1000 : null,
      avg_performance_score:
        row.avg_performance_score != null ? Math.round(Number(row.avg_performance_score) * 10) / 10 : null,
      snapshot_count: Number(row.snapshot_count ?? 0),
    };
  }

  async captureCwv(customerId: number, limit = 3): Promise<SeoCwvCaptureResult> {
    const urls = await this.urlsForCustomer(customerId, limit);
    if (!urls.length) {
      return { customer_id: customerId, captured: 0, snapshots: [], errors: [], skipped: true, reason: 'no_urls' };
    }
    const snapshots: SeoCwvCaptureResult['snapshots'] = [];
    const errors: string[] = [];
    for (const url of urls) {
      try {
        const metrics = await effectivePageSpeed(url);
        const ins = await this.db.query<{ id: string }>(
          `INSERT INTO ${SCHEMA}.seo_cwv_snapshots (
             customer_id, url, lcp_ms, cls, inp_ms, performance_score, cwv_rating, source, checked_at
           ) VALUES ($1,$2,$3,$4,$5,$6,$7,$8,NOW()) RETURNING id`,
          [
            customerId,
            String(metrics.url ?? url),
            metrics.lcp_ms ?? null,
            metrics.cls ?? null,
            metrics.inp_ms ?? null,
            metrics.performance_score ?? null,
            String(metrics.cwv_rating ?? 'unknown'),
            String(metrics.source ?? 'pagespeed'),
          ],
        );
        snapshots.push({
          snapshot_id: Number(ins.rows[0].id),
          url,
          cwv_rating: String(metrics.cwv_rating ?? 'unknown'),
        });
      } catch (err) {
        errors.push(`${url}: ${err instanceof Error ? err.message : String(err)}`);
      }
    }
    return { customer_id: customerId, captured: snapshots.length, snapshots, errors };
  }
}
