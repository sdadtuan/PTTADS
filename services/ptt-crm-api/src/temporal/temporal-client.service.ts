import { Injectable, Logger, OnModuleDestroy } from '@nestjs/common';
import { Connection, Client, WorkflowHandle } from '@temporalio/client';
import { AppConfigService } from '../config/app-config.service';

export type TemporalSignalResult = 'sent' | 'stub' | 'skipped';

@Injectable()
export class TemporalClientService implements OnModuleDestroy {
  private readonly logger = new Logger(TemporalClientService.name);
  private connection: Connection | null = null;
  private client: Client | null = null;

  constructor(private readonly config: AppConfigService) {}

  onModuleDestroy(): void {
    void this.connection?.close();
    this.connection = null;
    this.client = null;
  }

  isEnabled(): boolean {
    return Boolean(this.config.temporalAddress);
  }

  onboardingWorkflowId(clientId: string): string {
    return `client-onboarding-${clientId}`;
  }

  launchQaWorkflowId(runId: string): string {
    return `launch-qa-${runId}`;
  }

  creativeWorkflowId(creativeId: string): string {
    return `creative-approval-${creativeId}`;
  }

  campaignWriteWorkflowId(requestId: string): string {
    return `campaign-write-${requestId}`;
  }

  emailCampaignWorkflowId(campaignId: string): string {
    return `email-campaign-${campaignId}`;
  }

  emailJourneyWorkflowId(journeyId: string): string {
    return `email-journey-${journeyId}`;
  }

  async startWorkflow(
    workflowType: string,
    workflowId: string,
    args: unknown[],
  ): Promise<{ workflowId: string; runId: string | null; started: boolean }> {
    if (!this.isEnabled()) {
      this.logger.debug(`Temporal stub start ${workflowType} id=${workflowId}`);
      return { workflowId, runId: null, started: false };
    }
    try {
      const temporal = await this.getClient();
      const handle = await temporal.workflow.start(workflowType, {
        taskQueue: this.config.temporalTaskQueue,
        workflowId,
        args,
      });
      return { workflowId, runId: handle.firstExecutionRunId ?? null, started: true };
    } catch (err) {
      const message = err instanceof Error ? err.message : String(err);
      if (message.includes('already started') || message.includes('Workflow execution already started')) {
        return { workflowId, runId: null, started: false };
      }
      this.logger.warn(`Temporal start failed ${workflowType}: ${message}`);
      return { workflowId, runId: null, started: false };
    }
  }

  async signalWorkflow(
    workflowId: string,
    signalName: string,
    payload: Record<string, unknown>,
  ): Promise<TemporalSignalResult> {
    if (!this.isEnabled()) {
      return 'stub';
    }
    try {
      const temporal = await this.getClient();
      const handle: WorkflowHandle = temporal.workflow.getHandle(workflowId);
      await handle.signal(signalName, payload);
      return 'sent';
    } catch (err) {
      this.logger.warn(
        `Temporal signal ${signalName} failed wf=${workflowId}: ${err instanceof Error ? err.message : err}`,
      );
      return 'skipped';
    }
  }

  async cancelWorkflow(workflowId: string, reason = 'client_offboarded'): Promise<boolean> {
    if (!this.isEnabled()) {
      return false;
    }
    try {
      const temporal = await this.getClient();
      const handle: WorkflowHandle = temporal.workflow.getHandle(workflowId);
      await handle.cancel();
      this.logger.log(`Temporal cancel wf=${workflowId} reason=${reason}`);
      return true;
    } catch (err) {
      this.logger.debug(
        `Temporal cancel skipped wf=${workflowId}: ${err instanceof Error ? err.message : err}`,
      );
      return false;
    }
  }

  async describeWorkflow(workflowId: string): Promise<{
    workflow_id: string;
    status: string;
    run_id: string | null;
    found: boolean;
  }> {
    if (!this.isEnabled()) {
      return { workflow_id: workflowId, status: 'stub', run_id: null, found: false };
    }
    try {
      const temporal = await this.getClient();
      const handle = temporal.workflow.getHandle(workflowId);
      const desc = await handle.describe();
      return {
        workflow_id: workflowId,
        status: String(desc.status?.name ?? 'UNKNOWN'),
        run_id: desc.runId ?? null,
        found: true,
      };
    } catch (err) {
      this.logger.debug(
        `Temporal describe failed wf=${workflowId}: ${err instanceof Error ? err.message : err}`,
      );
      return { workflow_id: workflowId, status: 'NOT_FOUND', run_id: null, found: false };
    }
  }

  private async getClient(): Promise<Client> {
    if (this.client) {
      return this.client;
    }
    const address = this.config.temporalAddress;
    if (!address) {
      throw new Error('Temporal not configured');
    }
    this.connection = await Connection.connect({ address });
    this.client = new Client({
      connection: this.connection,
      namespace: this.config.temporalNamespace,
    });
    return this.client;
  }
}
