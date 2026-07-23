export interface PaymentRetainGateResult {
  ok: boolean;
  level: 'ok' | 'warn';
  requires_confirm: boolean;
  messages: string[];
  outstanding_vnd: number;
}

export function validatePaymentRetainGate(input: {
  outstandingVnd: number;
  financeConfirm?: boolean;
}): PaymentRetainGateResult {
  const outstanding = Math.max(0, Math.round(Number(input.outstandingVnd ?? 0)));
  if (outstanding <= 0) {
    return {
      ok: true,
      level: 'ok',
      requires_confirm: false,
      messages: [],
      outstanding_vnd: 0,
    };
  }
  const msg = `Còn công nợ HĐ: ${outstanding.toLocaleString('vi-VN')} VND — cần xác nhận trước khi chuyển Retain`;
  if (input.financeConfirm) {
    return {
      ok: true,
      level: 'warn',
      requires_confirm: false,
      messages: [msg.replace(' — cần xác nhận trước khi chuyển Retain', '')],
      outstanding_vnd: outstanding,
    };
  }
  return {
    ok: false,
    level: 'warn',
    requires_confirm: true,
    messages: [msg],
    outstanding_vnd: outstanding,
  };
}

export function paymentGateFromSummary(
  summary: { outstanding_vnd?: number; outstanding?: number } | null,
  financeConfirm?: boolean,
): PaymentRetainGateResult {
  const outstanding = Number(summary?.outstanding_vnd ?? summary?.outstanding ?? 0);
  return validatePaymentRetainGate({ outstandingVnd: outstanding, financeConfirm });
}
