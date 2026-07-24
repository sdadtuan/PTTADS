import { Injectable, Logger } from '@nestjs/common';
import { MetaTrackingRepository } from '../meta-tracking/meta-tracking.repository';
import {
  evaluateMetaLaunchQaItems,
  isMetaLaunchQaEnabled,
  mergeMetaLaunchQaChecklist,
} from '../meta-tracking/launch-qa-meta.util';
import { LaunchQaPgRepository, type LaunchQaRunRow } from '../service-lifecycle/launch-qa-pg.repository';
import { launchQaProgress } from '../service-lifecycle/lifecycle-launch-gate.util';

export interface MetaBridgeResult {
  synced: boolean;
  run_id?: string;
  idempotent?: boolean;
  launch_ready?: boolean;
  reason?: string;
  updated_keys?: string[];
}

@Injectable()
export class LaunchQaMetaBridgeService {
  private readonly logger = new Logger(LaunchQaMetaBridgeService.name);

  constructor(
    private readonly repo: LaunchQaPgRepository,
    private readonly trackingRepo: MetaTrackingRepository,
  ) {}

  async syncRun(run: LaunchQaRunRow | null): Promise<MetaBridgeResult> {
    if (!isMetaLaunchQaEnabled()) {
      return { synced: false, reason: 'meta_tracking_disabled' };
    }
    if (!run) {
      return { synced: false, reason: 'no_run' };
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
    if (!(await this.repo.pgReady())) {
      return { synced: false, reason: 'launch_qa_pg_unavailable' };
    }

    const evals = await evaluateMetaLaunchQaItems(this.trackingRepo, run.client_id);
    const updates: Record<string, { completed: boolean; note: string; completedBy?: string }> = {};
    for (const item of evals) {
      const current = run.checklist?.[item.key];
      const nextCompleted = item.passed;
      const nextNote = item.note;
      if (current?.completed === nextCompleted && current?.note === nextNote) {
        continue;
      }
      updates[item.key] = {
        completed: nextCompleted,
        note: nextNote,
        completedBy: nextCompleted ? 'meta_launch_qa_bridge' : undefined,
      };
    }

    const mergedChecklist = mergeMetaLaunchQaChecklist(run.checklist ?? {});
    const missingMetaKeys = Object.keys(mergedChecklist).some(
      (key) => !(key in (run.checklist ?? {})),
    );
    if (!Object.keys(updates).length && !missingMetaKeys) {
      return {
        synced: true,
        run_id: run.id,
        idempotent: true,
        launch_ready: run.launch_ready,
        reason: 'already_synced',
      };
    }

    try {
      const updated = await this.repo.syncAutoChecklistItems(run.id, updates, mergedChecklist);
      const progress = launchQaProgress(updated.checklist);
      this.logger.log(
        `Synced meta Launch QA run=${updated.id} client=${run.client_id} ${progress.completed}/${progress.total}`,
      );
      return {
        synced: true,
        run_id: updated.id,
        launch_ready: updated.launch_ready,
        updated_keys: Object.keys(updates),
      };
    } catch (err) {
      this.logger.warn(`meta bridge failed: ${err instanceof Error ? err.message : err}`);
      return { synced: false, reason: 'update_failed' };
    }
  }

  async syncByClientCampaign(clientId: string, externalCampaignId: string): Promise<MetaBridgeResult> {
    if (!(await this.repo.pgReady())) {
      return { synced: false, reason: 'launch_qa_pg_unavailable' };
    }
    const run = await this.repo.findLatestRun(clientId.trim(), externalCampaignId.trim());
    return this.syncRun(run);
  }
}
