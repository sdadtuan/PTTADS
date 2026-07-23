import { Injectable, Logger } from '@nestjs/common';
import { LaunchQaPgRepository } from '../service-lifecycle/launch-qa-pg.repository';
import { launchQaProgress } from '../service-lifecycle/lifecycle-launch-gate.util';

export interface BudgetBridgeResult {
  synced: boolean;
  run_id?: string;
  idempotent?: boolean;
  launch_ready?: boolean;
  reason?: string;
}

@Injectable()
export class LaunchQaCampaignWriteBridgeService {
  private readonly logger = new Logger(LaunchQaCampaignWriteBridgeService.name);

  constructor(private readonly repo: LaunchQaPgRepository) {}

  async onBudgetExecuted(input: {
    clientId: string;
    externalCampaignId: string;
    executedBy?: string;
    requestId?: string;
  }): Promise<BudgetBridgeResult> {
    const clientId = input.clientId.trim();
    const campaignId = String(input.externalCampaignId ?? '').trim();
    if (!clientId || !campaignId) {
      return { synced: false, reason: 'missing_client_or_campaign' };
    }
    if (!(await this.repo.pgReady())) {
      return { synced: false, reason: 'launch_qa_pg_unavailable' };
    }

    const run = await this.repo.findLatestRun(clientId, campaignId);
    if (!run) {
      return { synced: false, reason: 'no_launch_qa_run' };
    }
    if (run.status !== 'in_progress') {
      return {
        synced: true,
        run_id: run.id,
        idempotent: true,
        launch_ready: run.launch_ready,
        reason: 'run_not_in_progress',
      };
    }

    const item = run.checklist?.budget_confirmed;
    if (item?.completed) {
      return {
        synced: true,
        run_id: run.id,
        idempotent: true,
        launch_ready: run.launch_ready,
        reason: 'already_tickled',
      };
    }

    const note = input.requestId
      ? `Auto-sync từ campaign write ${input.requestId}`
      : 'Auto-sync từ campaign write executed';

    try {
      const updated = await this.repo.updateChecklistItem(run.id, 'budget_confirmed', {
        completed: true,
        completedBy: input.executedBy?.trim() || 'system@campaign-write',
        note,
      });
      const progress = launchQaProgress(updated.checklist);
      this.logger.log(
        `Synced budget_confirmed run=${updated.id} client=${clientId} campaign=${campaignId} ${progress.completed}/${progress.total}`,
      );
      return {
        synced: true,
        run_id: updated.id,
        launch_ready: updated.launch_ready,
      };
    } catch (err) {
      this.logger.warn(`budget bridge failed: ${err instanceof Error ? err.message : err}`);
      return { synced: false, reason: 'update_failed' };
    }
  }
}
