import { launchQaHandoverGateFromRun } from './lifecycle-launch-handover-gate.util';

describe('launchQaHandoverGateFromRun', () => {
  it('requires confirm when not launch_ready', () => {
    const g = launchQaHandoverGateFromRun({
      run: {
        launch_ready: false,
        status: 'in_progress',
        checklist: { a: { completed: true }, b: { completed: false } },
      },
    });
    expect(g.requires_confirm).toBe(true);
    expect(g.ok).toBe(false);
  });

  it('allows with confirm flag', () => {
    const g = launchQaHandoverGateFromRun({
      run: {
        launch_ready: false,
        status: 'in_progress',
        checklist: { a: { completed: false } },
      },
      launchQaConfirm: true,
    });
    expect(g.ok).toBe(true);
    expect(g.requires_confirm).toBe(false);
  });

  it('ok when launch_ready', () => {
    const g = launchQaHandoverGateFromRun({
      run: { launch_ready: true, status: 'passed', checklist: {} },
    });
    expect(g.ok).toBe(true);
    expect(g.requires_confirm).toBe(false);
  });
});
