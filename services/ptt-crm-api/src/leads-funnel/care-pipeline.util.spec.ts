import {
  carePipelineState,
  presalesCareGateState,
  serializeStagesDone,
} from './care-pipeline.util';

describe('care-pipeline.util', () => {
  it('presales gate incomplete before first_contact done', () => {
    const gate = presalesCareGateState('first_contact', '{}');
    expect(gate.complete).toBe(false);
    expect(gate.missing_keys).toContain('first_contact');
  });

  it('presales gate complete when first_contact in done json', () => {
    const done = serializeStagesDone({ first_contact: '2026-07-23 10:00:00' });
    const gate = presalesCareGateState('first_contact', done);
    expect(gate.complete).toBe(true);
  });

  it('care pipeline marks B2 complete', () => {
    const done = serializeStagesDone({ first_contact: '2026-07-23 10:00:00' });
    const pipe = carePipelineState('first_contact', 'first_contact', done);
    expect(pipe.all_complete).toBe(true);
    expect(pipe.stages[0]?.done).toBe(true);
  });
});
