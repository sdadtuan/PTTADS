import { Injectable } from '@nestjs/common';
import { SeoTechnicalRepository } from './seo-technical.repository';
import {
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
}
