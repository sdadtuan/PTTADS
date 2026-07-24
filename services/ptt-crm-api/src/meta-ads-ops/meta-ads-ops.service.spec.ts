import { MetaAdsOpsService } from './meta-ads-ops.service';
import { MetaAdsOpsRepository } from './meta-ads-ops.repository';
import { CampaignWritesService } from '../campaign-writes/campaign-writes.service';
import { MetaTrackingRepository } from '../meta-tracking/meta-tracking.repository';

describe('MetaAdsOpsService', () => {
  const repo = {
    clientExists: jest.fn(),
    isTenantLocked: jest.fn(),
    fetchMetaAccount: jest.fn(),
    fetchApprovedCreative: jest.fn(),
    findWriteRequest: jest.fn(),
  } as unknown as MetaAdsOpsRepository;

  const trackingRepo = {} as unknown as MetaTrackingRepository;

  const writes = {
    submit: jest.fn(),
  } as unknown as CampaignWritesService;

  const service = new MetaAdsOpsService(repo, trackingRepo, writes);

  beforeEach(() => {
    jest.resetAllMocks();
    process.env.PTT_META_ADS_OPS_ENABLED = '1';
  });

  it('returns disabled templates when flag off', () => {
    process.env.PTT_META_ADS_OPS_ENABLED = '0';
    const out = service.listTemplates();
    expect(out.disabled).toBe(true);
    expect(out.templates).toEqual([]);
  });

  it('lists launch templates when enabled', () => {
    const out = service.listTemplates();
    expect(out.templates.length).toBeGreaterThan(0);
    expect(out.templates[0].id).toBe('re_lead_default');
  });

  it('builds deep link url', async () => {
    (repo.fetchMetaAccount as jest.Mock).mockResolvedValue({ external_account_id: 'act_123' });
    const out = await service.getDeepLink({ client_id: 'c1' });
    expect(out.url).toContain('adsmanager/manage/campaigns');
    expect(out.url).toContain('act=123');
  });
});
