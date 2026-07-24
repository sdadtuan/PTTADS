import { MetaOpsWebhookService } from './meta-ops-webhook.service';
import { MetaWebhookRepository } from './meta-webhook.repository';

describe('MetaOpsWebhookService', () => {
  const repo = {
    pgMetaAlertsReady: jest.fn(),
    resolveClientIdByAdAccount: jest.fn(),
    insertOpsAlert: jest.fn(),
  } as unknown as MetaWebhookRepository;

  const service = new MetaOpsWebhookService(repo);

  beforeEach(() => {
    jest.resetAllMocks();
    process.env.PTT_META_OPS_WEBHOOKS = '1';
  });

  it('skips when flag off', async () => {
    process.env.PTT_META_OPS_WEBHOOKS = '0';
    const out = await service.processPayload({});
    expect(out.skipped).toBe(true);
    expect(out.created).toBe(0);
  });

  it('returns not ready when meta_alerts missing', async () => {
    (repo.pgMetaAlertsReady as jest.Mock).mockResolvedValue(false);
    const out = await service.processPayload({});
    expect(out.ok).toBe(false);
    expect(out.reason).toBe('meta_alerts_not_ready');
  });

  it('creates account disabled alert', async () => {
    (repo.pgMetaAlertsReady as jest.Mock).mockResolvedValue(true);
    (repo.resolveClientIdByAdAccount as jest.Mock).mockResolvedValue('client-1');
    (repo.insertOpsAlert as jest.Mock).mockResolvedValue({
      ok: true,
      created: true,
      alert_id: 'a1',
    });

    const out = await service.processPayload({
      object: 'ad_account',
      entry: [
        {
          id: '123',
          changes: [
            {
              field: 'account_update',
              value: {
                account_id: 'act_123',
                account_status: 2,
                disable_reason: 'policy_violation',
              },
            },
          ],
        },
      ],
    });

    expect(out.ok).toBe(true);
    expect(out.events).toBe(1);
    expect(out.created).toBe(1);
    expect(repo.insertOpsAlert).toHaveBeenCalledWith(
      expect.objectContaining({
        alertType: 'meta_account_disabled',
        severity: 'danger',
        clientId: 'client-1',
      }),
    );
  });

  it('skips unresolved client', async () => {
    (repo.pgMetaAlertsReady as jest.Mock).mockResolvedValue(true);
    (repo.resolveClientIdByAdAccount as jest.Mock).mockResolvedValue(null);

    const out = await service.processPayload({
      object: 'ad_account',
      entry: [
        {
          id: '123',
          changes: [
            {
              field: 'account_update',
              value: {
                account_id: 'act_123',
                account_status: 2,
              },
            },
          ],
        },
      ],
    });

    expect(out.events).toBe(1);
    expect(out.created).toBe(0);
    expect(out.results[0]).toMatchObject({ ok: false, error: 'client_not_resolved' });
  });
});
