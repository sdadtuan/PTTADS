import { Injectable } from '@nestjs/common';
import { TemporalClientService, TemporalSignalResult } from '../temporal/temporal-client.service';

@Injectable()
export class TemporalEmailCampaignService {
  constructor(private readonly temporal: TemporalClientService) {}

  workflowId(campaignId: string): string {
    return this.temporal.emailCampaignWorkflowId(campaignId);
  }

  async start(request: {
    campaignId: string;
    clientId: string;
    campaignName: string;
    submittedBy: string;
  }) {
    return this.temporal.startWorkflow('EmailCampaignApprovalWorkflow', this.workflowId(request.campaignId), [
      {
        campaign_id: request.campaignId,
        client_id: request.clientId,
        campaign_name: request.campaignName,
        submitted_by: request.submittedBy,
      },
    ]);
  }

  async signalApprove(campaignId: string, reviewedBy: string, note?: string): Promise<TemporalSignalResult> {
    return this.temporal.signalWorkflow(this.workflowId(campaignId), 'approve_campaign', {
      reviewed_by: reviewedBy,
      note: note ?? '',
    });
  }

  async signalReject(campaignId: string, reviewedBy: string, note?: string): Promise<TemporalSignalResult> {
    return this.temporal.signalWorkflow(this.workflowId(campaignId), 'reject_campaign', {
      reviewed_by: reviewedBy,
      note: note ?? '',
    });
  }
}
