import { validateOnboardDeliverGate } from './lifecycle-onboard-gate.util';

describe('lifecycle-onboard-gate.util', () => {
  it('passes when client active', () => {
    const out = validateOnboardDeliverGate({ clientActive: true, orchestratorRequiredPercent: 50 });
    expect(out.ok).toBe(true);
  });

  it('blocks when orchestrator and checklist incomplete', () => {
    const out = validateOnboardDeliverGate({
      orchestratorRequiredPercent: 80,
      checklistPercent: 90,
    });
    expect(out.ok).toBe(false);
    expect(out.messages.join(' ')).toMatch(/Orchestrator/);
  });

  it('passes at 100%', () => {
    const out = validateOnboardDeliverGate({
      orchestratorRequiredPercent: 100,
      checklistPercent: 100,
    });
    expect(out.ok).toBe(true);
  });
});
