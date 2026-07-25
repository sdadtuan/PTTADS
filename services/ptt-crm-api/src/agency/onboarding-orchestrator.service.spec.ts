import { NotFoundException } from '@nestjs/common';
import { OnboardingOrchestratorService } from './onboarding-orchestrator.service';

describe('OnboardingOrchestratorService', () => {
  const agency = {
    getOnboardingSummary: jest.fn(),
    patchOnboardingItem: jest.fn(),
  };
  const repo = {
    fetchClient: jest.fn(),
    listOnboardingItems: jest.fn(),
  };
  const detectRepo = {
    detectSeo: jest.fn(),
    detectEmail: jest.fn(),
    countLeads: jest.fn(),
  };
  const portalUsers = {
    tableReady: jest.fn(),
    listByClient: jest.fn(),
  };

  const service = new OnboardingOrchestratorService(
    agency as never,
    repo as never,
    detectRepo as never,
    portalUsers as never,
  );

  const clientId = '550e8400-e29b-41d4-a716-446655440000';

  beforeEach(() => {
    jest.resetAllMocks();
    repo.fetchClient.mockResolvedValue({
      id: clientId,
      status: 'onboarding',
      channel_accounts: [
        {
          channel: 'meta',
          has_token: true,
          token_status: 'valid',
          pixel_id: '123456',
        },
      ],
    });
    agency.getOnboardingSummary.mockResolvedValue({
      client_code: 'C001',
      client_name: 'Demo Client',
      items: [
        { item_key: 'ad_account_access', label: 'Ad account', completed: false },
        { item_key: 'bm_access', label: 'BM access', completed: false },
        { item_key: 'pixel_dataset', label: 'Pixel', completed: false },
        { item_key: 'client_approver', label: 'Approver', completed: false },
        { item_key: 'hub_contract', label: 'Hub contract', completed: true },
        { item_key: 'webhook_test', label: 'Webhook', completed: false },
      ],
      linked_lifecycles: [
        {
          lifecycle_id: 42,
          stage: 'onboard',
          service_delivery_url: '/crm/service-delivery/42',
        },
      ],
    });
    portalUsers.tableReady.mockResolvedValue(true);
    portalUsers.listByClient.mockResolvedValue([
      { role: 'approver', active: true },
    ]);
    detectRepo.detectSeo.mockResolvedValue({
      mapped: false,
      customer_id: null,
      gsc_connected: false,
      has_settings: false,
    });
    detectRepo.detectEmail.mockResolvedValue({ workspace: false, verified_domain: false });
    detectRepo.countLeads.mockResolvedValue(3);
  });

  it('returns cross-module steps with auto detection', async () => {
    const out = await service.getOrchestrator(clientId);
    expect(out.client_name).toBe('Demo Client');
    expect(out.steps.length).toBeGreaterThanOrEqual(10);
    const metaToken = out.steps.find((s) => s.key === 'meta_token');
    expect(metaToken?.status).toBe('done');
    expect(metaToken?.auto_detected).toBe(true);
    const webhook = out.steps.find((s) => s.key === 'webhook_test');
    expect(webhook?.status).toBe('done');
    expect(out.progress.required_percent).toBeGreaterThan(0);
  });

  it('throws when client missing', async () => {
    repo.fetchClient.mockResolvedValue(null);
    await expect(service.getOrchestrator(clientId)).rejects.toBeInstanceOf(NotFoundException);
  });

  it('sync auto-ticks checklist items from detection', async () => {
    agency.patchOnboardingItem.mockResolvedValue({ items: [], progress: { total: 6, completed: 3, percent: 50 } });
    repo.listOnboardingItems.mockResolvedValue([
      { item_key: 'ad_account_access', label: 'Ad account', completed: true },
      { item_key: 'bm_access', label: 'BM access', completed: true },
      { item_key: 'pixel_dataset', label: 'Pixel', completed: true },
      { item_key: 'client_approver', label: 'Approver', completed: true },
      { item_key: 'hub_contract', label: 'Hub contract', completed: true },
      { item_key: 'webhook_test', label: 'Webhook', completed: true },
    ]);

    const out = await service.syncOrchestrator(clientId);
    expect(out.synced_items).toEqual(
      expect.arrayContaining(['ad_account_access', 'bm_access', 'pixel_dataset', 'client_approver', 'webhook_test']),
    );
    expect(agency.patchOnboardingItem).toHaveBeenCalledWith(
      clientId,
      'ad_account_access',
      expect.objectContaining({ completed: true, completed_by: 'orchestrator:auto' }),
    );
  });
});
