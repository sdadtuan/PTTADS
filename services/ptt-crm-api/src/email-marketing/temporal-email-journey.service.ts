import { Injectable } from '@nestjs/common';
import { TemporalClientService } from '../temporal/temporal-client.service';

@Injectable()
export class TemporalEmailJourneyService {
  constructor(private readonly temporal: TemporalClientService) {}

  workflowId(journeyId: string): string {
    return this.temporal.emailJourneyWorkflowId(journeyId);
  }

  async start(request: {
    journeyId: string;
    clientId: string;
    journeyName: string;
    activatedBy: string;
  }) {
    return this.temporal.startWorkflow('EmailJourneyWorkflow', this.workflowId(request.journeyId), [
      {
        journey_id: request.journeyId,
        client_id: request.clientId,
        journey_name: request.journeyName,
        activated_by: request.activatedBy,
      },
    ]);
  }

  async signalPause(journeyId: string, note?: string) {
    return this.temporal.signalWorkflow(this.workflowId(journeyId), 'pause_journey', { note: note ?? '' });
  }

  async signalStop(journeyId: string, note?: string) {
    return this.temporal.signalWorkflow(this.workflowId(journeyId), 'stop_journey', { note: note ?? '' });
  }
}
