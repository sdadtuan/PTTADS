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

  it('blocks handover→retain without finance confirm when outstanding', () => {
    expect(() =>
      validateStageAdvance({
        fromStage: 'handover',
        toStage: 'retain',
        currentStageComplete: true,
        paymentGate: {
          ok: false,
          messages: ['Còn công nợ HĐ'],
        },
      }),
    ).toThrow(/công nợ/i);
  });

  it('advance info shows block reason for TMMT', () => {
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

  it('advance info shows payment gate on handover', () => {
    const info = getStageAdvanceInfo({
      currentStage: 'handover',
      currentStageComplete: true,
      currentDone: 2,
      currentTotal: 2,
      paymentGate: {
        ok: false,
        requires_confirm: true,
        outstanding_vnd: 5_000_000,
        messages: ['Còn công nợ'],
      },
    });
    expect(info.can_advance_forward).toBe(false);
    expect(info.payment_gate?.requires_confirm).toBe(true);
  });

  it('blocks deliver→handover without launch qa confirm', () => {
    expect(() =>
      validateStageAdvance({
        fromStage: 'deliver',
        toStage: 'handover',
        currentStageComplete: true,
        launchQaGate: { ok: false, messages: ['Launch QA chưa launch_ready'] },
      }),
    ).toThrow(/Launch QA/i);
  });

  it('advance info shows launch qa gate on deliver', () => {
    const info = getStageAdvanceInfo({
      currentStage: 'deliver',
      currentStageComplete: true,
      currentDone: 2,
      currentTotal: 2,
      launchQaGate: {
        ok: false,
        warn_only: true,
        launch_ready: false,
        progress_percent: 50,
        progress_completed: 3,
        progress_total: 6,
        requires_confirm: true,
        status: 'in_progress',
        messages: ['Launch QA chưa launch_ready'],
      },
    });
    expect(info.can_advance_forward).toBe(false);
    expect(info.launch_qa_gate?.requires_confirm).toBe(true);
  });
});
