import { EmailMarketingCampaignRepository } from './email-marketing-campaign.repository';
import { EmailMarketingEnterpriseRepository } from './email-marketing-enterprise.repository';
import { EmailMarketingOpsRepository } from './email-marketing-ops.repository';
import { EmailMarketingRepository } from './email-marketing.repository';
import { EmailMarketingService } from './email-marketing.service';

describe('EmailMarketingService', () => {
  const repo = {
    hubSummary: jest.fn(),
    governance: jest.fn(),
  } as unknown as jest.Mocked<EmailMarketingRepository>;

  const ops = {
    listEmailClients: jest.fn(),
    listWorkspaces: jest.fn(),
    createWorkspace: jest.fn(),
    importContacts: jest.fn(),
    recordConsent: jest.fn(),
    captureLead: jest.fn(),
  } as unknown as jest.Mocked<EmailMarketingOpsRepository>;

  const campaign = {
    listSegments: jest.fn(),
    createSegment: jest.fn(),
    computeSegment: jest.fn(),
    listTemplates: jest.fn(),
    createTemplate: jest.fn(),
    getTemplate: jest.fn(),
    updateTemplate: jest.fn(),
    preflightTemplate: jest.fn(),
    listCampaigns: jest.fn(),
    createCampaign: jest.fn(),
    getCampaign: jest.fn(),
    preflightCampaign: jest.fn(),
    submitCampaign: jest.fn(),
  } as unknown as jest.Mocked<EmailMarketingCampaignRepository>;

  const enterprise = {
    listJourneys: jest.fn(),
    getJourney: jest.fn(),
    createJourney: jest.fn(),
    updateJourney: jest.fn(),
    activateJourney: jest.fn(),
    listDomains: jest.fn(),
    registerDomain: jest.fn(),
    verifyDomain: jest.fn(),
    pauseDomain: jest.fn(),
    reportsSummary: jest.fn(),
    campaignReport: jest.fn(),
    deliverabilityReport: jest.fn(),
    engagementSeries: jest.fn(),
    getReportSchedule: jest.fn(),
    listReportSchedules: jest.fn(),
    createReportSchedule: jest.fn(),
    updateReportSchedule: jest.fn(),
    deleteReportSchedule: jest.fn(),
  } as unknown as jest.Mocked<EmailMarketingEnterpriseRepository>;

  const sendOrchestrator = {
    onCampaignSubmitted: jest.fn(),
    onCampaignApproved: jest.fn(),
    staffApproveAndSend: jest.fn(),
    signalRejectOnly: jest.fn(),
  };

  const jobQueue = {
    enqueueDnsVerify: jest.fn().mockResolvedValue({ job_id: 'job-1' }),
    enqueueClickhouseExport: jest.fn().mockResolvedValue({ job_id: 'job-ch', mode: 'queue' }),
    enqueueReportScheduleRun: jest.fn().mockResolvedValue({ job_id: 'job-rpt' }),
    enqueueExperimentRollup: jest.fn().mockResolvedValue({ job_id: 'job-exp' }),
  };

  const experiments = {
    listExperiments: jest.fn(),
    getExperiment: jest.fn(),
    getRunningExperimentForCampaign: jest.fn(),
    createExperiment: jest.fn(),
    startExperiment: jest.fn(),
    declareWinner: jest.fn(),
  };

  const temporalJourney = {
    start: jest.fn().mockResolvedValue({ started: false }),
  };

  function makeService() {
    return new EmailMarketingService(
      repo,
      ops,
      campaign,
      enterprise,
      experiments as never,
      sendOrchestrator as never,
      jobQueue as never,
      temporalJourney as never,
    );
  }

  afterEach(() => {
    jest.clearAllMocks();
  });

  it('returns hub with default 28-day window', async () => {
    repo.hubSummary.mockResolvedValue({
      ok: true,
      schema_ready: true,
      summary: {
        workspaces: 1,
        contacts: 0,
        emails_sent: 0,
        open_rate_pct: 0,
        complaint_rate_pct: 0,
        pending_approvals: 0,
        send_queue_lag_minutes: 0,
        revenue_attrib: 0,
      },
      clients: [],
      pending_approvals: [],
      send_calendar: [],
      alerts: [],
      filters: { days: 28, client_id: null, domain: null },
    });
    const svc = makeService();
    const out = await svc.hub({});
    expect(repo.hubSummary).toHaveBeenCalledWith({ clientId: undefined, days: 28, domain: undefined });
    expect(out.ok).toBe(true);
  });

  it('caps days parameter at 365', async () => {
    repo.hubSummary.mockResolvedValue({
      ok: true,
      schema_ready: false,
      summary: {
        workspaces: 0,
        contacts: 0,
        emails_sent: 0,
        open_rate_pct: 0,
        complaint_rate_pct: 0,
        pending_approvals: 0,
        send_queue_lag_minutes: 0,
        revenue_attrib: 0,
      },
      clients: [],
      pending_approvals: [],
      send_calendar: [],
      alerts: [],
      filters: { days: 365, client_id: null, domain: null },
    });
    const svc = makeService();
    await svc.hub({ days: 9999 });
    expect(repo.hubSummary).toHaveBeenCalledWith(expect.objectContaining({ days: 365 }));
  });

  it('delegates workspace create to ops repository', async () => {
    ops.createWorkspace.mockResolvedValue({
      id: 'ws-1',
      client_id: 'c-1',
      client_code: 'ABC',
      client_name: 'ABC Corp',
      name: 'ABC Email',
      default_from_name: null,
      default_from_email: null,
      default_reply_to: null,
      esp_provider: 'sendgrid',
      daily_send_cap: 10000,
      frequency_cap_7d: 5,
      timezone: 'Asia/Ho_Chi_Minh',
      status: 'active',
      contact_count: 0,
      subscriber_count: 0,
      suppressed_count: 0,
      created_at: '',
      updated_at: '',
    });
    const svc = makeService();
    const out = await svc.createWorkspace({
      clientId: 'c-1',
      name: 'ABC Email',
      actor: 'staff@test.local',
    });
    expect(out.id).toBe('ws-1');
    expect(ops.createWorkspace).toHaveBeenCalled();
  });

  it('delegates segment compute to campaign repository', async () => {
    campaign.computeSegment.mockResolvedValue({
      ok: true,
      segment_id: 'seg-1',
      member_count: 3,
      excluded_suppression: 0,
      excluded_consent: 1,
    });
    const svc = makeService();
    const out = await svc.computeSegment('seg-1', 'staff@test.local');
    expect(out.member_count).toBe(3);
    expect(campaign.computeSegment).toHaveBeenCalledWith('seg-1', 'staff@test.local');
  });

  it('delegates reports summary to enterprise repository', async () => {
    enterprise.reportsSummary.mockResolvedValue({
      ok: true,
      days: 28,
      client_id: null,
      sent: 10,
      delivered: 8,
      opens: 3,
      clicks: 1,
      unsubscribes: 0,
      open_rate_pct: 30,
      click_rate_pct: 10,
      revenue_attrib: 0,
    });
    const svc = makeService();
    const out = await svc.reportsSummary({ days: 28 });
    expect(out.sent).toBe(10);
    expect(enterprise.reportsSummary).toHaveBeenCalledWith({ clientId: undefined, days: 28 });
  });
});
