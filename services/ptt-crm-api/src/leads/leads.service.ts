import { Injectable } from '@nestjs/common';
import { LeadV1, ListLeadsQuery } from './leads.types';
import { LeadsRepository } from './leads.repository';

@Injectable()
export class LeadsService {
  constructor(private readonly repo: LeadsRepository) {}

  async listLeads(query: ListLeadsQuery): Promise<{ leads: LeadV1[]; total: number; limit: number; offset: number }> {
    const limit = Math.max(1, Math.min(Number(query.limit ?? 50), 200));
    const offset = Math.max(0, Number(query.offset ?? 0));
    const result = await this.repo.listLeads({ ...query, limit, offset });
    return { ...result, limit, offset };
  }

  async getLead(id: number): Promise<LeadV1 | null> {
    return this.repo.getLeadById(id);
  }
}
