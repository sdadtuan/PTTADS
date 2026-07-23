import { validatePaymentRetainGate } from './lifecycle-payment-gate.util';

describe('lifecycle-payment-gate.util', () => {
  it('passes when no outstanding', () => {
    const gate = validatePaymentRetainGate({ outstandingVnd: 0 });
    expect(gate.ok).toBe(true);
    expect(gate.requires_confirm).toBe(false);
  });

  it('requires confirm when outstanding without finance_confirm', () => {
    const gate = validatePaymentRetainGate({ outstandingVnd: 5_000_000 });
    expect(gate.ok).toBe(false);
    expect(gate.requires_confirm).toBe(true);
  });

  it('passes with finance_confirm when outstanding', () => {
    const gate = validatePaymentRetainGate({ outstandingVnd: 3_000_000, financeConfirm: true });
    expect(gate.ok).toBe(true);
    expect(gate.level).toBe('warn');
  });
});
