import {
  BadRequestException,
  ConflictException,
  ForbiddenException,
  Injectable,
  NotFoundException,
  ServiceUnavailableException,
} from '@nestjs/common';
import { DomainEventService } from '../events/domain-event.service';
import {
  creativeApprovedIdempotencyKey,
  creativeRejectedIdempotencyKey,
} from '../events/event-idempotency';
import { PortalJwtPayload } from '../portal/portal-jwt.util';
import { CreativesRepository } from './creatives.repository';
import {
  CreateCreativeBody,
  CreateCreativeResponse,
  CreativeDecisionResponse,
  CreativePendingResponse,
} from './creatives.types';
import { TemporalCreativeService } from './temporal-creative.service';

@Injectable()
export class CreativesService {
  constructor(
    private readonly repo: CreativesRepository,
    private readonly events: DomainEventService,
    private readonly temporal: TemporalCreativeService,
  ) {}

  async listPending(clientId: string): Promise<CreativePendingResponse> {
    await this.ensureReady();
    const rows = await this.repo.listPending(clientId);
    return { ok: true, client_id: clientId, count: rows.length, rows };
  }

  async submit(body: CreateCreativeBody): Promise<CreateCreativeResponse> {
    await this.ensureReady();
    const clientId = body.client_id?.trim();
    const title = body.title?.trim();
    if (!clientId || !title) {
      throw new BadRequestException({ error: 'client_id and title required' });
    }
    if (!(await this.repo.clientExists(clientId))) {
      throw new NotFoundException({ error: 'client_not_found' });
    }

    const version = Math.max(1, Number(body.version) || 1);
    const submittedBy = body.submitted_by?.trim() || 'am@pttads.vn';
    const creative = await this.repo.create({
      clientId,
      title,
      description: body.description?.trim() || null,
      externalCampaignId: body.external_campaign_id?.trim() || null,
      externalCampaignName: body.external_campaign_name?.trim() || null,
      version,
      assetUrl: body.asset_url?.trim() || null,
      assetType: body.asset_type?.trim() || 'image',
      submittedBy,
    });

    const wf = await this.temporal.startCreativeWorkflow({
      creativeId: creative.id,
      clientId,
      title,
      version,
      submittedBy,
    });

    const linked = await this.repo.updateTemporalMeta(creative.id, wf.workflowId, wf.runId);
    return {
      ok: true,
      creative: linked ?? creative,
      workflow_id: wf.workflowId,
      workflow_started: wf.started,
      temporal_run_id: wf.runId,
    };
  }

  async approve(user: PortalJwtPayload, creativeId: string): Promise<CreativeDecisionResponse> {
    this.assertApprover(user);
    return this.decide(user, creativeId, 'approved', null);
  }

  async reject(
    user: PortalJwtPayload,
    creativeId: string,
    note?: string,
  ): Promise<CreativeDecisionResponse> {
    this.assertApprover(user);
    return this.decide(user, creativeId, 'rejected', note?.trim() || null);
  }

  private async decide(
    user: PortalJwtPayload,
    creativeId: string,
    decision: 'approved' | 'rejected',
    note: string | null,
  ): Promise<CreativeDecisionResponse> {
    await this.ensureReady();
    const existing = await this.repo.findById(creativeId);
    if (!existing) {
      throw new NotFoundException({ error: 'Not found' });
    }
    if (existing.client_id !== user.client_id) {
      throw new ForbiddenException({ error: 'client_id_mismatch' });
    }
    if (existing.status !== 'pending_client') {
      throw new ConflictException({ error: 'creative_not_pending', status: existing.status });
    }

    const updated = await this.repo.updateDecision(
      creativeId,
      decision,
      user.email,
      note,
    );
    if (!updated) {
      throw new ConflictException({ error: 'creative_not_pending' });
    }

    const eventType = decision === 'approved' ? 'CreativeApproved' : 'CreativeRejected';
    const idempotencyKey =
      decision === 'approved'
        ? creativeApprovedIdempotencyKey(creativeId, updated.version)
        : creativeRejectedIdempotencyKey(creativeId, updated.version);

    const eventId = await this.events.emit(
      eventType,
      'creative',
      creativeId,
      {
        creative_id: creativeId,
        client_id: user.client_id,
        version: updated.version,
        reviewed_by: user.email,
        review_note: note,
        external_campaign_id: updated.external_campaign_id,
      },
      user.sub,
      idempotencyKey,
    );

    const temporalSignal = await this.temporal.signalDecision({
      creativeId,
      clientId: user.client_id,
      version: updated.version,
      decision,
      reviewedBy: user.email,
      note,
      workflowId: updated.temporal_workflow_id,
    });

    return {
      ok: true,
      creative: updated,
      event_id: eventId,
      temporal_signal: temporalSignal,
    };
  }

  private assertApprover(user: PortalJwtPayload): void {
    if (user.role !== 'approver') {
      throw new ForbiddenException({ error: 'approver_role_required' });
    }
  }

  private async ensureReady(): Promise<void> {
    if (!(await this.repo.pgCreativesReady())) {
      throw new ServiceUnavailableException({ ok: false, error: 'creatives_tables_not_ready' });
    }
  }
}
