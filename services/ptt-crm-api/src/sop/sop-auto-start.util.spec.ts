import { shouldReuseLifecycleSopRun } from './sop-auto-start.util';

describe('shouldReuseLifecycleSopRun', () => {
  it('reuses when sop_run_id set and run exists', () => {
    expect(shouldReuseLifecycleSopRun(42, true)).toBe(true);
  });

  it('creates new when no sop_run_id', () => {
    expect(shouldReuseLifecycleSopRun(null, false)).toBe(false);
    expect(shouldReuseLifecycleSopRun(0, true)).toBe(false);
  });

  it('creates new when sop_run_id stale (run missing)', () => {
    expect(shouldReuseLifecycleSopRun(99, false)).toBe(false);
  });
});
