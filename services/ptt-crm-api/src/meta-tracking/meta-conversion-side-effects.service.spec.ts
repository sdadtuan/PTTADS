import { MetaConversionSideEffectsService } from './meta-conversion-side-effects.service';
import { JobQueueRepository } from '../webhooks/job-queue.repository';

describe('MetaConversionSideEffectsService', () => {
  const jobQueue = {
    enqueueMetaConversionEval: jest.fn(),
  } as unknown as JobQueueRepository;

  beforeEach(() => {
    jest.resetAllMocks();
    delete process.env.PTT_META_TRACKING_ENABLED;
    delete process.env.PTT_CAPI_STUB;
    delete process.env.PTT_CAPI_ENABLED;
  });

  it('skips when tracking disabled', async () => {
    const svc = new MetaConversionSideEffectsService(jobQueue);
    const out = await svc.enqueueConversionEval({
      leadId: 1,
      clientId: '550e8400-e29b-41d4-a716-446655440000',
      oldStatus: 'new',
      newStatus: 'qualified',
    });
    expect(out).toBeNull();
    expect(jobQueue.enqueueMetaConversionEval).not.toHaveBeenCalled();
  });

  it('enqueues meta_conversion_eval on status change', async () => {
    process.env.PTT_META_TRACKING_ENABLED = '1';
    process.env.PTT_CAPI_STUB = '1';
    (jobQueue.enqueueMetaConversionEval as jest.Mock).mockResolvedValue({
      id: 'job-1',
      job_type: 'meta_conversion_eval',
      status: 'pending',
      created: true,
    });
    const svc = new MetaConversionSideEffectsService(jobQueue);
    const out = await svc.enqueueConversionEval({
      leadId: 42,
      clientId: '550e8400-e29b-41d4-a716-446655440000',
      oldStatus: 'new',
      newStatus: 'qualified',
    });
    expect(out?.id).toBe('job-1');
    expect(jobQueue.enqueueMetaConversionEval).toHaveBeenCalled();
  });
});
