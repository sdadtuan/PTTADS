import {
  BadRequestException,
  Injectable,
  NotFoundException,
  ServiceUnavailableException,
} from '@nestjs/common';
import { DomainEventService } from '../events/domain-event.service';
import { CampaignWritesRepository } from './campaign-writes.repository';
import {
  ApproveCampaignWriteBody,
  SubmitCampaignWriteBody,
} from './campaign-writes.types';
import { TemporalCampaignWriteService } from './temporal-campaign-write.service';

@Injectable()
export class CampaignWritesService {
  constructor(
    private readonly repo: CampaignWritesRepository,
    private readonly temporal: TemporalCampaignWriteService,
    private readonly events: DomainEventService,
  ) {}

  async submit(body: SubmitCampaignWriteBody) {
    if (!(await this.repo.tableReady())) {
      throw new ServiceUnavailableException({ error: 'campaign_write_table_not_ready' });
    }
    const clientId = body.client_id?.trim();
    const campaignId = body.external_campaign_id?.trim();
    if (!clientId || !campaignId) {
      throw new BadRequestException({ error: 'client_id and external_campaign_id required' });
    }
    if (!body.new_value || typeof body.new_value !== 'object') {
      throw new BadRequestException({ error: 'new_value required' });
    }
    const submittedBy = body.submitted_by?.trim() || 'am@pttads.vn';
    const changeType = body.change_type ?? 'daily_budget';
    const channel = (body.channel ?? 'meta').trim().toLowerCase();

    const row = await this.repo.insertRequest({
      clientId,
      channel,
      externalAccountId: body.external_account_id?.trim() || null,
      externalCampaignId: campaignId,
      externalCampaignName: body.external_campaign_name?.trim() || null,
      changeType,
      oldValue: body.old_value ?? {},
      newValue: body.new_value,
      submittedBy,
      workflowId: null,
      runId: null,
    });

    const wf = await this.temporal.start({
      requestId: row.id,
      clientId,
      externalCampaignId: campaignId,
      changeType,
      newValue: body.new_value,
      submittedBy,
    });
    const linked = await this.repo.updateTemporalMeta(row.id, wf.workflowId, wf.runId);

    await this.events.emit(
      'CampaignWriteSubmitted',
      'campaign_write',
      row.id,
      { change_type: changeType, new_value: body.new_value },
      row.client_id,
      `campaign-write:${row.id}:submitted`,
    );

    return {
      ok: true,
      request: linked ?? row,
      workflow_id: wf.workflowId,
      workflow_started: wf.started,
      temporal_run_id: wf.runId,
      temporal_signal: wf.started ? 'sent' : 'stub',
    };
  }

  async listPending(clientId?: string) {
    if (!(await this.repo.tableReady())) {
      throw new ServiceUnavailableException({ error: 'campaign_write_table_not_ready' });
    }
    const rows = await this.repo.listPending(clientId?.trim());
    return { ok: true, count: rows.length, rows };
  }

  async approve(id: string, body: ApproveCampaignWriteBody) {
    const row = await this.repo.findById(id.trim());
    if (!row) {
      throw new NotFoundException({ error: 'not_found' });
    }
    if (row.status !== 'pending_approval') {
      throw new BadRequestException({ error: 'not_pending' });
    }
    const approvedBy = body.approved_by?.trim() || 'admin@pttads.vn';
    const updated = await this.repo.markApproved(id, approvedBy, body.note?.trim() || null);
    if (!updated) {
      throw new BadRequestException({ error: 'approve_failed' });
    }
    const signal = await this.temporal.signalApprove(id, approvedBy, body.note);
    await this.events.emit(
      'CampaignWriteApproved',
      'campaign_write',
      id,
      { change_type: row.change_type, new_value: row.new_value },
      row.client_id,
      `campaign-write:${id}:approved`,
    );
    return { ok: true, request: updated, temporal_signal: signal };
  }

  async reject(id: string, body: ApproveCampaignWriteBody) {
    const row = await this.repo.findById(id.trim());
    if (!row) {
      throw new NotFoundException({ error: 'not_found' });
    }
    if (row.status !== 'pending_approval') {
      throw new BadRequestException({ error: 'not_pending' });
    }
    const approvedBy = body.approved_by?.trim() || 'admin@pttads.vn';
    const updated = await this.repo.markRejected(id, approvedBy, body.note?.trim() || null);
    if (!updated) {
      throw new BadRequestException({ error: 'reject_failed' });
    }
    const signal = await this.temporal.signalReject(id, approvedBy, body.note);
    return { ok: true, request: updated, temporal_signal: signal };
  }
}
