import { Injectable } from '@nestjs/common';
import { AppConfigService } from '../config/app-config.service';
import { TemporalClientService } from '../temporal/temporal-client.service';
import { shouldReuseLaunchQaRun } from './launch-qa-auto-start.util';
import { LaunchQaPgRepository } from './launch-qa-pg.repository';

export interface LaunchQaAutoStartResult {
  started: boolean;
  run_id?: string;
  idempotent?: boolean;
  reason?: string;
}

@Injectable()
export class LaunchQaAutoStartService {
  constructor(
    private readonly repo: LaunchQaPgRepository,
    private readonly config: AppConfigService,
    private readonly temporal: TemporalClientService,
  ) {}

  async maybeStartOnDeliverEnter(input: {
    agencyClientId: string;
    externalCampaignId: string;
    campaignName?: string;
    startedBy?: string;
  }): Promise<LaunchQaAutoStartResult> {
    if (!this.config.launchQaAutoStartOnDeliver) {
      return { started: false, reason: 'PTT_LAUNCH_QA_AUTO_START_ON_DELIVER disabled' };
    }

    const clientId = input.agencyClientId.trim();
    const campaignId = input.externalCampaignId.trim();
    if (!clientId || !campaignId) {
      return { started: false, reason: 'missing_client_or_campaign' };
    }

    if (!(await this.repo.pgReady())) {
      return { started: false, reason: 'launch_qa_runs table missing' };
    }
    if (!(await this.repo.clientExists(clientId))) {
      return { started: false, reason: 'client_not_found' };
    }

    const existing = await this.repo.findLatestRun(clientId, campaignId);
    if (shouldReuseLaunchQaRun(existing)) {
      return {
        started: true,
        run_id: existing!.id,
        idempotent: true,
        reason: 'client_campaign_pair',
      };
    }

    const startedBy = input.startedBy?.trim() || 'am@pttads.vn';
    const run = await this.repo.createRun({
      clientId,
      externalCampaignId: campaignId,
      campaignName: input.campaignName,
      startedBy,
    });

    if (this.temporal.isEnabled()) {
      try {
        const workflowId = this.temporal.launchQaWorkflowId(run.id);
        const wf = await this.temporal.startWorkflow('LaunchQAWorkflow', workflowId, [
          {
            run_id: run.id,
            client_id: clientId,
            external_campaign_id: campaignId,
            started_by: startedBy,
            campaign_name: input.campaignName?.trim() || null,
          },
        ]);
        await this.repo.updateTemporalMeta(run.id, wf.workflowId, wf.runId);
      } catch {
        /* PG run is source of truth */
      }
    }

    return { started: true, run_id: run.id };
  }
}
