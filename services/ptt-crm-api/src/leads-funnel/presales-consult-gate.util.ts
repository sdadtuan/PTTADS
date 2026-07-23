import { GO_THRESHOLDS } from '../intake/intake-definitions.util';

export interface IntakeSessionGateRow {
  status?: string | null;
  mode?: string | null;
  decision?: string | null;
  bant_total?: number | null;
}

export interface ConsultAdvanceGateInput {
  leadTaskDone: boolean;
  sessions: IntakeSessionGateRow[];
  overrideReason?: string;
  allowOverride?: boolean;
  confirm?: boolean;
}

export interface ConsultAdvanceGateResult {
  ok: boolean;
  level: 'block' | 'warn' | 'ok';
  messages: string[];
  decision?: string;
  bant_total?: number;
  requires_confirm: boolean;
  requires_override: boolean;
}

export function validatePresalesConsultAdvance(input: ConsultAdvanceGateInput): ConsultAdvanceGateResult {
  const messages: string[] = [];
  const decision = String(
    [...input.sessions]
      .filter((s) => String(s.status || '') === 'completed')
      .sort((a, b) => Number(b.bant_total ?? 0) - Number(a.bant_total ?? 0))[0]?.decision || '',
  );
  const latestCompleted = input.sessions.find((s) => String(s.status || '') === 'completed');
  const bantTotal = Number(latestCompleted?.bant_total ?? 0);

  if (!input.leadTaskDone) {
    messages.push('Hoàn thành task Lead trước khi chuyển Tư vấn');
    return block(messages, decision, bantTotal);
  }

  const hasAnyIntake = input.sessions.some((s) => String(s.status || '') === 'completed');
  if (!hasAnyIntake) {
    messages.push('Hoàn thành Lead Intake trước khi chuyển Tư vấn');
    return block(messages, decision, bantTotal);
  }

  if (decision === 'no_go') {
    const reason = String(input.overrideReason || '').trim();
    if (!reason) {
      messages.push('Intake No-Go — không chuyển Consult (Director override + lý do)');
      return {
        ok: false,
        level: 'block',
        messages,
        decision,
        bant_total: bantTotal,
        requires_confirm: false,
        requires_override: true,
      };
    }
    if (!input.allowOverride) {
      messages.push('Cần quyền Director để override No-Go → Consult');
      return {
        ok: false,
        level: 'block',
        messages,
        decision,
        bant_total: bantTotal,
        requires_confirm: false,
        requires_override: true,
      };
    }
    messages.push(`Director override No-Go: ${reason.slice(0, 500)}`);
    return warn(messages, decision, bantTotal, true);
  }

  if (decision === 'nurture') {
    messages.push('Nurture — cân nhắc trước khi chuyển Consult sâu');
    return warn(messages, decision, bantTotal, false);
  }

  if (decision === 'go' && bantTotal < GO_THRESHOLDS.nurture_min) {
    messages.push(`BANT ${bantTotal}/30 — dưới ngưỡng Nurture (${GO_THRESHOLDS.nurture_min})`);
    return warn(messages, decision, bantTotal, false);
  }

  if (decision === 'go' && bantTotal < GO_THRESHOLDS.go) {
    messages.push(`BANT ${bantTotal}/30 — dưới ngưỡng Go (${GO_THRESHOLDS.go})`);
    return warn(messages, decision, bantTotal, false);
  }

  messages.push('Sẵn sàng chuyển Tư vấn');
  return {
    ok: true,
    level: 'ok',
    messages,
    decision,
    bant_total: bantTotal,
    requires_confirm: false,
    requires_override: false,
  };
}

export function consultAdvanceBlockReason(gate: ConsultAdvanceGateResult, confirm = false): string {
  if (!gate.ok) return gate.messages[0] || 'Không thể chuyển Consult';
  if (gate.requires_confirm && !confirm) return gate.messages[0] || 'Cần xác nhận';
  return '';
}

function block(messages: string[], decision: string, bantTotal: number): ConsultAdvanceGateResult {
  return {
    ok: false,
    level: 'block',
    messages,
    decision,
    bant_total: bantTotal,
    requires_confirm: false,
    requires_override: false,
  };
}

function warn(
  messages: string[],
  decision: string,
  bantTotal: number,
  requiresOverride: boolean,
): ConsultAdvanceGateResult {
  return {
    ok: true,
    level: 'warn',
    messages,
    decision,
    bant_total: bantTotal,
    requires_confirm: true,
    requires_override: requiresOverride,
  };
}
