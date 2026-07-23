import { launchQaGateFromRun, launchQaProgress, type LaunchQaGateResult } from './lifecycle-launch-gate.util';

export interface LaunchQaHandoverGateResult extends LaunchQaGateResult {
  requires_confirm: boolean;
  progress_completed: number;
  progress_total: number;
}

export function launchQaHandoverGateFromRun(input: {
  run: Parameters<typeof launchQaGateFromRun>[0]['run'];
  hasContext?: boolean;
  launchQaConfirm?: boolean;
}): LaunchQaHandoverGateResult {
  const base = launchQaGateFromRun({ run: input.run, hasContext: input.hasContext });
  const progress = launchQaProgress(input.run?.checklist ?? null);

  if (base.ok || base.launch_ready) {
    return {
      ...base,
      requires_confirm: false,
      progress_completed: progress.completed,
      progress_total: progress.total,
    };
  }

  if (input.launchQaConfirm) {
    return {
      ...base,
      ok: true,
      requires_confirm: false,
      progress_completed: progress.completed,
      progress_total: progress.total,
      messages: base.messages.length
        ? base.messages
        : [
            `Launch QA chưa launch_ready (${progress.completed}/${progress.total}) — đã xác nhận bàn giao`,
          ],
    };
  }

  return {
    ...base,
    ok: false,
    requires_confirm: true,
    progress_completed: progress.completed,
    progress_total: progress.total,
    messages: [
      base.messages[0] ??
        `Launch QA chưa launch_ready (${progress.completed}/${progress.total} mục) — xác nhận trước khi chuyển Handover`,
    ],
  };
}
