import {
  detectCampaignAnomalies,
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
});
