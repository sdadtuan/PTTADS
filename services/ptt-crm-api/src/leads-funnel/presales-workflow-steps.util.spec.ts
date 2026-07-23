import { listPresalesServiceSlugs, workflowStepsForService } from './presales-workflow-steps.util';

describe('workflowStepsForService', () => {
  it('returns SEO steps for dich-vu-seo-tong-the', () => {
    const steps = workflowStepsForService('dich-vu-seo-tong-the');
    expect(steps.lead[0]?.title).toContain('SEO');
    expect(steps.consult.length).toBeGreaterThan(0);
    expect(steps.proposal.length).toBeGreaterThan(0);
  });

  it('falls back to generic for unknown slug', () => {
    const steps = workflowStepsForService('unknown-slug-xyz');
    expect(steps.lead[0]?.title).toContain('Qualify');
  });

  it('exports 12 service slugs from Python source', () => {
    expect(listPresalesServiceSlugs().length).toBeGreaterThanOrEqual(12);
  });
});
