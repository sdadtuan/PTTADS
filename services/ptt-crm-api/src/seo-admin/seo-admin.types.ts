export const SEO_AEO_SERVICE_SLUGS = [
  'dich-vu-aeo',
  'dich-vu-seo-tong-the',
  'dich-vu-seo-local',
  'dich-vu-seo-audit',
] as const;

export interface SeoHubClientRow {
  customer_id: number;
  customer_name: string;
  customer_company: string;
  settings_ok: boolean;
  domains: string[];
  markets: string[];
  contract_tier: string;
  active_projects: number;
  active_initiatives: number;
  aeo_queries: number;
  aeo_visible: number;
  aeo_coverage_pct: number;
  critical_issues: number;
  content_overdue: number;
  health_score: number;
  health_tier: 'good' | 'warn' | 'bad';
}

export interface SeoHubAlert {
  severity: 'warn' | 'danger';
  message: string;
  link: string;
  link_label: string;
}

export interface SeoHubSummaryBlock {
  seo_clients: number;
  active_lifecycles: number;
  aeo_queries_total: number;
  aeo_visible_total: number;
  aeo_coverage_pct: number;
  settings_missing: number;
  active_initiatives: number;
  critical_issues: number;
  open_alerts: number;
  failed_sync_runs: number;
  organic_growth_pct: number;
  publish_sla_pct: number;
}

export interface SeoHubResponse {
  ok: boolean;
  summary: SeoHubSummaryBlock;
  clients: SeoHubClientRow[];
  alerts: SeoHubAlert[];
  executive: {
    gsc_totals: Record<string, unknown>;
    content_delivery: Record<string, number>;
    filters: { customer_id?: number | null; days: number; market?: string | null };
  };
}

export interface SeoClientsListResponse {
  ok: boolean;
  clients: SeoHubClientRow[];
  total: number;
}
