import { Injectable, Logger } from '@nestjs/common';
import { LaunchQaPgRepository, type LaunchQaRunRow } from '../service-lifecycle/launch-qa-pg.repository';
import { launchQaProgress } from '../service-lifecycle/lifecycle-launch-gate.util';
import {
  evaluateZaloLaunchQaItems,
  isZaloLaunchQaEnabled,
  mergeZaloLaunchQaChecklist,
} from '../zalo-tracking/launch-qa-zalo.util';
import { ZaloLaunchQaRepository } from '../zalo-tracking/zalo-launch-qa.repository';

export interface ZaloBridgeResult {
  synced: boolean;
  run_id?: string;
  idempotent?: boolean;
  launch_ready?: boolean;
  reason?: string;
  updated_keys?: string[];
}

@Injectable()
export class LaunchQaZaloBridgeService {
  private readonly logger = new Logger(LaunchQaZaloBridgeService.name);

  constructor(
    private readonly repo: LaunchQaPgRepository,
    private readonly zaloRepo: ZaloLaunchQaRepository,
  ) {}

  async syncRun(run: LaunchQaRunRow | null): Promise<ZaloBridgeResult> {
    if (!isZaloLaunchQaEnabled()) {
      return { synced: false, reason: 'zalo_launch_qa_disabled' };
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

    const account = await this.zaloRepo.fetchZaloChannelAccount(run.client_id);
    const hasZalo = Boolean(account?.has_account);
    const evals = evaluateZaloLaunchQaItems(account);
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
        completedBy: nextCompleted ? 'zalo_launch_qa_bridge' : undefined,
      };
    }

    const mergedChecklist = mergeZaloLaunchQaChecklist(run.checklist ?? {}, hasZalo);
    const missingKeys = Object.keys(mergedChecklist).some((key) => !(key in (run.checklist ?? {})));
    if (!Object.keys(updates).length && !missingKeys) {
      return {
        synced: true,
        run_id: run.id,
        idempotent: true,
        launch_ready: run.launch_ready,
        reason: hasZalo ? 'already_synced' : 'no_zalo_channel',
      };
    }

    try {
      const updated = await this.repo.syncAutoChecklistItems(run.id, updates, mergedChecklist);
      const progress = launchQaProgress(updated.checklist);
      this.logger.log(
        `Synced zalo Launch QA run=${updated.id} client=${run.client_id} ${progress.completed}/${progress.total}`,
      );
      return {
        synced: true,
        run_id: updated.id,
        launch_ready: updated.launch_ready,
        updated_keys: Object.keys(updates),
      };
    } catch (err) {
      this.logger.warn(`zalo bridge failed: ${err instanceof Error ? err.message : err}`);
      return { synced: false, reason: 'update_failed' };
    }
  }
}
