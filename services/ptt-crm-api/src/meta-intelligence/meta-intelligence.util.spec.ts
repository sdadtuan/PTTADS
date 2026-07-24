import {
  buildForecastProjection,
  computeZscore,
  detectCampaignAnomalies,
  detectCampaignStatAnomalies,
  isMedianSpike,
  recommendBudgetChange,
} from './meta-intelligence.util';

describe('meta-intelligence.util', () => {
  it('detects spend spike', () => {
    const spike = isMedianSpike(200_000, [100_000, 110_000, 95_000, 105_000], 50);
    expect(spike.spike).toBe(true);
  });

  it('detectCampaignAnomalies includes roas_low', () => {
    const items = detectCampaignAnomalies({
      spendToday: 300_000,
      leadsToday: 2,
      conversionValueToday: 600_000,
      spendHistory: [100_000, 110_000, 95_000],
      cplHistory: [50_000, 55_000],
      spikePct: 50,
      roasMinTarget: 3,
      roasMinSpend: 100_000,
    });
    expect(items.some((i) => i.alert_type === 'spend_spike')).toBe(true);
    expect(items.some((i) => i.alert_type === 'roas_low')).toBe(true);
  });

  it('recommendBudgetChange decrease path', () => {
    const rec = recommendBudgetChange({
      avgDailySpend: 1_000_000,
      cpl: 150_000,
      targetCpl: 100_000,
      leads: 3,
      roas: 1.5,
      decreasePct: 15,
      increasePct: 10,
      cplOverRatio: 1.15,
      cplUnderRatio: 0.85,
    });
    expect(rec?.recommendation_type).toBe('decrease_budget');
    expect(rec?.suggested_daily_budget_vnd).toBe(850_000);
  });

  it('computeZscore detects spike', () => {
    const z = computeZscore(250_000, [100_000, 110_000, 95_000, 105_000, 98_000, 102_000]);
    expect(z).not.toBeNull();
    expect(z!).toBeGreaterThan(2);
  });

  it('detectCampaignStatAnomalies returns spend_zscore', () => {
    const items = detectCampaignStatAnomalies({
      spendToday: 300_000,
      leadsToday: 3,
      spendHistory: [100_000, 110_000, 95_000, 105_000, 98_000],
      cplHistory: [50_000, 55_000, 48_000],
      zscoreThreshold: 2,
    });
    expect(items.some((i) => i.alert_type === 'spend_zscore')).toBe(true);
  });

  it('buildForecastProjection returns 7d projection', () => {
    const out = buildForecastProjection({
      historical: [
        { performance_date: '2026-07-17', value: 100_000 },
        { performance_date: '2026-07-18', value: 110_000 },
        { performance_date: '2026-07-19', value: 120_000 },
      ],
      projectionDays: 7,
    });
    expect(out.projection).toHaveLength(7);
    expect(out.slope).toBeGreaterThan(0);
  });
});
