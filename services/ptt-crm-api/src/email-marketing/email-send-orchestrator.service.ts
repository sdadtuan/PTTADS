import { Injectable, Logger } from '@nestjs/common';
import { EmailJobQueueService } from './email-job-queue.service';
import { TemporalEmailCampaignService } from './temporal-email-campaign.service';

@Injectable()
export class EmailSendOrchestratorService {
  private readonly logger = new Logger(EmailSendOrchestratorService.name);

  constructor(
    private readonly jobs: EmailJobQueueService,
    private readonly temporal: TemporalEmailCampaignService,
  ) {}

  async onCampaignSubmitted(params: {
    campaignId: string;
    clientId: string;
    campaignName: string;
    submittedBy: string;
  }): Promise<void> {
    await this.temporal.start(params);
  }

  async onCampaignApproved(params: {
    campaignId: string;
    clientId: string;
    reviewedBy: string;
    note?: string;
    scheduledAt?: string | null;
  }): Promise<{ prepare_job_id: string | null; temporal: string }> {
    if (params.scheduledAt) {
      const when = new Date(params.scheduledAt);
      if (!Number.isNaN(when.getTime()) && when.getTime() > Date.now()) {
        await this.temporal.signalApprove(params.campaignId, params.reviewedBy, params.note);
        return { prepare_job_id: null, temporal: 'scheduled' };
      }
    }
    const signal = await this.temporal.signalApprove(
      params.campaignId,
      params.reviewedBy,
      params.note,
    );
    if (signal === 'sent') {
      return { prepare_job_id: null, temporal: 'sent' };
    }
    this.logger.debug(
      `Temporal stub/skipped for campaign=${params.campaignId} — direct enqueue prepare`,
    );
    const out = await this.jobs.enqueueCampaignPrepare(params.campaignId, params.clientId);
    return { prepare_job_id: out.job_id, temporal: signal };
  }

  async staffApproveAndSend(params: {
    campaignId: string;
    clientId: string;
    reviewedBy: string;
  }): Promise<{ prepare_job_id: string | null }> {
    const out = await this.jobs.enqueueCampaignPrepare(params.campaignId, params.clientId);
    return { prepare_job_id: out.job_id };
  }

  async signalRejectOnly(campaignId: string, reviewedBy: string, note?: string): Promise<void> {
    await this.temporal.signalReject(campaignId, reviewedBy, note);
  }
}
