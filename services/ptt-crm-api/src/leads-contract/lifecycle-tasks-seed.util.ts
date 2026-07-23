import type { DatabaseSync } from 'node:sqlite';
import {
  lifecycleStepsForService,
  POST_ONBOARD_STAGES,
  RECURRING_DELIVER_SLUGS,
  type LifecycleStageKey,
  type WorkflowStep,
} from './lifecycle-workflow-steps.util';

function insertTask(
  db: DatabaseSync,
  lifecycleId: number,
  stage: string,
  stepIndex: number,
  step: WorkflowStep,
  ts: string,
): void {
  db.prepare(
    `INSERT INTO crm_svc_tasks
       (lifecycle_id, stage, step_index, title, description, form_fields, form_data,
        ai_prompt_key, ai_output, is_done, done_at, done_by, notes, is_custom, created_at, updated_at)
     VALUES (?, ?, ?, ?, ?, ?, '{}', ?, '', 0, '', NULL, '', 0, ?, ?)`,
  ).run(
    lifecycleId,
    stage,
    stepIndex,
    step.title,
    step.description,
    JSON.stringify(step.form_fields ?? []),
    step.ai_prompt_key ?? '',
    ts,
    ts,
  );
}

function seedDeliverSteps(
  db: DatabaseSync,
  lifecycleId: number,
  serviceSlug: string,
  steps: WorkflowStep[],
  ts: string,
): number {
  let count = 0;
  if (RECURRING_DELIVER_SLUGS.has(serviceSlug)) {
    for (let month = 1; month <= 12; month += 1) {
      const base = steps[0];
      if (!base) break;
      insertTask(
        db,
        lifecycleId,
        'deliver',
        month - 1,
        {
          ...base,
          title: `${base.title} — Tháng ${month}`,
        },
        ts,
      );
      count += 1;
    }
    return count;
  }
  steps.forEach((step, idx) => {
    insertTask(db, lifecycleId, 'deliver', idx, step, ts);
    count += 1;
  });
  return count;
}

/** Seed onboard/deliver/handover/retain — only stages with zero non-custom tasks. */
export function seedPostOnboardLifecycleTasks(
  db: DatabaseSync,
  lifecycleId: number,
  serviceSlug: string,
  ts: string,
): number {
  const steps = lifecycleStepsForService(serviceSlug);
  let added = 0;
  for (const stage of POST_ONBOARD_STAGES) {
    const existing = db
      .prepare(
        `SELECT COUNT(*) AS c FROM crm_svc_tasks
         WHERE lifecycle_id = ? AND stage = ? AND is_custom = 0`,
      )
      .get(lifecycleId, stage) as { c: number };
    if (Number(existing.c) > 0) continue;
    const stageSteps = steps[stage as LifecycleStageKey] ?? [];
    if (stage === 'deliver') {
      added += seedDeliverSteps(db, lifecycleId, serviceSlug, stageSteps, ts);
    } else {
      stageSteps.forEach((step, idx) => {
        insertTask(db, lifecycleId, stage, idx, step, ts);
        added += 1;
      });
    }
  }
  return added;
}

export function ensureSvcTasksSchema(db: DatabaseSync): void {
  db.exec(`
    CREATE TABLE IF NOT EXISTS crm_svc_tasks (
      id INTEGER PRIMARY KEY AUTOINCREMENT,
      lifecycle_id INTEGER NOT NULL,
      stage TEXT NOT NULL DEFAULT '',
      step_index INTEGER NOT NULL DEFAULT 0,
      title TEXT NOT NULL DEFAULT '',
      description TEXT NOT NULL DEFAULT '',
      form_fields TEXT NOT NULL DEFAULT '[]',
      form_data TEXT NOT NULL DEFAULT '{}',
      ai_output TEXT NOT NULL DEFAULT '',
      ai_prompt_key TEXT NOT NULL DEFAULT '',
      is_done INTEGER NOT NULL DEFAULT 0,
      done_at TEXT NOT NULL DEFAULT '',
      done_by INTEGER,
      notes TEXT NOT NULL DEFAULT '',
      is_custom INTEGER NOT NULL DEFAULT 0,
      created_at TEXT NOT NULL DEFAULT '',
      updated_at TEXT NOT NULL DEFAULT ''
    )
  `);
}
