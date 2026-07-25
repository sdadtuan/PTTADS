import { Injectable } from '@nestjs/common';
import { SeoAuthorityRepository } from './seo-authority.repository';
import { SeoAuthoritySignalRow, SeoAuthoritySummary } from './seo-authority.types';

@Injectable()
export class SeoAuthorityService {
  constructor(private readonly repo: SeoAuthorityRepository) {}

  listSignals(
    customerId: number,
    params?: { signal_type?: string; status?: string },
  ): Promise<SeoAuthoritySignalRow[]> {
    return this.repo.listSignals(customerId, params);
  }

  addSignal(customerId: number, body: Record<string, unknown>): Promise<SeoAuthoritySignalRow> {
    return this.repo.addSignal(customerId, body);
  }

  importCsv(
    customerId: number,
    csvText: string,
    signalType: string,
  ): Promise<{ ok: boolean; imported: number; skipped: number }> {
    return this.repo.importCsv(customerId, csvText, signalType).then((out) => ({ ok: true, ...out }));
  }

  summary(customerId: number): Promise<SeoAuthoritySummary> {
    return this.repo.summary(customerId);
  }
}
