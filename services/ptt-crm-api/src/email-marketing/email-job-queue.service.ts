import { Injectable } from '@nestjs/common';
import { AppConfigService } from '../config/app-config.service';
import { JobQueueRepository } from '../webhooks/job-queue.repository';

@Injectable()
export class EmailJobQueueService {
  private static readonly SYSTEM_CLIENT = '00000000-0000-0000-0000-000000000000';

  constructor(
    private readonly config: AppConfigService,
    private readonly jobQueue: JobQueueRepository,
  ) {}

  sendEnabled(): boolean {
    return this.config.emailSendEnabled;
  }

  async enqueueCampaignPrepare(campaignId: string, clientId: string): Promise<{ job_id: string | null; mode: string }> {
    if (!this.sendEnabled()) {
      return { job_id: null, mode: 'disabled' };
    }
    if (!this.config.jobsEnabled) {
      throw new Error('Job queue disabled (PTT_JOBS_ENABLED=0)');
    }
    const job = await this.jobQueue.enqueueEmailJob({
      jobType: 'email_campaign_prepare',
      payload: { campaign_id: campaignId, client_id: clientId },
      idempotencyKey: `email_prepare:${campaignId}`,
      clientId,
    });
    return { job_id: job.id, mode: 'queue' };
  }

  async enqueueSendBatch(campaignId: string, clientId: string): Promise<{ job_id: string | null }> {
    if (!this.sendEnabled() || !this.config.jobsEnabled) {
      return { job_id: null };
    }
    const job = await this.jobQueue.enqueueEmailJob({
      jobType: 'email_send_batch',
      payload: { campaign_id: campaignId, client_id: clientId },
      idempotencyKey: `email_send_batch:${campaignId}`,
      clientId,
    });
    return { job_id: job.id };
  }

  async enqueueClickhouseExport(params?: {
    factDate?: string;
    clientId?: string;
  }): Promise<{ job_id: string | null; mode: string }> {
    if (!this.config.jobsEnabled) {
      return { job_id: null, mode: 'disabled' };
    }
    const factDate = params?.factDate?.trim() || new Date().toISOString().slice(0, 10);
    const job = await this.jobQueue.enqueueEmailJob({
      jobType: 'email_clickhouse_export',
      payload: { fact_date: factDate, client_id: params?.clientId ?? null },
      idempotencyKey: `email_ch_export:${factDate}:${params?.clientId ?? 'all'}`,
      clientId: params?.clientId ?? EmailJobQueueService.SYSTEM_CLIENT,
    });
    return { job_id: job.id, mode: 'queue' };
  }

  async enqueueAttributionRollup(params?: {
    clientId?: string;
    metricDate?: string;
  }): Promise<{ job_id: string | null }> {
    if (!this.config.jobsEnabled) return { job_id: null };
    const metricDate = params?.metricDate?.trim() || new Date().toISOString().slice(0, 10);
    const job = await this.jobQueue.enqueueEmailJob({
      jobType: 'email_attribution_rollup',
      payload: { client_id: params?.clientId ?? null, metric_date: metricDate },
      idempotencyKey: `email_attrib:${metricDate}:${params?.clientId ?? 'all'}`,
      clientId: params?.clientId ?? EmailJobQueueService.SYSTEM_CLIENT,
    });
    return { job_id: job.id };
  }

  async enqueueDeliverabilityScan(hours = 24): Promise<{ job_id: string | null }> {
    if (!this.config.jobsEnabled) return { job_id: null };
    const job = await this.jobQueue.enqueueEmailJob({
      jobType: 'email_deliverability_scan',
      payload: { hours },
      idempotencyKey: `email_deliv_scan:${new Date().toISOString().slice(0, 13)}`,
      clientId: EmailJobQueueService.SYSTEM_CLIENT,
    });
    return { job_id: job.id };
  }

  async enqueueDnsVerify(domainId: string, clientId: string, actor: string): Promise<{ job_id: string | null }> {
    if (!this.config.jobsEnabled) return { job_id: null };
    const job = await this.jobQueue.enqueueEmailJob({
      jobType: 'email_dns_verify',
      payload: { domain_id: domainId, actor },
      idempotencyKey: `email_dns_verify:${domainId}:${new Date().toISOString().slice(0, 10)}`,
      clientId,
    });
    return { job_id: job.id };
  }

  async enqueueReportScheduleRun(scheduleId: string, clientId: string): Promise<{ job_id: string | null }> {
    if (!this.config.jobsEnabled) return { job_id: null };
    const job = await this.jobQueue.enqueueEmailJob({
      jobType: 'email_report_schedules',
      payload: { schedule_id: scheduleId, client_id: clientId },
      idempotencyKey: `email_report_run:${scheduleId}:${Date.now()}`,
      clientId,
    });
    return { job_id: job.id };
  }

  async enqueueDueReportSchedules(asOf?: string): Promise<{ job_id: string | null }> {
    if (!this.config.jobsEnabled) return { job_id: null };
    const day = asOf?.trim() || new Date().toISOString().slice(0, 10);
    const job = await this.jobQueue.enqueueEmailJob({
      jobType: 'email_report_schedules',
      payload: { as_of: day },
      idempotencyKey: `email_report_due:${day}`,
      clientId: EmailJobQueueService.SYSTEM_CLIENT,
    });
    return { job_id: job.id };
  }

  async enqueueExperimentRollup(experimentId: string, clientId: string): Promise<{ job_id: string | null }> {
    if (!this.config.jobsEnabled) return { job_id: null };
    const job = await this.jobQueue.enqueueEmailJob({
      jobType: 'email_experiment_rollup',
      payload: { experiment_id: experimentId },
      idempotencyKey: `email_experiment_rollup:${experimentId}:${new Date().toISOString().slice(0, 13)}`,
      clientId,
    });
    return { job_id: job.id };
  }
}
