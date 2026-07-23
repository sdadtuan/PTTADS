import { getStageAdvanceInfo, StageAdvanceError, validateStageAdvance } from './lifecycle-stage.util';

describe('lifecycle-stage.util', () => {
  it('allows backward move without task check', () => {
    expect(() =>
      validateStageAdvance({
        fromStage: 'deliver',
        toStage: 'onboard',
        currentStageComplete: false,
      }),
    ).not.toThrow();
  });

  it('blocks skip forward', () => {
    expect(() =>
      validateStageAdvance({
        fromStage: 'lead',
        toStage: 'proposal',
        currentStageComplete: true,
      }),
    ).toThrow(StageAdvanceError);
  });

  it('blocks forward when tasks incomplete', () => {
    expect(() =>
      validateStageAdvance({
        fromStage: 'onboard',
        toStage: 'deliver',
        currentStageComplete: false,
        tmmtGate: { ok: true, messages: [] },
      }),
    ).toThrow(/Hoàn thành tất cả task/);
  });

  it('blocks onboard→deliver when TMMT invalid', () => {
    expect(() =>
      validateStageAdvance({
        fromStage: 'onboard',
        toStage: 'deliver',
        currentStageComplete: true,
        tmmtGate: { ok: false, messages: ['TMMT chưa đủ'] },
      }),
    ).toThrow('TMMT chưa đủ');
  });

  it('advance info shows block reason', () => {
    const info = getStageAdvanceInfo({
      currentStage: 'onboard',
      currentStageComplete: true,
      currentDone: 3,
      currentTotal: 3,
      tmmtGate: { ok: false, messages: ['Điền TMMT'] },
    });
    expect(info.can_advance_forward).toBe(false);
    expect(info.block_reason).toContain('TMMT');
  });
});
