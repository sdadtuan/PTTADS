import { Injectable, Optional } from '@nestjs/common';
import { AppConfigService } from '../config/app-config.service';
import { LeadsFunnelSqliteRepository } from '../leads-funnel/leads-funnel-sqlite.repository';
import { PgLeadsRepository } from './pg-leads.repository';
import { SqliteLeadsRepository } from './sqlite-leads.repository';
import { LeadV1, ListLeadsQuery } from './leads.types';

@Injectable()
export class LeadsRepository {
  constructor(
    private readonly config: AppConfigService,
    private readonly sqliteRepo: SqliteLeadsRepository,
    private readonly pgRepo: PgLeadsRepository,
    @Optional() private readonly funnelRepo?: LeadsFunnelSqliteRepository,
  ) {}

  useSqliteDatabasePath(dbPath: string): void {
    this.sqliteRepo.useDatabasePath(dbPath);
  }

  listLeads(query: ListLeadsQuery): Promise<{ leads: LeadV1[]; total: number }> | { leads: LeadV1[]; total: number } {
    const enriched = this.withReviewQueueFilter(query);
    if (this.config.leadsReadSource === 'pg') {
      return this.pgRepo.listLeads(enriched);
    }
    return this.sqliteRepo.listLeads(enriched);
  }

  getLeadById(leadId: number): Promise<LeadV1 | null> | LeadV1 | null {
    if (this.config.leadsReadSource === 'pg') {
      return this.pgRepo.getLeadById(leadId);
    }
    return this.sqliteRepo.getLeadById(leadId);
  }

  private withReviewQueueFilter(query: ListLeadsQuery): ListLeadsQuery {
    const filter = query.review_queue_filter;
    if (!filter || !this.config.crmLeadsFunnelNest || !this.funnelRepo) {
      return query;
    }
    if (this.config.leadsReadSource === 'pg') {
      return { ...query, review_queue_ids: this.funnelRepo.listReviewQueueLeadIds() };
    }
    return query;
  }
}
