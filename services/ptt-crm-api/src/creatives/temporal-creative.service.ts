import { Injectable, Logger } from '@nestjs/common';
import { TemporalClientService, TemporalSignalResult } from '../temporal/temporal-client.service';

export interface CreativeSignalPayload {
  creativeId: string;
  clientId: string;
  version: number;
  decision: 'approved' | 'rejected';
  reviewedBy: string;
  note?: string | null;
  workflowId?: string | null;
}

export interface StartCreativeWorkflowInput {
  creativeId: string;
  clientId: string;
  title: string;
  version: number;
  submittedBy: string;
}

@Injectable()
export class TemporalCreativeService {
  private readonly logger = new Logger(TemporalCreativeService.name);

  constructor(private readonly temporal: TemporalClientService) {}

  isEnabled(): boolean {
    return this.temporal.isEnabled();
  }

  workflowIdForCreative(creativeId: string): string {
    return this.temporal.creativeWorkflowId(creativeId);
  }

  async startCreativeWorkflow(input: StartCreativeWorkflowInput) {
    const workflowId = this.workflowIdForCreative(input.creativeId);
    const result = await this.temporal.startWorkflow('CreativeApprovalWorkflow', workflowId, [
      {
        creative_id: input.creativeId,
        client_id: input.clientId,
        title: input.title,
        version: input.version,
        submitted_by: input.submittedBy,
      },
    ]);
    return {
      workflowId: result.workflowId,
      runId: result.runId,
      started: result.started,
    };
  }

  async signalDecision(payload: CreativeSignalPayload): Promise<TemporalSignalResult> {
    if (!this.temporal.isEnabled()) {
      this.logger.debug(`Temporal stub: ${payload.decision} creative=${payload.creativeId}`);
      return 'stub';
    }
    const workflowId =
      payload.workflowId?.trim() || this.workflowIdForCreative(payload.creativeId);
    const signalPayload = {
      reviewed_by: payload.reviewedBy,
      note: payload.note ?? null,
    };
    const signalName = payload.decision === 'approved' ? 'approve_creative' : 'reject_creative';
    return this.temporal.signalWorkflow(workflowId, signalName, signalPayload);
  }
}
