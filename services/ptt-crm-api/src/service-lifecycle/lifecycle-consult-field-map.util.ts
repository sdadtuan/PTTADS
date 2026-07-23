const DEFAULT_CRM_TO_CONSULT: Record<string, string> = {
  niche: 'target_audience',
  domain: 'current_status',
  goal: 'current_status',
  campaign_goal: 'product_usp',
};

const SLUG_CRM_TO_CONSULT: Record<string, Record<string, string>> = {
  'dich-vu-seo-tong-the': { domain: 'current_status', need: 'current_status' },
  'dich-vu-aeo': { domain: 'current_status', need: 'current_status' },
  'dich-vu-seo-local': { city: 'local_keywords', gbp_status: 'current_status', need: 'current_status' },
  'dich-vu-seo-audit': { domain: 'current_status', need: 'audit_scope' },
  'dich-vu-quan-tri-website': { domain: 'current_status', platform: 'current_status', need: 'pain_points' },
  'thiet-ke-website': { website_type: 'current_status', need: 'current_status' },
  'thiet-ke-website-tron-goi': { website_type: 'current_status', features: 'current_status', need: 'integrations' },
  'thiet-ke-landing-page': { lp_purpose: 'usp', campaign: 'target_audience', niche: 'target_audience' },
  'quang-cao-facebook': {
    niche: 'target_audience',
    campaign_goal: 'product_usp',
    has_ads_account: 'current_status',
    daily_budget: 'current_status',
  },
  'quang-cao-google': {
    niche: 'target_keywords',
    campaign_type: 'current_status',
    has_google_ads: 'current_status',
    monthly_budget: 'current_status',
  },
  'thue-tai-khoan-quang-cao': {
    platform: 'current_status',
    urgency: 'risk_assessment',
    niche: 'current_status',
    monthly_spend: 'current_status',
  },
  'tiep-thi-noi-dung': { channels: 'current_status', articles_per_month: 'current_status', need: 'current_status' },
};

export function getCrmFieldMap(serviceSlug: string): Record<string, string> {
  const key = String(serviceSlug ?? '').trim();
  return { ...DEFAULT_CRM_TO_CONSULT, ...(SLUG_CRM_TO_CONSULT[key] ?? {}) };
}

export const SEO_SLUGS = new Set([
  'dich-vu-seo-tong-the',
  'dich-vu-seo-local',
  'dich-vu-aeo',
  'dich-vu-seo-audit',
]);
