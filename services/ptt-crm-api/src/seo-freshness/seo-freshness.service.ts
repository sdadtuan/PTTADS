import { Injectable } from '@nestjs/common';
import { SeoFreshnessRepository } from './seo-freshness.repository';
import { SeoFreshnessRow } from './seo-freshness.types';

@Injectable()
export class SeoFreshnessService {
  constructor(private readonly repo: SeoFreshnessRepository) {}

  listQueue(customerId: number, minPriority?: string): Promise<SeoFreshnessRow[]> {
    return this.repo.listQueue(customerId, { min_priority: minPriority });
  }

  scoreContent(customerId: number, contentId: number): Promise<{ ok: boolean; item: SeoFreshnessRow }> {
    return this.repo.scoreContent(customerId, contentId).then((item) => ({ ok: true, item }));
  }

  scoreAll(customerId: number): Promise<{ ok: boolean; scored: number }> {
    return this.repo.scoreAll(customerId).then((out) => ({ ok: true, ...out }));
  }

  flagRefresh(contentId: number): Promise<{ ok: boolean }> {
    return this.repo.flagRefresh(contentId);
  }
}
