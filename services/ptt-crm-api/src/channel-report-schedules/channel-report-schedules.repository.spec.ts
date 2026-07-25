import { ChannelReportSchedulesRepository } from './channel-report-schedules.repository';

describe('ChannelReportSchedulesRepository', () => {
  const config = { databaseUrl: 'postgresql://test' } as never;
  const repo = new ChannelReportSchedulesRepository(config);

  it('computeNextRun weekly returns future date', () => {
    const next = repo.computeNextRun('weekly', 0, 1, new Date('2026-07-20T12:00:00Z'));
    expect(next >= '2026-07-21').toBe(true);
  });

  it('computeNextRun monthly caps day_of_month at 28', () => {
    const next = repo.computeNextRun('monthly', 0, 99, new Date('2026-07-20T12:00:00Z'));
    const day = Number(next.slice(-2));
    expect(day).toBeLessThanOrEqual(28);
  });
});
