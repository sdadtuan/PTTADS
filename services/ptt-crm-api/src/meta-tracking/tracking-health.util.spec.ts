import {
  computeTrackingHealthGlobal,
  emptyTrackingHealthGlobal,
} from './tracking-health.util';

describe('tracking-health.util', () => {
  it('computes fail rate and match hint from status counts', () => {
    const global = computeTrackingHealthGlobal({
      byStatus: { sent: 9, failed: 1, skipped: 2, pending: 1 },
      avgLatencyMs: 125.4,
    });
    expect(global.sent).toBe(9);
    expect(global.failed).toBe(1);
    expect(global.skipped).toBe(2);
    expect(global.pending).toBe(1);
    expect(global.fail_rate_pct).toBe(10);
    expect(global.match_hint_pct).toBe(90);
    expect(global.avg_latency_ms).toBe(125);
  });

  it('empty global defaults to zeros', () => {
    const global = emptyTrackingHealthGlobal();
    expect(global.sent).toBe(0);
    expect(global.match_hint_pct).toBeNull();
  });
});
