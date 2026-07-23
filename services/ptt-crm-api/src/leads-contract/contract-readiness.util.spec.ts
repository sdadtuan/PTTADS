import { buildReadinessChecks } from './contract-readiness.util';

describe('buildReadinessChecks', () => {
  it('requires all presales stages and marketing plan', () => {
    const checks = buildReadinessChecks({
      careStageCurrent: 'first_contact',
      careStagesDoneJson: JSON.stringify({ first_contact: { care_status: 'da_lien_he_thanh_cong' } }),
      presales: {
        stage: 'proposal',
        status: 'active',
        tasksProgress: {
          lead: { total: 1, done: 1 },
          consult: { total: 1, done: 1 },
          proposal: { total: 1, done: 0 },
        },
      },
      marketingPlan: null,
      contract: null,
      pendingApproval: null,
    });
    expect(checks.find((c) => c.key === 'presales_proposal')?.ok).toBe(false);
    expect(checks.find((c) => c.key === 'marketing_plan')?.ok).toBe(false);
  });
});
