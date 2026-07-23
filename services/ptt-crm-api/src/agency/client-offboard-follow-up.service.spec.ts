import { ClientOffboardFollowUpService } from './client-offboard-follow-up.service';

describe('ClientOffboardFollowUpService', () => {
  const jobQueue = {
    cancelPendingJobsForClient: jest.fn(),
  };
  const temporal = {
    onboardingWorkflowId: jest.fn(),
    cancelWorkflow: jest.fn(),
  };
  const service = new ClientOffboardFollowUpService(jobQueue as never, temporal as never);

  beforeEach(() => {
    jest.resetAllMocks();
    temporal.onboardingWorkflowId.mockReturnValue('client-onboarding-c1');
    jobQueue.cancelPendingJobsForClient.mockResolvedValue(2);
    temporal.cancelWorkflow.mockResolvedValue(true);
  });

  it('cancels pending jobs and onboarding workflow', async () => {
    const out = await service.run('c1');
    expect(jobQueue.cancelPendingJobsForClient).toHaveBeenCalledWith('c1');
    expect(temporal.onboardingWorkflowId).toHaveBeenCalledWith('c1');
    expect(temporal.cancelWorkflow).toHaveBeenCalledWith('client-onboarding-c1', 'client_offboarded');
    expect(out).toEqual({ jobs_cancelled: 2, workflow_cancelled: true });
  });
});
