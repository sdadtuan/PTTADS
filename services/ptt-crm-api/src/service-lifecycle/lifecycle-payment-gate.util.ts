export interface PaymentRetainGateResult {
  ok: boolean;
  level: 'ok' | 'warn' | 'block';
  requires_confirm: boolean;
  requires_finance_role: boolean;
  strict_mode: boolean;
  can_confirm: boolean;
  messages: string[];
  outstanding_vnd: number;
  ar_pending_vnd: number;
  ar_overdue_vnd: number;
}

export function validatePaymentRetainGate(input: {
  outstandingVnd: number;
  arPendingVnd?: number;
  arOverdueVnd?: number;
  financeConfirm?: boolean;
  strictMode?: boolean;
  hasFinanceCap?: boolean;
}): PaymentRetainGateResult {
  const outstanding = Math.max(0, Math.round(Number(input.outstandingVnd ?? 0)));
  const arPending = Math.max(0, Math.round(Number(input.arPendingVnd ?? 0)));
  const arOverdue = Math.max(0, Math.round(Number(input.arOverdueVnd ?? 0)));
  const strictMode = Boolean(input.strictMode);
  const hasFinanceCap = Boolean(input.hasFinanceCap);
  const needsGate = outstanding > 0 || arOverdue > 0;

  const base = {
    outstanding_vnd: outstanding,
    ar_pending_vnd: arPending,
    ar_overdue_vnd: arOverdue,
    strict_mode: strictMode,
    requires_finance_role: strictMode && needsGate,
    can_confirm: strictMode ? hasFinanceCap : true,
  };

  if (!needsGate) {
    return {
      ...base,
      ok: true,
      level: 'ok',
      requires_confirm: false,
      messages: [],
    };
  }

  const parts: string[] = [];
  if (outstanding > 0) {
    parts.push(`Còn công nợ HĐ: ${outstanding.toLocaleString('vi-VN')} VND`);
  }
  if (arOverdue > 0) {
    parts.push(`AR quá hạn: ${arOverdue.toLocaleString('vi-VN')} VND`);
  }
  if (arPending > 0 && arOverdue === 0) {
    parts.push(`AR chờ thu: ${arPending.toLocaleString('vi-VN')} VND`);
  }

  const msgBase = parts.join(' · ');

  if (strictMode) {
    if (input.financeConfirm && hasFinanceCap) {
      return {
        ...base,
        ok: true,
        level: 'warn',
        requires_confirm: false,
        messages: [`Finance đã xác nhận — ${msgBase}`],
      };
    }
    return {
      ...base,
      ok: false,
      level: 'block',
      requires_confirm: true,
      messages: [
        `${msgBase} — strict mode: cần Finance xác nhận trước khi chuyển Retain`,
      ],
    };
  }

  const msg = `${msgBase} — cần xác nhận trước khi chuyển Retain`;
  if (input.financeConfirm) {
    return {
      ...base,
      ok: true,
      level: 'warn',
      requires_confirm: false,
      messages: [msg.replace(' — cần xác nhận trước khi chuyển Retain', '')],
    };
  }
  return {
    ...base,
    ok: false,
    level: 'warn',
    requires_confirm: true,
    messages: [msg],
  };
}

export function paymentGateFromSummary(
  summary: {
    outstanding_vnd?: number;
    outstanding?: number;
    ar_pending_vnd?: number;
    ar_overdue_vnd?: number;
  } | null,
  options?: {
    financeConfirm?: boolean;
    strictMode?: boolean;
    hasFinanceCap?: boolean;
  },
): PaymentRetainGateResult {
  const outstanding = Number(summary?.outstanding_vnd ?? summary?.outstanding ?? 0);
  return validatePaymentRetainGate({
    outstandingVnd: outstanding,
    arPendingVnd: Number(summary?.ar_pending_vnd ?? 0),
    arOverdueVnd: Number(summary?.ar_overdue_vnd ?? 0),
    financeConfirm: options?.financeConfirm,
    strictMode: options?.strictMode,
    hasFinanceCap: options?.hasFinanceCap,
  });
}
