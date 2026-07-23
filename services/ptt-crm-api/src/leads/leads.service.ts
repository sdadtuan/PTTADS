import { Injectable } from '@nestjs/common';
import { AppConfigService } from '../config/app-config.service';
import { LeadV1, ListLeadsQuery, ReviewQueueListFilter } from './leads.types';
import { LeadsRepository } from './leads.repository';

@Injectable()
export class LeadsService {
  constructor(
    private readonly repo: LeadsRepository,
    private readonly config: AppConfigService,
  ) {}

  async listLeads(query: ListLeadsQuery): Promise<{ leads: LeadV1[]; total: number; limit: number; offset: number }> {
    const limit = Math.max(1, Math.min(Number(query.limit ?? 50), 200));
    const offset = Math.max(0, Number(query.offset ?? 0));
    const reviewQueueFilter = this.resolveReviewQueueFilter(query);
    const result = await this.repo.listLeads({ ...query, limit, offset, review_queue_filter: reviewQueueFilter });
    return { ...result, limit, offset };
  }

  async getLead(id: number): Promise<LeadV1 | null> {
    return this.repo.getLeadById(id);
  }

  private resolveReviewQueueFilter(query: ListLeadsQuery): ReviewQueueListFilter | undefined {
    if (!this.config.crmLeadsFunnelNest) return undefined;
    if (query.review_queue_only) return 'only';
    if (query.hide_review_queue === false) return undefined;
    return 'hide';
  }
}
