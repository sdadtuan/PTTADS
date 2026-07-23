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
}): void {
  const { fromStage, toStage, currentStageComplete, tmmtGate } = input;
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
}

export function getStageAdvanceInfo(input: {
  currentStage: string;
  currentStageComplete: boolean;
  currentDone: number;
  currentTotal: number;
  tmmtGate?: { ok: boolean; messages?: string[] };
}): {
  current_stage: string;
  next_stage: string | null;
  can_advance_forward: boolean;
  block_reason: string;
  current_complete: boolean;
  current_done: number;
  current_total: number;
} {
  const { currentStage, currentStageComplete, currentDone, currentTotal, tmmtGate } = input;
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
  } else {
    canForward = true;
  }
  return {
    current_stage: currentStage,
    next_stage: nxt,
    can_advance_forward: canForward,
    block_reason: blockReason,
    current_complete: currentStageComplete,
    current_done: currentDone,
    current_total: currentTotal,
  };
}
