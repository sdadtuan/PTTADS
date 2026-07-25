import { Injectable } from '@nestjs/common';
import { SeoGovernanceRepository } from './seo-governance.repository';
import {
  SeoGovernanceComplianceSummary,
  SeoGovernanceEvaluateResult,
  SeoGovernancePolicyRow,
} from './seo-governance.types';
import { governanceEnabled } from './seo-governance.constants';

@Injectable()
export class SeoGovernanceService {
  constructor(private readonly repo: SeoGovernanceRepository) {}

  isEnabled(): boolean {
    return governanceEnabled();
  }

  listPolicies(customerId?: number | null): Promise<SeoGovernancePolicyRow[]> {
    return this.repo.listPolicies(customerId);
  }

  upsertPolicy(payload: Record<string, unknown>): Promise<SeoGovernancePolicyRow> {
    return this.repo.upsertPolicy(payload);
  }

  evaluateContent(contentId: number, action?: string): Promise<SeoGovernanceEvaluateResult> {
    return this.repo.evaluateContentPublish(contentId, action);
  }

  assertPublishAllowed(contentId: number, action?: string): Promise<void> {
    return this.repo.assertPublishAllowed(contentId, action);
  }

  recordOverride(params: {
    evaluationId: number;
    policyKey: string;
    actorId: string;
    reason: string;
  }) {
    return this.repo.recordOverride(params);
  }

  complianceSummary(customerId: number | null, days?: number): Promise<SeoGovernanceComplianceSummary> {
    return this.repo.complianceSummary(customerId, days);
  }
}
