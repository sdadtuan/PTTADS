import { validatePresalesConsultAdvance } from './presales-consult-gate.util';

describe('validatePresalesConsultAdvance', () => {
  it('blocks when lead task incomplete', () => {
    const gate = validatePresalesConsultAdvance({
      leadTaskDone: false,
      sessions: [{ status: 'completed', decision: 'go', bant_total: 24 }],
    });
    expect(gate.ok).toBe(false);
    expect(gate.messages[0]).toContain('task Lead');
  });

  it('blocks when no completed intake', () => {
    const gate = validatePresalesConsultAdvance({
      leadTaskDone: true,
      sessions: [{ status: 'draft', decision: '', bant_total: 0 }],
    });
    expect(gate.ok).toBe(false);
    expect(gate.messages[0]).toContain('Lead Intake');
  });

  it('requires confirm on nurture decision', () => {
    const gate = validatePresalesConsultAdvance({
      leadTaskDone: true,
      sessions: [{ status: 'completed', decision: 'nurture', bant_total: 20 }],
    });
    expect(gate.ok).toBe(true);
    expect(gate.requires_confirm).toBe(true);
  });

  it('allows go with strong BANT', () => {
    const gate = validatePresalesConsultAdvance({
      leadTaskDone: true,
      sessions: [{ status: 'completed', decision: 'go', bant_total: 26 }],
    });
    expect(gate.ok).toBe(true);
    expect(gate.requires_confirm).toBe(false);
  });
});
