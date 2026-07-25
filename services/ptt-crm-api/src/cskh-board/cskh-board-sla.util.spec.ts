import {
  CSKH_FIRST_CALL_SLA_MINUTES,
  computeFirstCallSla,
  isNewLeadStatus,
} from './cskh-board-sla.util';

describe('cskh-board-sla.util', () => {
  const base = new Date('2026-07-26T10:00:00.000Z');

  it('isNewLeadStatus recognizes new/moi', () => {
    expect(isNewLeadStatus('new')).toBe(true);
    expect(isNewLeadStatus('moi')).toBe(true);
    expect(isNewLeadStatus('qualified')).toBe(false);
  });

  it('returns na for non-new status', () => {
    const out = computeFirstCallSla({
      status: 'qualified',
      receivedAt: base.toISOString(),
      createdAt: base.toISOString(),
      firstCallAt: null,
      now: new Date(base.getTime() + 20 * 60_000),
    });
    expect(out.sla_state).toBe('na');
  });

  it('breach when no call after 15 minutes', () => {
    const out = computeFirstCallSla({
      status: 'new',
      receivedAt: base.toISOString(),
      createdAt: base.toISOString(),
      firstCallAt: null,
      now: new Date(base.getTime() + CSKH_FIRST_CALL_SLA_MINUTES * 60_000 + 60_000),
    });
    expect(out.sla_state).toBe('breach');
  });

  it('ok when first call within 15 minutes', () => {
    const out = computeFirstCallSla({
      status: 'new',
      receivedAt: base.toISOString(),
      createdAt: base.toISOString(),
      firstCallAt: new Date(base.getTime() + 10 * 60_000).toISOString(),
      now: new Date(base.getTime() + 12 * 60_000),
    });
    expect(out.sla_state).toBe('ok');
  });

  it('breach when first call logged after deadline', () => {
    const out = computeFirstCallSla({
      status: 'new',
      receivedAt: base.toISOString(),
      createdAt: base.toISOString(),
      firstCallAt: new Date(base.getTime() + 20 * 60_000).toISOString(),
      now: new Date(base.getTime() + 21 * 60_000),
    });
    expect(out.sla_state).toBe('breach');
  });
});
