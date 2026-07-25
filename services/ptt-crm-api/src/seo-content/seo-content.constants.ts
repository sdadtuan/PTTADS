export const SEO_CONTENT_SCHEMA = 'seo_aeo';

export const CONTENT_WORKFLOW_STATUSES = [
  'idea',
  'researching',
  'brief_ready',
  'in_writing',
  'seo_review',
  'aeo_review',
  'technical_review',
  'client_review',
  'approved',
  'published',
  'monitoring',
  'refresh_required',
  'archived',
] as const;

export type ContentWorkflowStatus = (typeof CONTENT_WORKFLOW_STATUSES)[number];

export const PIPELINE_COLUMNS: ReadonlyArray<{ key: string; statuses: readonly string[]; label: string }> = [
  { key: 'idea', statuses: ['idea', 'researching'], label: 'Ý tưởng / Research' },
  { key: 'brief_ready', statuses: ['brief_ready'], label: 'Brief sẵn sàng' },
  { key: 'in_writing', statuses: ['in_writing'], label: 'Đang viết' },
  { key: 'seo_review', statuses: ['seo_review'], label: 'SEO Review' },
  { key: 'aeo_review', statuses: ['aeo_review'], label: 'AEO Review' },
  { key: 'technical_review', statuses: ['technical_review'], label: 'Technical Review' },
  { key: 'client_review', statuses: ['client_review'], label: 'Client Review' },
  { key: 'approved', statuses: ['approved'], label: 'Đã duyệt' },
  { key: 'published', statuses: ['published', 'monitoring'], label: 'Published / Monitoring' },
  { key: 'refresh', statuses: ['refresh_required'], label: 'Cần refresh' },
];

export const CONTENT_TRANSITIONS: Record<string, readonly string[]> = {
  idea: ['researching', 'brief_ready', 'archived'],
  researching: ['brief_ready', 'idea', 'archived'],
  brief_ready: ['in_writing', 'researching', 'archived'],
  in_writing: ['seo_review', 'brief_ready', 'archived'],
  seo_review: ['aeo_review', 'in_writing', 'archived'],
  aeo_review: ['approved', 'technical_review', 'in_writing', 'archived'],
  technical_review: ['client_review', 'approved', 'in_writing', 'archived'],
  client_review: ['approved', 'in_writing', 'archived'],
  approved: ['published', 'in_writing', 'archived'],
  published: ['monitoring', 'refresh_required', 'archived'],
  monitoring: ['refresh_required', 'archived'],
  refresh_required: ['in_writing', 'researching', 'archived'],
  archived: ['idea'],
};

export const APPROVAL_STAGES = ['seo_review', 'aeo_review', 'technical_review', 'client_review'] as const;

export const APPROVE_NEXT_STATUS: Record<string, string> = {
  seo_review: 'aeo_review',
  aeo_review: 'approved',
  technical_review: 'client_review',
  client_review: 'approved',
};

export function canTransition(current: string, target: string): boolean {
  return (CONTENT_TRANSITIONS[current] ?? []).includes(target);
}

export function opportunityScore(
  volume: number | null | undefined,
  difficulty: number | null | undefined,
  businessValue: string,
): number {
  const vol = Math.max(0, Number(volume ?? 0));
  const diff = Number(difficulty ?? 50);
  const bvMap: Record<string, number> = { low: 0.2, medium: 0.5, high: 0.8 };
  const bv = bvMap[String(businessValue || 'medium')] ?? 0.5;
  const volNorm = Math.min(vol / 5000, 1);
  const diffInv = Math.max(0, 1 - diff / 100);
  return Math.round((volNorm * 0.4 + diffInv * 0.35 + bv * 0.25) * 1000) / 10;
}
