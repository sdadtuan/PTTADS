import { Injectable } from '@nestjs/common';
import { SeoRanksRepository } from './seo-ranks.repository';
import { SeoRankCaptureResult, SeoRankKeywordRow, SeoRankSovSummary } from './seo-ranks.types';

@Injectable()
export class SeoRanksService {
  constructor(private readonly repo: SeoRanksRepository) {}

  listKeywords(customerId: number): Promise<SeoRankKeywordRow[]> {
    return this.repo.listKeywords(customerId);
  }

  addKeyword(customerId: number, body: Record<string, unknown>): Promise<SeoRankKeywordRow> {
    return this.repo.addKeyword(customerId, body);
  }

  importCsv(
    customerId: number,
    csvText: string,
  ): Promise<{ ok: boolean; tracked_added: number; snapshots: number }> {
    return this.repo.importCsv(customerId, csvText).then((out) => ({ ok: true, ...out }));
  }

  captureRanks(customerId: number): Promise<{ ok: boolean; result: SeoRankCaptureResult }> {
    return this.repo.captureRanks(customerId).then((result) => ({ ok: true, result }));
  }

  shareOfVoice(customerId: number, topN?: number): Promise<SeoRankSovSummary> {
    return this.repo.shareOfVoice(customerId, topN ?? 10);
  }
}
