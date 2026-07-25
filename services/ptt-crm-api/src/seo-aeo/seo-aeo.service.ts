import { Injectable } from '@nestjs/common';
import { JobQueueRepository } from '../webhooks/job-queue.repository';
import { aeoScanStubMode } from './seo-aeo.constants';
import { stubScanResult } from './seo-aeo-scan.util';
import { SeoAeoRepository } from './seo-aeo.repository';
import {
  SeoAeoCoverageSummary,
  SeoAeoMentionRow,
  SeoAeoQueryRow,
} from './seo-aeo.types';

@Injectable()
export class SeoAeoService {
  constructor(
    private readonly repo: SeoAeoRepository,
    private readonly jobQueue: JobQueueRepository,
  ) {}

  listQueries(customerId: number): Promise<SeoAeoQueryRow[]> {
    return this.repo.listQueries(customerId);
  }

  addQuery(customerId: number, body: Record<string, unknown>): Promise<SeoAeoQueryRow> {
    return this.repo.addQuery(customerId, body);
  }

  archiveQuery(questionId: number): Promise<{ ok: boolean }> {
    return this.repo.archiveQuery(questionId).then(() => ({ ok: true }));
  }

  listMentions(questionId: number): Promise<SeoAeoMentionRow[]> {
    return this.repo.listMentions(questionId);
  }

  coverage(customerId: number): Promise<SeoAeoCoverageSummary> {
    return this.repo.coverage(customerId);
  }

  async enqueueScan(
    customerId: number,
    queryIds?: number[],
  ): Promise<{ ok: boolean; mode: string; job?: unknown; outcome?: unknown; error?: string }> {
    const payload: Record<string, unknown> = {
      customer_id: customerId,
      query_ids: queryIds ?? [],
    };
    const stamp = new Date().toISOString().slice(0, 10);
    const idem = `seo_aeo_scan:${customerId}:${stamp}`;
    const job = await this.jobQueue.enqueueSeoAeoScanJob({ payload, idempotencyKey: idem });
    if (job) {
      return { ok: true, mode: 'queue', job };
    }
    if (process.env.PTT_JOBS_SYNC_FALLBACK?.trim().toLowerCase() !== '0') {
      const outcome = await this.scanBatchSync(customerId, queryIds);
      return { ok: outcome.ok, mode: 'sync', outcome };
    }
    return { ok: false, mode: 'none', error: 'job_queue_unavailable' };
  }

  async scanBatchSync(
    customerId: number,
    queryIds?: number[],
  ): Promise<{ ok: boolean; scanned: number; ok_count: number; results: Array<Record<string, unknown>> }> {
    let queries = await this.repo.listQueries(customerId);
    if (queryIds?.length) {
      const idSet = new Set(queryIds.map(Number));
      queries = queries.filter((q) => idSet.has(q.id));
    }
    if (!queries.length) {
      return { ok: true, scanned: 0, ok_count: 0, results: [] };
    }
    const results: Array<Record<string, unknown>> = [];
    let okCount = 0;
    for (const q of queries) {
      try {
        const scan = aeoScanStubMode() ? stubScanResult(q.query_text) : stubScanResult(q.query_text);
        const mentionId = await this.repo.insertMention({
          customerId,
          questionId: q.id,
          queryText: q.query_text,
          scan,
        });
        okCount += 1;
        results.push({ query_id: q.id, ok: true, mention_id: mentionId, brand_visible: scan.brand_visible });
      } catch (err) {
        results.push({
          query_id: q.id,
          ok: false,
          error: err instanceof Error ? err.message : String(err),
        });
      }
    }
    return { ok: okCount === queries.length, scanned: queries.length, ok_count: okCount, results };
  }
}
