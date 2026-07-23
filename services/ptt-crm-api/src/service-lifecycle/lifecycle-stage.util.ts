import { VALID_STAGES, stageIndex } from './service-lifecycle.types';

export class StageAdvanceError extends Error {
  constructor(message: string) {
    super(message);
    this.name = 'StageAdvanceError';
  }
}

export function nextStage(stage: string): string | null {
  const idx = stageIndex(stage);
  if (idx < 0 || idx >= VALID_STAGES.length - 1) return null;
  return VALID_STAGES[idx + 1];
}

export function validateStageAdvance(input: {
  fromStage: string;
  toStage: string;
  currentStageComplete: boolean;
  tmmtGate?: { ok: boolean; messages?: string[] };
  paymentGate?: { ok: boolean; messages?: string[] };
  launchQaGate?: { ok: boolean; messages?: string[] };
}): void {
  const { fromStage, toStage, currentStageComplete, tmmtGate, paymentGate, launchQaGate } = input;
  if (!(VALID_STAGES as readonly string[]).includes(toStage)) {
    throw new StageAdvanceError(`Stage không hợp lệ: ${toStage}`);
  }
  const fromIdx = stageIndex(fromStage);
  const toIdx = stageIndex(toStage);
  if (toIdx === fromIdx) return;
  if (toIdx < fromIdx) return;
  if (toIdx !== fromIdx + 1) {
    throw new StageAdvanceError(
      'Chỉ được chuyển sang bước kế tiếp. Hoàn thành từng giai đoạn theo thứ tự.',
    );
  }
  if (!currentStageComplete) {
    throw new StageAdvanceError(
      'Hoàn thành tất cả task của giai đoạn hiện tại trước khi chuyển bước.',
    );
  }
  if (toStage === 'deliver' && fromStage === 'onboard') {
    if (!tmmtGate?.ok) {
      throw new StageAdvanceError((tmmtGate?.messages ?? ['TMMT chưa đủ'])[0] ?? 'TMMT chưa đủ');
    }
  }
  if (toStage === 'handover' && fromStage === 'deliver') {
    if (launchQaGate && !launchQaGate.ok) {
      throw new StageAdvanceError(
        (launchQaGate.messages ?? ['Cần xác nhận Launch QA trước khi chuyển Handover'])[0] ??
          'Cần xác nhận Launch QA trước khi chuyển Handover',
      );
    }
  }
  if (toStage === 'retain' && fromStage === 'handover') {
    if (paymentGate && !paymentGate.ok) {
      throw new StageAdvanceError(
        (paymentGate.messages ?? ['Cần xác nhận công nợ trước khi chuyển Retain'])[0] ??
          'Cần xác nhận công nợ trước khi chuyển Retain',
      );
    }
  }
}

export function getStageAdvanceInfo(input: {
  currentStage: string;
  currentStageComplete: boolean;
  currentDone: number;
  currentTotal: number;
  tmmtGate?: { ok: boolean; messages?: string[] };
  paymentGate?: { ok: boolean; requires_confirm?: boolean; messages?: string[]; outstanding_vnd?: number };
  launchQaGate?: {
    ok: boolean;
    warn_only: true;
    launch_ready: boolean;
    progress_percent: number;
    progress_completed?: number;
    progress_total?: number;
    requires_confirm?: boolean;
    status: string | null;
    messages: string[];
  };
}): {
  current_stage: string;
  next_stage: string | null;
  can_advance_forward: boolean;
  block_reason: string;
  current_complete: boolean;
  current_done: number;
  current_total: number;
  payment_gate?: {
    ok: boolean;
    requires_confirm: boolean;
    outstanding_vnd: number;
    messages: string[];
  };
  launch_qa_gate?: {
    ok: boolean;
    warn_only: true;
    launch_ready: boolean;
    progress_percent: number;
    progress_completed: number;
    progress_total: number;
    requires_confirm: boolean;
    status: string | null;
    messages: string[];
  };
} {
  const { currentStage, currentStageComplete, currentDone, currentTotal, tmmtGate, paymentGate, launchQaGate } =
    input;
  const nxt = nextStage(currentStage);
  let blockReason = '';
  let canForward = false;
  if (!nxt) {
    blockReason = 'Đã ở giai đoạn cuối.';
  } else if (!currentStageComplete) {
    blockReason = 'Hoàn thành tất cả task giai đoạn hiện tại trước khi chuyển bước.';
  } else if (nxt === 'deliver' && currentStage === 'onboard') {
    if (!tmmtGate?.ok) {
      blockReason = (tmmtGate?.messages ?? ['TMMT chưa đủ'])[0] ?? 'TMMT chưa đủ';
    } else {
      canForward = true;
    }
  } else if (nxt === 'retain' && currentStage === 'handover') {
    if (paymentGate?.requires_confirm) {
      blockReason =
        (paymentGate.messages ?? ['Còn công nợ HĐ — xác nhận trên workflow detail trước khi Retain'])[0] ??
        'Còn công nợ HĐ — xác nhận trên workflow detail trước khi Retain';
    } else {
      canForward = true;
    }
  } else if (nxt === 'handover' && currentStage === 'deliver') {
    if (launchQaGate?.requires_confirm) {
      blockReason =
        (launchQaGate.messages ?? ['Launch QA chưa launch_ready — xác nhận trước khi Handover'])[0] ??
        'Launch QA chưa launch_ready — xác nhận trước khi Handover';
    } else {
      canForward = true;
    }
  } else {
    canForward = true;
  }
  const paymentGateOut =
    nxt === 'retain' && currentStage === 'handover' && paymentGate
      ? {
          ok: paymentGate.ok ?? false,
          requires_confirm: Boolean(paymentGate.requires_confirm),
          outstanding_vnd: Number(paymentGate.outstanding_vnd ?? 0),
          messages: paymentGate.messages ?? [],
        }
      : undefined;
  const launchQaGateOut =
    nxt === 'handover' && currentStage === 'deliver' && launchQaGate
      ? {
          ok: launchQaGate.ok,
          warn_only: true as const,
          launch_ready: launchQaGate.launch_ready,
          progress_percent: launchQaGate.progress_percent,
          progress_completed: Number(launchQaGate.progress_completed ?? 0),
          progress_total: Number(launchQaGate.progress_total ?? 0),
          requires_confirm: Boolean(launchQaGate.requires_confirm),
          status: launchQaGate.status,
          messages: launchQaGate.messages,
        }
      : undefined;
  return {
    current_stage: currentStage,
    next_stage: nxt,
    can_advance_forward: canForward,
    block_reason: blockReason,
    current_complete: currentStageComplete,
    current_done: currentDone,
    current_total: currentTotal,
    payment_gate: paymentGateOut,
    launch_qa_gate: launchQaGateOut,
  };
}
