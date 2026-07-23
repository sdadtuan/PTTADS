import workflowData from './presales-workflow-steps.data.json';

export interface PresalesWorkflowStep {
  title: string;
  description: string;
  ai_prompt_key?: string;
  form_fields?: Array<{ key: string; label: string; type: string }>;
}

type WorkflowData = Record<string, Record<string, PresalesWorkflowStep[]>>;

const SERVICE_STEPS = workflowData as WorkflowData;

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
  const slug = String(serviceSlug || '').trim();
  const steps = SERVICE_STEPS[slug];
  if (!steps) return GENERIC_STEPS;
  return {
    lead: steps.lead?.length ? steps.lead : GENERIC_STEPS.lead,
    consult: steps.consult?.length ? steps.consult : GENERIC_STEPS.consult,
    proposal: steps.proposal?.length ? steps.proposal : GENERIC_STEPS.proposal,
  };
}

export function listPresalesServiceSlugs(): string[] {
  return Object.keys(SERVICE_STEPS).sort();
}
