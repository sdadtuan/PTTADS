import { Injectable, Logger } from '@nestjs/common';
import { LaunchQaPgRepository } from '../service-lifecycle/launch-qa-pg.repository';
import { launchQaProgress } from '../service-lifecycle/lifecycle-launch-gate.util';

export interface CreativeBridgeResult {
  synced: boolean;
  run_id?: string;
  idempotent?: boolean;
  launch_ready?: boolean;
  reason?: string;
}

@Injectable()
export class LaunchQaCreativeBridgeService {
  private readonly logger = new Logger(LaunchQaCreativeBridgeService.name);

  constructor(private readonly repo: LaunchQaPgRepository) {}

  async onCreativeApproved(input: {
    clientId: string;
    externalCampaignId: string | null;
    reviewedBy: string;
  }): Promise<CreativeBridgeResult> {
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

    const item = run.checklist?.creative_approved;
    if (item?.completed) {
      return {
        synced: true,
        run_id: run.id,
        idempotent: true,
        launch_ready: run.launch_ready,
        reason: 'already_tickled',
      };
    }

    try {
      const updated = await this.repo.updateChecklistItem(run.id, 'creative_approved', {
        completed: true,
        completedBy: input.reviewedBy,
        note: 'Auto-sync từ portal approve',
      });
      const progress = launchQaProgress(updated.checklist);
      this.logger.log(
        `Synced creative_approved run=${updated.id} client=${clientId} campaign=${campaignId} ${progress.completed}/${progress.total}`,
      );
      return {
        synced: true,
        run_id: updated.id,
        launch_ready: updated.launch_ready,
      };
    } catch (err) {
      this.logger.warn(`creative bridge failed: ${err instanceof Error ? err.message : err}`);
      return { synced: false, reason: 'update_failed' };
    }
  }
}
