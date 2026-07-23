export interface LaunchQaProgress {
  total: number;
  completed: number;
  percent: number;
}

export interface LaunchQaGateResult {
  ok: boolean;
  warn_only: true;
  launch_ready: boolean;
  progress_percent: number;
  status: string | null;
  messages: string[];
}

export function launchQaProgress(checklist: Record<string, { completed?: boolean }> | null): LaunchQaProgress {
  const entries = Object.values(checklist ?? {}).filter((v) => v && typeof v === 'object');
  const total = entries.length;
  const completed = entries.filter((v) => Boolean(v.completed)).length;
  const percent = total ? Math.round((completed / total) * 100) : 0;
  return { total, completed, percent };
}

export function launchQaGateFromRun(input: {
  run: { launch_ready?: boolean; status?: string; checklist?: Record<string, { completed?: boolean }> } | null;
  hasContext?: boolean;
}): LaunchQaGateResult {
  const { run, hasContext = true } = input;
  if (!hasContext) {
    return {
      ok: true,
      warn_only: true,
      launch_ready: false,
      progress_percent: 0,
      status: null,
      messages: ['Chưa có agency client / campaign — bỏ qua Launch QA gate'],
    };
  }
  if (!run) {
    return {
      ok: false,
      warn_only: true,
      launch_ready: false,
      progress_percent: 0,
      status: null,
      messages: ['Chưa có Launch QA run — mở tab Launch QA hoặc chờ auto-start khi vào Deliver'],
    };
  }
  const progress = launchQaProgress(run.checklist ?? null);
  const launchReady = Boolean(run.launch_ready) || run.status === 'passed';
  if (launchReady) {
    return {
      ok: true,
      warn_only: true,
      launch_ready: true,
      progress_percent: 100,
      status: run.status ?? 'passed',
      messages: [],
    };
  }
  return {
    ok: false,
    warn_only: true,
    launch_ready: false,
    progress_percent: progress.percent,
    status: run.status ?? 'in_progress',
    messages: [
      `Launch QA chưa launch_ready (${progress.completed}/${progress.total} mục) — hoàn thiện checklist trước bàn giao`,
    ],
  };
}
