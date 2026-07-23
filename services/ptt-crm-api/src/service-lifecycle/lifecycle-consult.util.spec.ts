import { buildConsultBrief, consultGateLevel, prefillConsultTaskForm } from './lifecycle-consult.util';

describe('lifecycle-consult.util', () => {
  it('consultGateLevel blocks no_go', () => {
    expect(consultGateLevel('no_go', 26)).toBe('block');
  });

  it('consultGateLevel ok for go with high BANT', () => {
    expect(consultGateLevel('go', 26)).toBe('ok');
  });

  it('buildConsultBrief without intake suggests intake action', () => {
    const brief = buildConsultBrief({
      lifecycleId: 1,
      serviceSlug: 'dich-vu-seo-tong-the',
      leadId: 10,
      leadTaskDone: false,
      leadTask: { task_id: 1, form_data: { need: 'Cần SEO' }, notes: '', is_done: false },
      intakeSessions: [],
    });
    expect(brief.service_label).toBe('SEO Tổng thể');
    expect((brief.recommended_actions as string[])[0]).toContain('Lead Intake');
  });

  it('prefillConsultTaskForm fills from lead need', () => {
    const out = prefillConsultTaskForm({
      serviceSlug: 'dich-vu-seo-tong-the',
      consultTask: {
        id: 2,
        lifecycle_id: 1,
        stage: 'consult',
        step_index: 0,
        title: 'Consult',
        description: '',
        form_fields: [],
        form_data: {},
        ai_prompt_key: '',
        ai_output: '',
        is_done: false,
        done_at: '',
        done_by: null,
        notes: '',
        is_custom: false,
        created_at: '',
        updated_at: '',
      },
      leadTask: {
        id: 1,
        lifecycle_id: 1,
        stage: 'lead',
        step_index: 0,
        title: 'Lead',
        description: '',
        form_fields: [],
        form_data: { need: 'Traffic tụt', domain: 'example.com' },
        ai_prompt_key: '',
        ai_output: '',
        is_done: false,
        done_at: '',
        done_by: null,
        notes: '',
        is_custom: false,
        created_at: '',
        updated_at: '',
      },
      latestIntake: null,
      overwrite: false,
    });
    expect(out.filled).toContain('current_status');
    expect(String(out.form_data.current_status)).toContain('Traffic');
  });
});
