import { BadRequestException, ServiceUnavailableException } from '@nestjs/common';
import { MetaConversionRulesService } from './meta-conversion-rules.service';
import { MetaTrackingRepository } from './meta-tracking.repository';

describe('MetaConversionRulesService', () => {
  const repo = {
    pgMetaConversionRulesReady: jest.fn(),
    listConversionRules: jest.fn(),
    createConversionRule: jest.fn(),
    patchConversionRule: jest.fn(),
  } as unknown as MetaTrackingRepository;

  beforeEach(() => {
    jest.resetAllMocks();
    delete process.env.PTT_META_TRACKING_ENABLED;
  });

  it('returns disabled payload when tracking flag off', async () => {
    const svc = new MetaConversionRulesService(repo);
    const out = await svc.listRules({});
    expect(out.ok).toBe(true);
    expect(out.disabled).toBe(true);
    expect(out.rules).toEqual([]);
  });

  it('lists rules when enabled', async () => {
    process.env.PTT_META_TRACKING_ENABLED = '1';
    (repo.pgMetaConversionRulesReady as jest.Mock).mockResolvedValue(true);
    (repo.listConversionRules as jest.Mock).mockResolvedValue([
      {
        id: 'r1',
        client_id: null,
        lead_status: 'qualified',
        event_name: 'CompleteRegistration',
        enabled: true,
        require_meta_attribution: true,
        value_vnd: 0,
        notes: '',
        created_at: '2026-07-24T00:00:00.000Z',
        updated_at: '2026-07-24T00:00:00.000Z',
      },
    ]);
    const svc = new MetaConversionRulesService(repo);
    const out = await svc.listRules({});
    expect(out.count).toBe(1);
    expect(out.rules[0]?.event_name).toBe('CompleteRegistration');
  });

  it('throws when rules table missing', async () => {
    process.env.PTT_META_TRACKING_ENABLED = '1';
    (repo.pgMetaConversionRulesReady as jest.Mock).mockResolvedValue(false);
    const svc = new MetaConversionRulesService(repo);
    await expect(svc.listRules({})).rejects.toBeInstanceOf(ServiceUnavailableException);
  });

  it('validates create body', async () => {
    process.env.PTT_META_TRACKING_ENABLED = '1';
    (repo.pgMetaConversionRulesReady as jest.Mock).mockResolvedValue(true);
    const svc = new MetaConversionRulesService(repo);
    await expect(svc.createRule({ lead_status: '', event_name: '' })).rejects.toBeInstanceOf(
      BadRequestException,
    );
  });

  it('patches rule fields', async () => {
    process.env.PTT_META_TRACKING_ENABLED = '1';
    (repo.pgMetaConversionRulesReady as jest.Mock).mockResolvedValue(true);
    (repo.patchConversionRule as jest.Mock).mockResolvedValue({
      id: 'r1',
      client_id: null,
      lead_status: 'qualified',
      event_name: 'CompleteRegistration',
      enabled: false,
      require_meta_attribution: true,
      value_vnd: 1000,
      notes: '',
      created_at: '2026-07-24T00:00:00.000Z',
      updated_at: '2026-07-24T00:00:00.000Z',
    });
    const svc = new MetaConversionRulesService(repo);
    const out = await svc.patchRule('r1', { enabled: false, value_vnd: 1000 });
    expect(out.rule.enabled).toBe(false);
    expect(out.rule.value_vnd).toBe(1000);
  });
});
