import { Injectable } from '@nestjs/common';
import { SeoStrategyRepository } from './seo-strategy.repository';

@Injectable()
export class SeoStrategyService {
  constructor(private readonly repo: SeoStrategyRepository) {}

  okrTree(customerId: number) {
    return this.repo.okrTree(customerId);
  }

  createGoal(customerId: number, payload: Record<string, unknown>) {
    return this.repo.createGoal(customerId, payload);
  }

  createKpi(customerId: number, payload: Record<string, unknown>) {
    return this.repo.createKpi(customerId, payload);
  }

  updateKpi(customerId: number, kpiId: number, payload: Record<string, unknown>) {
    return this.repo.updateKpi(customerId, kpiId, payload);
  }

  linkInitiative(customerId: number, initiativeId: number, goalId: number | null) {
    return this.repo.linkInitiative(customerId, initiativeId, goalId);
  }

  refreshKpis(customerId: number) {
    return this.repo.refreshKpiMetrics(customerId).then((updated) => ({ ok: true, updated }));
  }
}
