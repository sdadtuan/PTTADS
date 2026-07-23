import lifecycleStepsData from './lifecycle-workflow-steps.data.json';

export type WorkflowStep = {
  title: string;
  description: string;
  ai_prompt_key?: string;
  form_fields?: Array<{ key: string; label: string; type: string }>;
};

export type LifecycleStageKey = 'onboard' | 'deliver' | 'handover' | 'retain';

const DATA = lifecycleStepsData as Record<string, Partial<Record<LifecycleStageKey, WorkflowStep[]>>>;

export const POST_ONBOARD_STAGES: LifecycleStageKey[] = ['onboard', 'deliver', 'handover', 'retain'];

export const RECURRING_DELIVER_SLUGS = new Set([
  'dich-vu-aeo',
  'dich-vu-seo-tong-the',
  'dich-vu-seo-local',
  'dich-vu-quan-tri-website',
  'quang-cao-facebook',
  'quang-cao-google',
  'tiep-thi-noi-dung',
]);

export const SERVICE_LABELS: Record<string, string> = {
  'dich-vu-aeo': 'Dịch vụ AEO',
  'dich-vu-seo-tong-the': 'SEO Tổng thể',
  'dich-vu-seo-local': 'SEO Local',
  'dich-vu-seo-audit': 'SEO Audit',
  'dich-vu-quan-tri-website': 'Quản trị Website',
  'thiet-ke-website': 'Thiết kế Website',
  'thiet-ke-website-tron-goi': 'Website Trọn gói',
  'thiet-ke-landing-page': 'Landing Page',
  'quang-cao-facebook': 'Quảng cáo Facebook',
  'quang-cao-google': 'Quảng cáo Google',
  'thue-tai-khoan-quang-cao': 'Thuê Tài khoản Ads',
  'tiep-thi-noi-dung': 'Tiếp thị Nội dung',
};

export function lifecycleStepsForService(serviceSlug: string): Partial<Record<LifecycleStageKey, WorkflowStep[]>> {
  return DATA[serviceSlug] ?? {};
}

export function inferBillingType(serviceSlug: string): 'recurring' | 'one_off' {
  return RECURRING_DELIVER_SLUGS.has(serviceSlug) ? 'recurring' : 'one_off';
}
