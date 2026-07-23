import { shouldReuseLaunchQaRun } from './launch-qa-auto-start.util';

describe('shouldReuseLaunchQaRun', () => {
  it('reuses in_progress and passed', () => {
    expect(shouldReuseLaunchQaRun({ status: 'in_progress' })).toBe(true);
    expect(shouldReuseLaunchQaRun({ status: 'passed' })).toBe(true);
  });

  it('does not reuse failed or missing', () => {
    expect(shouldReuseLaunchQaRun({ status: 'failed' })).toBe(false);
    expect(shouldReuseLaunchQaRun(null)).toBe(false);
  });
});
