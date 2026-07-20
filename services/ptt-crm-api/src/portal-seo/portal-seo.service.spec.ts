import { ForbiddenException, NotFoundException, ServiceUnavailableException } from '@nestjs/common';
import { PortalSeoRepository } from './portal-seo.repository';
import { PortalSeoService } from './portal-seo.service';

describe('PortalSeoService', () => {
  const mockUser = {
    sub: '1',
    email: 'viewer@test.local',
    client_id: '550e8400-e29b-41d4-a716-446655440000',
    role: 'viewer' as const,
    iat: 1,
    exp: 9999999999,
  };

  const repo = {
    customerIdForPortalClient: jest.fn(),
    buildDashboard: jest.fn(),
    listPendingContent: jest.fn(),
    getContentDetail: jest.fn(),
    reviewContent: jest.fn(),
  } as unknown as jest.Mocked<PortalSeoRepository>;

  afterEach(() => {
    jest.restoreAllMocks();
    jest.clearAllMocks();
  });

  it('returns seo_enabled false when client not mapped', async () => {
    process.env.PTT_PORTAL_SEO_ENABLED = '1';
    repo.customerIdForPortalClient.mockResolvedValue(null);
    const svc = new PortalSeoService(repo);
    const out = await svc.summary(mockUser);
    expect(out.seo_enabled).toBe(false);
  });

  it('requires approver role for review', async () => {
    process.env.PTT_PORTAL_SEO_ENABLED = '1';
    const svc = new PortalSeoService(repo);
    await expect(
      svc.reviewContent({ ...mockUser, role: 'viewer' }, '42', { approved: true }),
    ).rejects.toBeInstanceOf(ForbiddenException);
  });

  it('throws when portal SEO disabled', async () => {
    process.env.PTT_PORTAL_SEO_ENABLED = '0';
    const svc = new PortalSeoService(repo);
    await expect(svc.summary(mockUser)).rejects.toBeInstanceOf(ServiceUnavailableException);
  });

  it('loads widgets from PG repository', async () => {
    process.env.PTT_PORTAL_SEO_ENABLED = '1';
    repo.customerIdForPortalClient.mockResolvedValue(1);
    repo.buildDashboard.mockResolvedValue({
      gsc: { clicks: 42, impressions: 100 },
      gsc_trend: [{ clicks: 1 }, { clicks: 2 }, { clicks: 3 }],
      aeo: { coverage_pct: 55 },
      critical_issues: 0,
    });
    repo.listPendingContent.mockResolvedValue([]);

    const svc = new PortalSeoService(repo);
    const out = await svc.widgets(mockUser);
    expect(out.widgets.gsc_clicks?.value).toBe(42);
    expect(out.customer_id).toBe(1);
  });

  it('throws not mapped for executive report when unmapped', async () => {
    process.env.PTT_PORTAL_SEO_ENABLED = '1';
    repo.customerIdForPortalClient.mockResolvedValue(null);
    const svc = new PortalSeoService(repo);
    await expect(svc.executiveReport(mockUser)).rejects.toBeInstanceOf(NotFoundException);
  });
});
