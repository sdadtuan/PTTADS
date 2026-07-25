import { Injectable } from '@nestjs/common';
import { randomBytes } from 'node:crypto';
import { SeoTechnicalRepository } from './seo-technical.repository';
import {
  SeoCrawlScheduleRow,
  SeoCwvCaptureResult,
  SeoCwvSnapshotRow,
  SeoCwvSummary,
  SeoSeverityMatrix,
  SeoTechnicalIssueRow,
} from './seo-technical.types';

@Injectable()
export class SeoTechnicalService {
  constructor(private readonly repo: SeoTechnicalRepository) {}

  listIssues(customerId: number, params?: { severity?: string; status?: string }) {
    return this.repo.listIssues(customerId, params);
  }

  severityMatrix(customerId: number): Promise<SeoSeverityMatrix> {
    return this.repo.severityMatrix(customerId);
  }

  createIssue(customerId: number, payload: Record<string, unknown>): Promise<SeoTechnicalIssueRow> {
    return this.repo.createIssue(customerId, payload);
  }

  updateIssue(issueId: number, payload: Record<string, unknown>): Promise<SeoTechnicalIssueRow> {
    return this.repo.updateIssue(issueId, payload);
  }

  importCrawlCsv(customerId: number, csv: string): Promise<{ ok: boolean; imported: number }> {
    return this.repo.importCrawlCsv(customerId, csv).then((imported) => ({ ok: true, imported }));
  }

  listCwv(customerId: number): Promise<{ summary: SeoCwvSummary; snapshots: SeoCwvSnapshotRow[] }> {
    return Promise.all([
      this.repo.cwvSummary(customerId),
      this.repo.listCwvSnapshots(customerId),
    ]).then(([summary, snapshots]) => ({ summary, snapshots }));
  }

  captureCwv(customerId: number): Promise<SeoCwvCaptureResult> {
    return this.repo.captureCwv(customerId);
  }

  getCrawlSchedule(customerId: number): Promise<{ ok: boolean; schedule: SeoCrawlScheduleRow | null }> {
    return this.repo.getCrawlSchedule(customerId).then((schedule) => ({ ok: true, schedule }));
  }

  upsertCrawlSchedule(
    customerId: number,
    body: Record<string, unknown>,
  ): Promise<{ ok: boolean; schedule: SeoCrawlScheduleRow }> {
    return this.repo.upsertCrawlSchedule(customerId, body).then((schedule) => ({ ok: true, schedule }));
  }

  verifyCrawlSecret(customerId: number, secret: string): Promise<boolean> {
    return this.repo.verifyCrawlSecret(customerId, secret);
  }

  ingestCrawlPayload(
    customerId: number,
    payload: { csv?: string; rows?: Array<Record<string, unknown>> },
  ): Promise<{ ok: boolean; rows_imported: number; customer_id: number }> {
    return this.repo.ingestCrawlPayload(customerId, payload);
  }

  generateCrawlSecret(): string {
    return randomBytes(18).toString('base64url');
  }
}
