import { Injectable, Logger } from '@nestjs/common';
import { DomainEventService } from '../events/domain-event.service';
import { EnqueuedJob, JobQueueRepository } from '../webhooks/job-queue.repository';
import { WorkflowsService } from '../workflows/workflows.service';

export interface AgencySideEffectsSummary {
  domain_event_id: string | null;
  jobs_enqueued: EnqueuedJob[];
  workflow_signal?: string;
}

@Injectable()
export class AgencySideEffectsService {
  private readonly logger = new Logger(AgencySideEffectsService.name);

  constructor(
    private readonly events: DomainEventService,
    private readonly workflows: WorkflowsService,
    private readonly jobQueue: JobQueueRepository,
  ) {}

  async onClientCreated(clientId: string, startedBy?: string): Promise<void> {
    try {
      const out = await this.workflows.startOnboarding({
        client_id: clientId,
        started_by: startedBy,
      });
      this.logger.log(
        `onboarding workflow client=${clientId} started=${out.workflow_started} signal=${out.temporal_signal}`,
      );
    } catch (err) {
      this.logger.warn(`onboarding start skipped client=${clientId}: ${String(err)}`);
    }
  }

  async onOnboardingPatched(clientId: string): Promise<string | undefined> {
    try {
      const out = await this.workflows.nudgeOnboarding(clientId);
      return out.temporal_signal;
    } catch (err) {
      this.logger.debug(`onboarding nudge skipped client=${clientId}: ${String(err)}`);
      return undefined;
    }
  }

  async onClientActivated(clientId: string, clientCode: string): Promise<AgencySideEffectsSummary> {
    const domainEventId = await this.events.emit('ClientOnboarded', 'client', clientId, {
      client_id: clientId,
      client_code: clientCode,
    });
    const jobs = await this.enqueueMetaInsightsSync(clientId);
    let workflowSignal: string | undefined;
    try {
      const nudge = await this.workflows.nudgeOnboarding(clientId);
      workflowSignal = nudge.temporal_signal;
    } catch {
      // optional
    }
    return {
      domain_event_id: domainEventId,
      jobs_enqueued: jobs,
      workflow_signal: workflowSignal,
    };
  }

  async onClientOffboarded(
    clientId: string,
    payload: Record<string, unknown>,
  ): Promise<string | null> {
    return this.events.emit(
      'ClientOffboarded',
      'client',
      clientId,
      payload,
      String(payload.initiated_by ?? 'system'),
      `client:${clientId}:offboarded`,
    );
  }

  async enqueueMetaInsightsSync(
    clientId: string,
    targetDate?: string,
  ): Promise<EnqueuedJob[]> {
    const dateKey = targetDate?.trim() || new Date().toISOString().slice(0, 10);
    const job = await this.jobQueue.enqueueAgencyJob({
      jobType: 'meta_insights_sync',
      payload: {
        client_id: clientId,
        compute_metrics: true,
        target_date: dateKey,
      },
      idempotencyKey: `meta_insights_sync:${clientId}:${dateKey}`,
      clientId,
    });
    return job ? [job] : [];
  }

  async enqueueGoogleInsightsSync(
    clientId: string,
    targetDate?: string,
  ): Promise<EnqueuedJob[]> {
    const dateKey = targetDate?.trim() || new Date().toISOString().slice(0, 10);
    const job = await this.jobQueue.enqueueAgencyJob({
      jobType: 'google_insights_sync',
      payload: {
        client_id: clientId,
        compute_metrics: true,
        target_date: dateKey,
      },
      idempotencyKey: `google_insights_sync:${clientId}:${dateKey}`,
      clientId,
    });
    return job ? [job] : [];
  }
}
