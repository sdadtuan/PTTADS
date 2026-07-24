import {
  buildMetaAttributionMeta,
  computeCplDelta,
  computeUnmappedSpendPct,
} from './meta-attribution.util';

describe('meta-attribution.util', () => {
  it('computeUnmappedSpendPct rounds to one decimal', () => {
    expect(computeUnmappedSpendPct(62, 1000)).toBe(6.2);
    expect(computeUnmappedSpendPct(0, 0)).toBe(0);
  });

  it('computeCplDelta marks over target', () => {
    const out = computeCplDelta(120_000, 100_000);
    expect(out.deltaVnd).toBe(20_000);
    expect(out.deltaPct).toBe(20);
    expect(out.overTarget).toBe(true);
  });

  it('buildMetaAttributionMeta uses last_touch_crm', () => {
    const meta = buildMetaAttributionMeta({
      dateTo: '2026-07-21',
      syncedAt: '2026-07-22T06:12:04.000Z',
      unmappedSpendPct: 6.2,
    });
    expect(meta.attribution_model).toBe('last_touch_crm');
    expect(meta.unmapped_spend_pct).toBe(6.2);
    expect(meta.spend_source).toBe('meta_api');
    expect(meta.data_freshness.through_date).toBe('2026-07-21');
  });
});
