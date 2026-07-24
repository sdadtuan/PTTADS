import { ServiceUnavailableException } from '@nestjs/common';
import { MetaCapiEventsService, MetaTrackingService } from './meta-tracking.service';
import { MetaTrackingRepository } from './meta-tracking.repository';

describe('MetaTrackingService', () => {
  const repo = {
    pgCapiEventLogReady: jest.fn(),
    countCapiByStatus: jest.fn(),
    avgCapiLatencyMs: jest.fn(),
    listTrackingAccounts: jest.fn(),
    listCapiEvents: jest.fn(),
  } as unknown as MetaTrackingRepository;

  beforeEach(() => {
    jest.resetAllMocks();
    delete process.env.PTT_META_TRACKING_ENABLED;
  });

  it('returns disabled payload when tracking flag off', async () => {
    process.env.PTT_META_TRACKING_ENABLED = '0';
    const svc = new MetaTrackingService(repo);
    const out = await svc.getHealth({});
    expect(out.ok).toBe(true);
    expect(out.disabled).toBe(true);
    expect(out.accounts).toEqual([]);
    expect(repo.pgCapiEventLogReady).not.toHaveBeenCalled();
  });

  it('aggregates health when enabled', async () => {
    process.env.PTT_META_TRACKING_ENABLED = '1';
    (repo.pgCapiEventLogReady as jest.Mock).mockResolvedValue(true);
    (repo.countCapiByStatus as jest.Mock).mockResolvedValue({ sent: 5, failed: 0 });
    (repo.avgCapiLatencyMs as jest.Mock).mockResolvedValue(200);
    (repo.listTrackingAccounts as jest.Mock).mockResolvedValue([
      {
        client_id: 'c1',
        channel_account_id: 'a1',
        pixel_id: 'px1',
        page_id: null,
        capi_enabled: true,
        last_sent_at: null,
        pixel_test_ok: null,
        client_code: 'C1',
        client_name: 'Client',
      },
    ]);

    const svc = new MetaTrackingService(repo);
    const out = await svc.getHealth({ window_days: '7' });
    expect(out.ok).toBe(true);
    expect(out.window_days).toBe(7);
    expect(out.global.sent).toBe(5);
    expect(out.accounts).toHaveLength(1);
    expect(out.attribution_model).toBe('last_touch_crm');
  });

  it('throws when capi log table missing', async () => {
    process.env.PTT_META_TRACKING_ENABLED = '1';
    (repo.pgCapiEventLogReady as jest.Mock).mockResolvedValue(false);
    const svc = new MetaTrackingService(repo);
    await expect(svc.getHealth({})).rejects.toBeInstanceOf(ServiceUnavailableException);
  });
});

describe('MetaCapiEventsService', () => {
  const repo = {
    pgCapiEventLogReady: jest.fn(),
    listCapiEvents: jest.fn(),
    getCapiEventById: jest.fn(),
    resetCapiEventPending: jest.fn(),
    listFlushableCapiEvents: jest.fn(),
  } as unknown as MetaTrackingRepository;

  const jobQueue = {
    enqueueCapiDispatch: jest.fn(),
  } as unknown as import('../webhooks/job-queue.repository').JobQueueRepository;

  beforeEach(() => {
    jest.resetAllMocks();
    delete process.env.PTT_META_TRACKING_ENABLED;
    delete process.env.PTT_CAPI_STUB;
    delete process.env.PTT_CAPI_ENABLED;
  });

  it('returns empty list when disabled', async () => {
    const svc = new MetaCapiEventsService(repo, jobQueue);
    const out = await svc.listEvents({});
    expect(out.disabled).toBe(true);
    expect(out.events).toEqual([]);
  });

  it('lists events when enabled', async () => {
    process.env.PTT_META_TRACKING_ENABLED = '1';
    (repo.pgCapiEventLogReady as jest.Mock).mockResolvedValue(true);
    (repo.listCapiEvents as jest.Mock).mockResolvedValue([
      {
        id: 'e1',
        client_id: 'c1',
        event_name: 'Lead',
        event_id: 'lead-1',
        lead_id: 1,
        pixel_id: 'px',
        status: 'sent',
        error_message: null,
        created_at: '2026-07-24T00:00:00.000Z',
        sent_at: '2026-07-24T00:00:01.000Z',
      },
    ]);
    const svc = new MetaCapiEventsService(repo, jobQueue);
    const out = await svc.listEvents({ limit: '10' });
    expect(out.ok).toBe(true);
    expect(out.count).toBe(1);
  });

  it('retries failed event and enqueues capi_dispatch', async () => {
    process.env.PTT_META_TRACKING_ENABLED = '1';
    process.env.PTT_CAPI_STUB = '1';
    (repo.pgCapiEventLogReady as jest.Mock).mockResolvedValue(true);
    (repo.getCapiEventById as jest.Mock).mockResolvedValue({
      id: 'log-1',
      client_id: 'c1',
      event_name: 'Lead',
      event_id: 'lead-1',
      lead_id: 1,
      pixel_id: 'px',
      status: 'failed',
      error_message: 'timeout',
      created_at: '2026-07-24T00:00:00.000Z',
      sent_at: null,
    });
    (repo.resetCapiEventPending as jest.Mock).mockResolvedValue({
      id: 'log-1',
      client_id: 'c1',
      event_name: 'Lead',
      event_id: 'lead-1',
      lead_id: 1,
      pixel_id: 'px',
      status: 'pending',
      error_message: null,
      created_at: '2026-07-24T00:00:00.000Z',
      sent_at: null,
    });
    (jobQueue.enqueueCapiDispatch as jest.Mock).mockResolvedValue({
      id: 'job-1',
      job_type: 'capi_dispatch',
      status: 'pending',
      created: true,
    });

    const svc = new MetaCapiEventsService(repo, jobQueue);
    const out = await svc.retryEvent('log-1');
    expect(out.ok).toBe(true);
    expect(out.status).toBe('pending');
    expect(out.job?.id).toBe('job-1');
    expect(jobQueue.enqueueCapiDispatch).toHaveBeenCalledWith(
      expect.objectContaining({
        payload: expect.objectContaining({ capi_log_id: 'log-1', client_id: 'c1' }),
      }),
    );
  });

  it('flush enqueues jobs for flushable rows', async () => {
    process.env.PTT_META_TRACKING_ENABLED = '1';
    process.env.PTT_CAPI_STUB = '1';
    (repo.pgCapiEventLogReady as jest.Mock).mockResolvedValue(true);
    (repo.listFlushableCapiEvents as jest.Mock).mockResolvedValue([
      {
        id: 'log-2',
        client_id: 'c1',
        event_name: 'Lead',
        event_id: 'lead-2',
        lead_id: 2,
        pixel_id: 'px',
        status: 'failed',
        error_message: 'err',
        created_at: '2026-07-24T00:00:00.000Z',
        sent_at: null,
      },
    ]);
    (repo.resetCapiEventPending as jest.Mock).mockImplementation(async (id: string) => ({
      id,
      client_id: 'c1',
      event_name: 'Lead',
      event_id: 'lead-2',
      lead_id: 2,
      pixel_id: 'px',
      status: 'pending',
      error_message: null,
      created_at: '2026-07-24T00:00:00.000Z',
      sent_at: null,
    }));
    (jobQueue.enqueueCapiDispatch as jest.Mock).mockResolvedValue({
      id: 'job-2',
      job_type: 'capi_dispatch',
      status: 'pending',
      created: true,
    });

    const svc = new MetaCapiEventsService(repo, jobQueue);
    const out = await svc.flushPending({});
    expect(out.ok).toBe(true);
    expect(out.processed).toBe(1);
    expect(out.enqueued).toBe(1);
  });
});
