import { launchQaGateFromRun, launchQaProgress } from './lifecycle-launch-gate.util';

describe('launchQaProgress', () => {
  it('computes percent from checklist', () => {
    const p = launchQaProgress({
      pixel_verified: { completed: true },
      utm_tracking: { completed: false },
    });
    expect(p.total).toBe(2);
    expect(p.completed).toBe(1);
    expect(p.percent).toBe(50);
  });
});

describe('launchQaGateFromRun', () => {
  it('warns when no run', () => {
    const g = launchQaGateFromRun({ run: null, hasContext: true });
    expect(g.ok).toBe(false);
    expect(g.warn_only).toBe(true);
    expect(g.messages[0]).toMatch(/Chưa có Launch QA run/);
  });

  it('ok when launch_ready', () => {
    const g = launchQaGateFromRun({
      run: { launch_ready: true, status: 'passed', checklist: {} },
    });
    expect(g.ok).toBe(true);
    expect(g.launch_ready).toBe(true);
  });

  it('warns when in progress', () => {
    const g = launchQaGateFromRun({
      run: {
        launch_ready: false,
        status: 'in_progress',
        checklist: {
          a: { completed: true },
          b: { completed: false },
        },
      },
    });
    expect(g.ok).toBe(false);
    expect(g.progress_percent).toBe(50);
  });
});
