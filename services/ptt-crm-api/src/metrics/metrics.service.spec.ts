import { MetricsService } from './metrics.service';
import { MetricsRepository } from './metrics.repository';

describe('MetricsService', () => {
  const repo = {
    pgPerformanceReady: jest.fn(),
    fetchCrossChannelSummary: jest.fn(),
  } as unknown as MetricsRepository;

  const service = new MetricsService(repo);

  beforeEach(() => {
    jest.resetAllMocks();
    process.env.PTT_METRICS_CROSS_CHANNEL_ENABLED = '1';
  });

  it('aggregates cross-channel totals', async () => {
    (repo.pgPerformanceReady as jest.Mock).mockResolvedValue(true);
    (repo.fetchCrossChannelSummary as jest.Mock).mockResolvedValue([
      { channel: 'meta', spend: 1000, leads_crm: 10, leads_platform: 12, cpl: 100, campaigns: 2, unmapped_rows: 0 },
      { channel: 'google', spend: 500, leads_crm: 5, leads_platform: 6, cpl: 100, campaigns: 1, unmapped_rows: 0 },
    ]);

    const out = await service.crossChannelSummary({ days: '7' });
    expect(out.ok).toBe(true);
    expect(out.totals.spend).toBe(1500);
    expect(out.totals.leads_crm).toBe(15);
    expect(out.channels).toHaveLength(2);
  });
});
