import { Test, TestingModule } from '@nestjs/testing';
import { PerformanceRepository } from './performance.repository';
import { PerformanceService } from './performance.service';

describe('PerformanceService.refreshZaloHubCpaOnLeadStatusChange', () => {
  let service: PerformanceService;
  const repo = {
    pgPerformanceReady: jest.fn(),
    refreshZaloConversionsForClientDate: jest.fn(),
  };

  beforeEach(async () => {
    jest.clearAllMocks();
    const module: TestingModule = await Test.createTestingModule({
      providers: [
        PerformanceService,
        { provide: PerformanceRepository, useValue: repo },
      ],
    }).compile();
    service = module.get(PerformanceService);
  });

  it('skips non-zalo channel', async () => {
    const out = await service.refreshZaloHubCpaOnLeadStatusChange({
      channel: 'meta',
      clientId: '550e8400-e29b-41d4-a716-446655440000',
      oldStatus: 'new',
      newStatus: 'won',
      receivedAt: '2026-07-20T10:00:00Z',
      createdAt: '2026-07-20T10:00:00Z',
    });
    expect(out).toBeNull();
    expect(repo.refreshZaloConversionsForClientDate).not.toHaveBeenCalled();
  });

  it('skips when neither old nor new status is won', async () => {
    repo.pgPerformanceReady.mockResolvedValue(true);
    const out = await service.refreshZaloHubCpaOnLeadStatusChange({
      channel: 'zalo',
      clientId: '550e8400-e29b-41d4-a716-446655440000',
      oldStatus: 'new',
      newStatus: 'qualified',
      receivedAt: '2026-07-20T10:00:00Z',
      createdAt: '2026-07-20T10:00:00Z',
    });
    expect(out).toBeNull();
    expect(repo.refreshZaloConversionsForClientDate).not.toHaveBeenCalled();
  });

  it('refreshes daily_performance when lead becomes won', async () => {
    repo.pgPerformanceReady.mockResolvedValue(true);
    repo.refreshZaloConversionsForClientDate.mockResolvedValue(2);
    const out = await service.refreshZaloHubCpaOnLeadStatusChange({
      channel: 'zalo',
      clientId: '550e8400-e29b-41d4-a716-446655440000',
      oldStatus: 'qualified',
      newStatus: 'won',
      receivedAt: '2026-07-20T10:00:00Z',
      createdAt: '2026-07-20T10:00:00Z',
    });
    expect(out).toEqual({ refreshed: 2, perf_date: '2026-07-20' });
    expect(repo.refreshZaloConversionsForClientDate).toHaveBeenCalledWith(
      '550e8400-e29b-41d4-a716-446655440000',
      '2026-07-20',
    );
  });

  it('refreshes when lead moves from won to lost', async () => {
    repo.pgPerformanceReady.mockResolvedValue(true);
    repo.refreshZaloConversionsForClientDate.mockResolvedValue(1);
    const out = await service.refreshZaloHubCpaOnLeadStatusChange({
      channel: 'zalo',
      clientId: '550e8400-e29b-41d4-a716-446655440000',
      oldStatus: 'won',
      newStatus: 'lost',
      receivedAt: '2026-07-20T10:00:00Z',
      createdAt: '2026-07-20T10:00:00Z',
    });
    expect(out).toEqual({ refreshed: 1, perf_date: '2026-07-20' });
  });
});
