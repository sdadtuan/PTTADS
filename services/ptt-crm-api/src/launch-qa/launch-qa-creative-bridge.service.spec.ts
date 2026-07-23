import { LaunchQaCreativeBridgeService } from './launch-qa-creative-bridge.service';

describe('LaunchQaCreativeBridgeService', () => {
  const repo = {
    pgReady: jest.fn(),
    findLatestRun: jest.fn(),
    updateChecklistItem: jest.fn(),
  };
  const bridge = new LaunchQaCreativeBridgeService(repo as never);

  beforeEach(() => {
    jest.resetAllMocks();
    repo.pgReady.mockResolvedValue(true);
  });

  it('skips when no campaign', async () => {
    const out = await bridge.onCreativeApproved({
      clientId: 'c1',
      externalCampaignId: null,
      reviewedBy: 'client@x.vn',
    });
    expect(out.synced).toBe(false);
    expect(out.reason).toBe('missing_client_or_campaign');
  });

  it('ticks creative_approved on approve', async () => {
    repo.findLatestRun.mockResolvedValue({
      id: 'run-1',
      status: 'in_progress',
      launch_ready: false,
      checklist: { creative_approved: { completed: false } },
    });
    repo.updateChecklistItem.mockResolvedValue({
      id: 'run-1',
      launch_ready: false,
      checklist: { creative_approved: { completed: true } },
    });
    const out = await bridge.onCreativeApproved({
      clientId: 'c1',
      externalCampaignId: 'CAMP-01',
      reviewedBy: 'client@x.vn',
    });
    expect(out.synced).toBe(true);
    expect(repo.updateChecklistItem).toHaveBeenCalledWith(
      'run-1',
      'creative_approved',
      expect.objectContaining({ completed: true }),
    );
  });

  it('idempotent when already completed', async () => {
    repo.findLatestRun.mockResolvedValue({
      id: 'run-1',
      status: 'in_progress',
      launch_ready: false,
      checklist: { creative_approved: { completed: true } },
    });
    const out = await bridge.onCreativeApproved({
      clientId: 'c1',
      externalCampaignId: 'CAMP-01',
      reviewedBy: 'client@x.vn',
    });
    expect(out.idempotent).toBe(true);
    expect(repo.updateChecklistItem).not.toHaveBeenCalled();
  });
});
