export const SEO_REPORTS_SCHEMA = 'seo_aeo';

export const DASHBOARD_TYPES = ['executive', 'seo', 'content', 'technical', 'aeo', 'ops'] as const;

export const REPORT_CADENCES = ['weekly', 'monthly'] as const;

export type DashboardType = (typeof DASHBOARD_TYPES)[number];
