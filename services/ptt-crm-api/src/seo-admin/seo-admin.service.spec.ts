import { BadRequestException } from '@nestjs/common';
import { SeoAdminService } from './seo-admin.service';
import { SeoAdminRepository } from './seo-admin.repository';
import { JobQueueRepository } from '../webhooks/job-queue.repository';

describe('SeoAdminService', () => {
  const repo = {
    hubSummary: jest.fn(),
    getClientWorkspace: jest.fn(),
    getSettings: jest.fn(),
    upsertSettings: jest.fn(),
    listClientTasks: jest.fn(),
    createSyncRun: jest.fn(),
  } as unknown as SeoAdminRepository;

  const jobQueue = {
    enqueueSeoSyncJob: jest.fn(),
  } as unknown as JobQueueRepository;

  const service = new SeoAdminService(repo, jobQueue);

  beforeEach(() => {
    jest.resetAllMocks();
  });

  it('lists clients from hub summary', async () => {
    (repo.hubSummary as jest.Mock).mockResolvedValue({
      ok: true,
      clients: [{ customer_id: 1 }],
    });
    const out = await service.listClients({});
    expect(out.total).toBe(1);
    expect(out.clients[0].customer_id).toBe(1);
  });

  it('rejects invalid sync source', async () => {
    await expect(service.triggerSync(5, 'bing')).rejects.toBeInstanceOf(BadRequestException);
  });

  it('enqueues gsc sync job', async () => {
    (repo.createSyncRun as jest.Mock).mockResolvedValue(99);
    (jobQueue.enqueueSeoSyncJob as jest.Mock).mockResolvedValue({
      id: 'job-1',
      job_type: 'seo_gsc_sync',
      status: 'pending',
    });
    const out = await service.triggerSync(5, 'gsc');
    expect(out.ok).toBe(true);
    expect(out.mode).toBe('queue');
    expect(out.job_id).toBe('job-1');
    expect(jobQueue.enqueueSeoSyncJob).toHaveBeenCalledWith(
      expect.objectContaining({ jobType: 'seo_gsc_sync' }),
    );
  });
});
