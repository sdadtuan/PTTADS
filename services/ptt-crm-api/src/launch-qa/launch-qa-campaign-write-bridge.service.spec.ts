import { LaunchQaCampaignWriteBridgeService } from './launch-qa-campaign-write-bridge.service';

describe('LaunchQaCampaignWriteBridgeService', () => {
  const repo = {
    pgReady: jest.fn(),
    findLatestRun: jest.fn(),
    updateChecklistItem: jest.fn(),
  };
  const bridge = new LaunchQaCampaignWriteBridgeService(repo as never);

  beforeEach(() => {
    jest.resetAllMocks();
    repo.pgReady.mockResolvedValue(true);
  });

  it('skips when no campaign', async () => {
    const out = await bridge.onBudgetExecuted({
      clientId: 'c1',
      externalCampaignId: '',
    });
    expect(out.synced).toBe(false);
    expect(out.reason).toBe('missing_client_or_campaign');
  });

  it('ticks budget_confirmed on executed', async () => {
    repo.findLatestRun.mockResolvedValue({
      id: 'run-1',
      status: 'in_progress',
      launch_ready: false,
      checklist: { budget_confirmed: { completed: false } },
    });
    repo.updateChecklistItem.mockResolvedValue({
      id: 'run-1',
      launch_ready: true,
      checklist: { budget_confirmed: { completed: true } },
    });
    const out = await bridge.onBudgetExecuted({
      clientId: 'c1',
      externalCampaignId: 'CAMP-01',
      executedBy: 'admin@pttads.vn',
      requestId: 'req-1',
    });
    expect(out.synced).toBe(true);
    expect(out.launch_ready).toBe(true);
    expect(repo.updateChecklistItem).toHaveBeenCalledWith(
      'run-1',
      'budget_confirmed',
      expect.objectContaining({ completed: true }),
    );
  });

  it('idempotent when already completed', async () => {
    repo.findLatestRun.mockResolvedValue({
      id: 'run-1',
      status: 'in_progress',
      launch_ready: false,
      checklist: { budget_confirmed: { completed: true } },
    });
    const out = await bridge.onBudgetExecuted({
      clientId: 'c1',
      externalCampaignId: 'CAMP-01',
    });
    expect(out.idempotent).toBe(true);
    expect(repo.updateChecklistItem).not.toHaveBeenCalled();
  });
});
