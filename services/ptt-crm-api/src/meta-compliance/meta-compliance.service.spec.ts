import { MetaComplianceService } from './meta-compliance.service';
import { MetaComplianceRepository } from './meta-compliance.repository';

describe('MetaComplianceService', () => {
  const repo = {
    clientExists: jest.fn(),
    fetchClient: jest.fn(),
    fetchChannelAccounts: jest.fn(),
    fetchPerformanceSummary: jest.fn(),
    fetchOpenAlerts: jest.fn(),
    fetchRecentCampaignWrites: jest.fn(),
    fetchTrackingSummary: jest.fn(),
  } as unknown as MetaComplianceRepository;

  const service = new MetaComplianceService(repo);

  beforeEach(() => {
    jest.resetAllMocks();
    process.env.PTT_META_COMPLIANCE_EXPORT_ENABLED = '1';
  });

  it('builds export bundle with redaction note', async () => {
    (repo.clientExists as jest.Mock).mockResolvedValue(true);
    (repo.fetchClient as jest.Mock).mockResolvedValue({ id: 'c1', code: 'ACME', name: 'Acme' });
    (repo.fetchChannelAccounts as jest.Mock).mockResolvedValue([
      { access_token: '[REDACTED]', external_account_id: 'act_1' },
    ]);
    (repo.fetchPerformanceSummary as jest.Mock).mockResolvedValue({ spend: 1000, leads_crm: 10 });
    (repo.fetchOpenAlerts as jest.Mock).mockResolvedValue([]);
    (repo.fetchRecentCampaignWrites as jest.Mock).mockResolvedValue([]);
    (repo.fetchTrackingSummary as jest.Mock).mockResolvedValue({ capi_sent: 5 });

    const out = await service.exportBundle('c1', '30');
    expect(out.ok).toBe(true);
    expect(out.export_version).toBe('1.0');
    expect(out.redaction.tokens_redacted).toBe(true);
    expect(out.channel_accounts[0].access_token).toBe('[REDACTED]');
  });
});
