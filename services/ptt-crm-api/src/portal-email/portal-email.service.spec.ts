import { ForbiddenException } from '@nestjs/common';
import { PortalEmailRepository } from './portal-email.repository';
import { PortalEmailService } from './portal-email.service';

describe('PortalEmailService', () => {
  const repo = {
    schemaReady: jest.fn(),
    hasWorkspace: jest.fn(),
    dashboard: jest.fn(),
    listCampaigns: jest.fn(),
    pendingApprovals: jest.fn(),
    approveCampaign: jest.fn(),
    rejectCampaign: jest.fn(),
    approvalPreview: jest.fn(),
    campaignStats: jest.fn(),
    reportsSummary: jest.fn(),
  } as unknown as jest.Mocked<PortalEmailRepository>;

  const sendOrchestrator = {
    onCampaignApproved: jest.fn().mockResolvedValue({ prepare_job_id: 'job-1', temporal: 'stub' }),
    signalRejectOnly: jest.fn().mockResolvedValue(undefined),
  };

  const viewer = {
    sub: 'u1',
    email: 'viewer@test.local',
    client_id: 'client-1',
    role: 'viewer' as const,
    iat: 0,
    exp: 9999999999,
  };

  const approver = { ...viewer, email: 'approver@test.local', role: 'approver' as const };

  afterEach(() => jest.clearAllMocks());

  it('returns disabled dashboard when schema not ready', async () => {
    repo.schemaReady.mockResolvedValue(false);
    const svc = new PortalEmailService(repo, sendOrchestrator as never);
    const out = await svc.dashboard(viewer);
    expect(out.email_enabled).toBe(false);
    expect(out.client_id).toBe('client-1');
  });

  it('blocks approve for viewer role', async () => {
    const svc = new PortalEmailService(repo, sendOrchestrator as never);
    await expect(svc.approveCampaign(viewer, 'camp-1')).rejects.toBeInstanceOf(ForbiddenException);
  });

  it('approves campaign for approver role', async () => {
    repo.approveCampaign.mockResolvedValue({
      id: 'camp-1',
      name: 'Test',
      status: 'approved',
      audience_count: 100,
      scheduled_at: null,
      sent_at: null,
      updated_at: '',
    });
    const svc = new PortalEmailService(repo, sendOrchestrator as never);
    const out = await svc.approveCampaign(approver, 'camp-1');
    expect(out.campaign.status).toBe('approved');
    expect(repo.approveCampaign).toHaveBeenCalledWith({
      clientId: 'client-1',
      campaignId: 'camp-1',
      actor: 'approver@test.local',
    });
  });

  it('returns approval preview for viewer', async () => {
    repo.schemaReady.mockResolvedValue(true);
    repo.approvalPreview.mockResolvedValue({
      campaign_id: 'camp-1',
      name: 'Preview',
      subject_template: 'Hello',
      html_body: '<p>Hi</p>',
      audience_count: 50,
      scheduled_at: null,
      template_name: 'T1',
      status: 'pending_approval',
    });
    const svc = new PortalEmailService(repo, sendOrchestrator as never);
    const out = await svc.approvalPreview(viewer, 'camp-1');
    expect(out.ok).toBe(true);
    expect(out.html_body).toContain('Hi');
  });
});
