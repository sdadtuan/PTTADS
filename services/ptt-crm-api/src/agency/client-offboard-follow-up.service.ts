import { Injectable, Logger } from '@nestjs/common';
import { TemporalClientService } from '../temporal/temporal-client.service';
import { JobQueueRepository } from '../webhooks/job-queue.repository';

export interface ClientOffboardFollowUpResult {
  jobs_cancelled: number;
  workflow_cancelled: boolean;
}

@Injectable()
export class ClientOffboardFollowUpService {
  private readonly logger = new Logger(ClientOffboardFollowUpService.name);

  constructor(
    private readonly jobQueue: JobQueueRepository,
    private readonly temporal: TemporalClientService,
  ) {}

  async run(clientId: string): Promise<ClientOffboardFollowUpResult> {
    const jobsCancelled = await this.jobQueue.cancelPendingJobsForClient(clientId);
    const workflowId = this.temporal.onboardingWorkflowId(clientId);
    const workflowCancelled = await this.temporal.cancelWorkflow(workflowId, 'client_offboarded');
    if (jobsCancelled > 0 || workflowCancelled) {
      this.logger.log(
        `offboard follow-up client=${clientId} jobs_cancelled=${jobsCancelled} workflow_cancelled=${workflowCancelled}`,
      );
    }
    return { jobs_cancelled: jobsCancelled, workflow_cancelled: workflowCancelled };
  }
}
