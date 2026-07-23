import { validateOfficialTmmt } from './lifecycle-marketing-plan.util';

describe('lifecycle-marketing-plan.util', () => {
  it('rejects missing plan', () => {
    const gate = validateOfficialTmmt(null);
    expect(gate.ok).toBe(false);
  });

  it('accepts filled official TMMT', () => {
    const prof = Object.fromEntries(
      [
        'market_context',
        'tam_sam_som',
        'geo_behavior',
        'segmentation_icp',
        'personas_roles',
        'jobs_to_be_done',
        'pains_desired_outcomes',
        'buy_triggers_obstacles',
        'criteria_vs_alternatives',
        'insights_evidence',
        'segment_priorities',
        'success_hypotheses_next',
      ].map((k) => [k, 'filled']),
    );
    const gate = validateOfficialTmmt({
      strategy_framework_json: JSON.stringify({ target_market: 'B2B SaaS' }),
      target_market_prof_json: JSON.stringify(prof),
    });
    expect(gate.ok).toBe(true);
  });
});
