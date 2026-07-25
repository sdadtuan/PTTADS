import { NotFoundException, ServiceUnavailableException } from '@nestjs/common';
import { ZaloLeadsService } from './zalo-leads.service';

describe('ZaloLeadsService', () => {
  const repo = {
    tablesReady: jest.fn(),
    listLeads: jest.fn(),
    listForms: jest.fn(),
    resolveFormContext: jest.fn(),
    listLeadEvents: jest.fn(),
  };
  const sideEffects = {
    enqueueZaloFormLeadPoll: jest.fn(),
  };
  const service = new ZaloLeadsService(repo as never, sideEffects as never);

  beforeEach(() => {
    jest.resetAllMocks();
    repo.tablesReady.mockResolvedValue(true);
  });

  it('listLeads returns rows', async () => {
    repo.listLeads.mockResolvedValue({ rows: [{ id: '1' }], total: 1 });
    const out = await service.listLeads({ client_id: 'c1' });
    expect(out.ok).toBe(true);
    expect(out.total).toBe(1);
  });

  it('pollForm enqueues job', async () => {
    repo.resolveFormContext.mockResolvedValue({ client_id: 'c1', oa_id: 'oa', form_id: 'f1' });
    sideEffects.enqueueZaloFormLeadPoll.mockResolvedValue([
      { id: 'job-1', job_type: 'zalo_form_lead_poll', status: 'pending', created: true },
    ]);
    const out = await service.pollForm('f1', { client_id: 'c1' });
    expect(out.ok).toBe(true);
    expect(out.jobs_enqueued).toHaveLength(1);
  });

  it('pollForm throws when form missing', async () => {
    repo.resolveFormContext.mockResolvedValue(null);
    await expect(service.pollForm('missing', {})).rejects.toBeInstanceOf(NotFoundException);
  });

  it('throws when tables not ready', async () => {
    repo.tablesReady.mockResolvedValue(false);
    await expect(service.listForms({})).rejects.toBeInstanceOf(ServiceUnavailableException);
  });
});
