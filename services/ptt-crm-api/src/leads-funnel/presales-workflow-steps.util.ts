export interface PresalesWorkflowStep {
  title: string;
  description: string;
  ai_prompt_key?: string;
  form_fields?: Array<{ key: string; label: string; type: string }>;
}

const GENERIC_STEPS: Record<string, PresalesWorkflowStep[]> = {
  lead: [
    {
      title: 'Qualify lead & xác nhận nhu cầu',
      description: 'Gọi/chát KH, xác nhận ngân sách và timeline.',
      form_fields: [{ key: 'need_summary', label: 'Tóm tắt nhu cầu', type: 'text' }],
    },
  ],
  consult: [
    {
      title: 'Brief tư vấn & Intake',
      description: 'Hoàn thành intake Go và brief consult.',
      form_fields: [{ key: 'consult_notes', label: 'Ghi chú tư vấn', type: 'text' }],
    },
  ],
  proposal: [
    {
      title: 'Báo giá & KH MKT sơ bộ',
      description: 'Hoàn thành proposal và KH MKT sơ bộ.',
      form_fields: [{ key: 'proposal_notes', label: 'Ghi chú báo giá', type: 'text' }],
    },
  ],
};

export function workflowStepsForService(serviceSlug: string): Record<string, PresalesWorkflowStep[]> {
  void serviceSlug;
  return GENERIC_STEPS;
}
