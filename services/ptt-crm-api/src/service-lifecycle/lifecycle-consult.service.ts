import { Injectable, NotFoundException } from '@nestjs/common';
import { IntakeSqliteRepository } from '../intake/intake-sqlite.repository';
import { buildConsultBrief, prefillConsultTaskForm } from './lifecycle-consult.util';
import { LifecycleTasksRepository } from './lifecycle-tasks.repository';
import { ServiceLifecycleSqliteRepository } from './service-lifecycle-sqlite.repository';

@Injectable()
export class LifecycleConsultService {
  constructor(
    private readonly sqlite: ServiceLifecycleSqliteRepository,
    private readonly tasks: LifecycleTasksRepository,
    private readonly intake: IntakeSqliteRepository,
  ) {}

  getConsultBrief(lifecycleId: number): Record<string, unknown> {
    const lc = this.sqlite.getLifecycleById(lifecycleId);
    if (!lc) {
      throw new NotFoundException({ error: `Không tìm thấy lifecycle #${lifecycleId}` });
    }

    const grouped = this.tasks.listTasksGrouped(lifecycleId);
    const leadTasks = grouped.lead ?? [];
    const leadTaskRow = leadTasks[0] ?? null;
    const leadTask = leadTaskRow
      ? {
          task_id: leadTaskRow.id,
          form_data: leadTaskRow.form_data,
          notes: leadTaskRow.notes,
          is_done: leadTaskRow.is_done,
        }
      : null;

    const intakeSessions = this.intake.listSessions({ lifecycleId, limit: 20 });

    return buildConsultBrief({
      lifecycleId,
      serviceSlug: lc.service_slug,
      leadId: lc.lead_id,
      leadTaskDone: this.tasks.isStageComplete(lifecycleId, 'lead'),
      leadTask,
      intakeSessions,
    });
  }

  prefillConsultTask(
    lifecycleId: number,
    opts: { overwrite?: boolean } = {},
  ): {
    task_id: number | null;
    filled: number;
    fields: string[];
    skipped_existing: string[];
  } {
    const lc = this.sqlite.getLifecycleById(lifecycleId);
    if (!lc) {
      throw new NotFoundException({ error: `Không tìm thấy lifecycle #${lifecycleId}` });
    }

    const grouped = this.tasks.listTasksGrouped(lifecycleId);
    const consultTasks = grouped.consult ?? [];
    const consultTask = consultTasks[0];
    if (!consultTask) {
      return { task_id: null, filled: 0, fields: [], skipped_existing: [] };
    }

    const leadTasks = grouped.lead ?? [];
    const leadTask = leadTasks[0] ?? null;
    const intakeSessions = this.intake.listSessions({ lifecycleId, limit: 20 });
    const latestCompleted = intakeSessions
      .filter((s) => s.status === 'completed')
      .sort((a, b) => {
        const ak = `${a.completed_at ?? ''}\0${a.id}`;
        const bk = `${b.completed_at ?? ''}\0${b.id}`;
        return bk.localeCompare(ak);
      })[0] ?? null;

    const result = prefillConsultTaskForm({
      serviceSlug: lc.service_slug,
      consultTask,
      leadTask,
      latestIntake: latestCompleted,
      overwrite: Boolean(opts.overwrite),
    });

    this.tasks.updateTask(consultTask.id, {
      form_data: result.form_data,
      notes: result.notes,
    });

    return {
      task_id: consultTask.id,
      filled: result.filled.length,
      fields: result.filled,
      skipped_existing: result.skipped_existing,
    };
  }
}
