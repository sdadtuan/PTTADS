import { Injectable } from '@nestjs/common';
import { AppConfigService } from '../config/app-config.service';
import { PgLeadsRepository } from './pg-leads.repository';
import { SqliteLeadsRepository } from './sqlite-leads.repository';
import { LeadV1, ListLeadsQuery } from './leads.types';

@Injectable()
export class LeadsRepository {
  constructor(
    private readonly config: AppConfigService,
    private readonly sqliteRepo: SqliteLeadsRepository,
    private readonly pgRepo: PgLeadsRepository,
  ) {}

  useSqliteDatabasePath(dbPath: string): void {
    this.sqliteRepo.useDatabasePath(dbPath);
  }

  listLeads(query: ListLeadsQuery): Promise<{ leads: LeadV1[]; total: number }> | { leads: LeadV1[]; total: number } {
    if (this.config.leadsReadSource === 'pg') {
      return this.pgRepo.listLeads(query);
    }
    return this.sqliteRepo.listLeads(query);
  }

  getLeadById(leadId: number): Promise<LeadV1 | null> | LeadV1 | null {
    if (this.config.leadsReadSource === 'pg') {
      return this.pgRepo.getLeadById(leadId);
    }
    return this.sqliteRepo.getLeadById(leadId);
  }
}
