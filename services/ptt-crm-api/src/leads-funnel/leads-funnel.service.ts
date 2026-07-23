import { Injectable, NotFoundException } from '@nestjs/common';
import { AppConfigService } from '../config/app-config.service';
import { StaffAuthService } from '../staff-auth/staff-auth.service';
import { StaffJwtPayload } from '../staff-auth/staff-jwt.util';
import {
  AdvancePresalesBody,
  CompleteCareStageBody,
  EnsurePresalesBody,
  LeadFunnelSnapshot,
  PatchMarketingPlanBody,
  PatchPresalesTaskBody,
  ReleaseReviewQueueBody,
} from './leads-funnel.types';
import { LeadsFunnelSqliteRepository } from './leads-funnel-sqlite.repository';
import { validatePreliminaryPlan } from './presales-marketing-plan.util';
import { reviewQueuePublicState } from './review-queue.util';
import { parseLeadMeta } from './care-pipeline.util';

@Injectable()
export class LeadsFunnelService {
  constructor(
    private readonly repo: LeadsFunnelSqliteRepository,
    private readonly config: AppConfigService,
    private readonly staffAuth: StaffAuthService,
  ) {}

  getFunnel(leadId: number): LeadFunnelSnapshot {
    const snap = this.repo.buildSnapshot(leadId, this.config.presalesOnLead);
    if (!snap) throw new NotFoundException({ error: 'Lead not found' });
    return snap;
  }

  getCarePipeline(leadId: number) {
    const snap = this.getFunnel(leadId);
    return { ok: true, ...snap.care_pipeline, presales_care_gate: snap.presales_care_gate };
  }

  submitCareReport(
    leadId: number,
    body: CompleteCareStageBody,
    actor: string,
    userId: number | null,
  ) {
    this.repo.submitCareReport(leadId, body, actor, userId);
    return { ok: true, funnel: this.getFunnel(leadId) };
  }

  completeCareStage(leadId: number, body: CompleteCareStageBody, actor: string) {
    try {
      this.repo.completeCareStage(leadId, body, actor);
    } catch (err) {
      throw new Error(err instanceof Error ? err.message : String(err));
    }
    return { ok: true, funnel: this.getFunnel(leadId) };
  }

  reviewQueueCount(): { count: number } {
    return { count: this.repo.countReviewQueue() };
  }

  listReviewQueue(limit?: number) {
    const rows = this.repo.listReviewQueue(limit);
    return {
      leads: rows.map((row) => ({
        id: row.id,
        full_name: row.full_name,
        phone: row.phone,
        status: row.status,
        review_queue: reviewQueuePublicState(parseLeadMeta(row.meta_json), row.first_assigned_at || ''),
      })),
      total: rows.length,
    };
  }

  syncReviewQueue(actor: string, dryRun = false) {
    return this.repo.syncReviewQueue(actor, dryRun);
  }

  releaseReviewQueue(leadId: number, body: ReleaseReviewQueueBody, actor: string) {
    try {
      this.repo.releaseFromReviewQueue(leadId, body, actor);
    } catch (err) {
      throw new Error(err instanceof Error ? err.message : String(err));
    }
    return { ok: true, funnel: this.getFunnel(leadId) };
  }

  getPresales(leadId: number) {
    const snap = this.getFunnel(leadId);
    return { ok: true, presales: snap.presales };
  }

  ensurePresales(leadId: number, body: EnsurePresalesBody, actor: string) {
    try {
      this.repo.ensurePresales(leadId, body.service_slug, actor);
    } catch (err) {
      throw new Error(err instanceof Error ? err.message : String(err));
    }
    return { ok: true, funnel: this.getFunnel(leadId) };
  }

  advancePresales(leadId: number, body: AdvancePresalesBody, allowOverride = false) {
    try {
      this.repo.advancePresales(leadId, {
        confirm: Boolean(body.confirm),
        overrideReason: body.override_reason,
        allowOverride,
      });
    } catch (err) {
      throw new Error(err instanceof Error ? err.message : String(err));
    }
    return { ok: true, funnel: this.getFunnel(leadId) };
  }

  async staffHasAssignCap(staffUser: StaffJwtPayload): Promise<boolean> {
    const me = await this.staffAuth.me(staffUser);
    return this.staffAuth.hasCap(me.caps, 'crm_leads', 'assign');
  }

  patchPresalesTask(
    leadId: number,
    taskId: number,
    body: PatchPresalesTaskBody,
    doneBy: number | null,
  ) {
    this.repo.updatePresalesTask(taskId, body, doneBy);
    return { ok: true, funnel: this.getFunnel(leadId) };
  }

  getMarketingPlan(leadId: number) {
    const snap = this.repo.getPresalesSnapshot(leadId);
    if (!snap) throw new NotFoundException({ error: 'No presales for lead' });
    const plan = this.repo.getOrCreatePreliminaryPlan(
      leadId,
      snap.presales.id,
      snap.presales.service_slug,
    );
    const validation = validatePreliminaryPlan(plan);
    return { ok: true, plan, validation };
  }

  patchMarketingPlan(leadId: number, body: PatchMarketingPlanBody) {
    const plan = this.repo.patchMarketingPlan(leadId, body);
    const validation = validatePreliminaryPlan(plan);
    return { ok: true, plan, validation, funnel: this.getFunnel(leadId) };
  }
}
