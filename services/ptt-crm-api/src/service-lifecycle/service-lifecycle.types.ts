export interface ServiceLifecycleRow {
  id: number;
  lead_id: number | null;
  customer_id: number | null;
  contract_id: number | null;
  service_slug: string;
  stage: string;
  status: string;
  assigned_am: number | null;
  assigned_sp: number | null;
  stage_entered_at: string;
  notes: string;
  marketing_plan_id: number | null;
  created_at: string;
  updated_at: string;
}

export interface ServiceLifecycleEventRow {
  id: number;
  lifecycle_id: number;
  from_stage: string | null;
  to_stage: string;
  actor_id: number | null;
  actor_type: string;
  notes: string;
  created_at: string;
}

export interface CreateServiceLifecycleBody {
  lead_id?: number | null;
  customer_id?: number | null;
  service_slug: string;
}

export interface PatchServiceLifecycleBody {
  stage?: string;
  service_slug?: string;
  notes?: string;
  assigned_am?: number | null;
  assigned_sp?: number | null;
}

export const VALID_STAGES = [
  'lead',
  'consult',
  'proposal',
  'onboard',
  'deliver',
  'handover',
  'retain',
] as const;

export const VALID_STATUSES = ['draft', 'active', 'closed', 'lost'] as const;

export const VALID_SLUGS = new Set([
  'dich-vu-aeo',
  'dich-vu-seo-tong-the',
  'dich-vu-seo-local',
  'dich-vu-seo-audit',
  'dich-vu-quan-tri-website',
  'thiet-ke-website',
  'thiet-ke-website-tron-goi',
  'thiet-ke-landing-page',
  'quang-cao-facebook',
  'quang-cao-google',
  'thue-tai-khoan-quang-cao',
  'tiep-thi-noi-dung',
]);

export function stageIndex(stage: string): number {
  const idx = (VALID_STAGES as readonly string[]).indexOf(String(stage ?? '').trim());
  return idx >= 0 ? idx : 0;
}

export function isValidStage(stage: string): boolean {
  return (VALID_STAGES as readonly string[]).includes(String(stage ?? '').trim());
}

export function isValidSlug(slug: string): boolean {
  return VALID_SLUGS.has(String(slug ?? '').trim());
}
