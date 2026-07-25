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

  it('strict mode blocks without finance cap', () => {
    const gate = validatePaymentRetainGate({
      outstandingVnd: 3_000_000,
      arOverdueVnd: 1_000_000,
      strictMode: true,
      hasFinanceCap: false,
    });
    expect(gate.ok).toBe(false);
    expect(gate.requires_finance_role).toBe(true);
    expect(gate.can_confirm).toBe(false);
  });

  it('strict mode passes with finance cap and confirm', () => {
    const gate = validatePaymentRetainGate({
      outstandingVnd: 3_000_000,
      strictMode: true,
      hasFinanceCap: true,
      financeConfirm: true,
    });
    expect(gate.ok).toBe(true);
  });
});
