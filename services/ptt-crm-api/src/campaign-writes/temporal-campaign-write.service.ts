import { Injectable } from '@nestjs/common';
import { TemporalClientService } from '../temporal/temporal-client.service';

@Injectable()
export class TemporalCampaignWriteService {
  constructor(private readonly temporal: TemporalClientService) {}

  workflowId(requestId: string): string {
    return this.temporal.campaignWriteWorkflowId(requestId);
  }

  async start(request: {
    requestId: string;
    clientId: string;
    externalCampaignId: string;
    changeType: string;
    newValue: Record<string, unknown>;
    submittedBy: string;
  }) {
    const workflowId = this.workflowId(request.requestId);
    return this.temporal.startWorkflow('CampaignWriteApprovalWorkflow', workflowId, [
      {
        request_id: request.requestId,
        client_id: request.clientId,
        external_campaign_id: request.externalCampaignId,
        change_type: request.changeType,
        new_value: request.newValue,
        submitted_by: request.submittedBy,
      },
    ]);
  }

  async signalApprove(requestId: string, approvedBy: string, note?: string) {
    return this.temporal.signalWorkflow(this.workflowId(requestId), 'approve_write', {
      approved_by: approvedBy,
      note: note ?? '',
    });
  }

  async signalReject(requestId: string, approvedBy: string, note?: string) {
    return this.temporal.signalWorkflow(this.workflowId(requestId), 'reject_write', {
      approved_by: approvedBy,
      note: note ?? '',
    });
  }
}
