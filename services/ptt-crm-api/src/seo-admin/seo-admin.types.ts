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

export interface SeoGscTrendPoint {
  date: string;
  clicks: number;
  impressions: number;
}

export interface SeoCriticalIssueRow {
  id: number;
  customer_id: number;
  url: string;
  issue_type: string;
  severity: string;
  status: string;
  customer_name: string;
}

export interface SeoHubResponse {
  ok: boolean;
  summary: SeoHubSummaryBlock;
  clients: SeoHubClientRow[];
  alerts: SeoHubAlert[];
  executive: {
    gsc_totals: Record<string, unknown>;
    gsc_trend: SeoGscTrendPoint[];
    content_delivery: Record<string, number>;
    critical_issues: SeoCriticalIssueRow[];
    filters: { customer_id?: number | null; days: number; market?: string | null };
  };
}

export interface SeoClientsListResponse {
  ok: boolean;
  clients: SeoHubClientRow[];
  total: number;
}

export interface SeoClientSettings {
  customer_id: number;
  domains: string[];
  markets: string[];
  languages: string[];
  industry: string;
  brand_guidelines: Record<string, unknown>;
  seo_guidelines: Record<string, unknown>;
  aeo_guidelines: Record<string, unknown>;
  contract_tier: string;
  notes: string;
  integrations: Record<string, unknown>;
  updated_at: string | null;
}

export interface SeoIntegrationPublicStatus {
  connected: boolean;
  site_url?: string;
  property_id?: string;
  status: string;
  connected_at?: string | null;
  last_sync_at?: string | null;
  last_sync_status?: string | null;
}

export interface SeoSyncRunRow {
  id: number;
  customer_id: number;
  source: string;
  status: string;
  started_at: string | null;
  finished_at: string | null;
  rows_imported: number;
  error_message: string;
}

export interface SeoClientWorkspaceResponse {
  ok: boolean;
  client: SeoHubClientRow;
  settings: SeoClientSettings;
  integrations: {
    gsc: SeoIntegrationPublicStatus;
    ga4: SeoIntegrationPublicStatus;
  };
  sync_runs: SeoSyncRunRow[];
  gsc_totals: Record<string, unknown>;
  content_delivery: Record<string, number>;
}

export interface SeoClientTaskServiceRow {
  kind: 'service';
  task_id: number;
  lifecycle_id: number;
  service_slug: string;
  stage: string;
  title: string;
  due_on: string;
  url: string;
}

export interface SeoClientTaskTechnicalRow {
  kind: 'technical';
  issue_id: number;
  crm_task_id: number | null;
  lifecycle_id: number | null;
  title: string;
  severity: string;
  status: string;
  url: string;
}

export interface SeoClientTasksResponse {
  ok: boolean;
  customer_id: number;
  service_tasks: SeoClientTaskServiceRow[];
  technical_issues: SeoClientTaskTechnicalRow[];
  open_count: number;
}

export interface SeoSettingsUpdateBody {
  domains?: string[];
  markets?: string[];
  languages?: string[];
  industry?: string;
  brand_guidelines?: Record<string, unknown>;
  seo_guidelines?: Record<string, unknown>;
  aeo_guidelines?: Record<string, unknown>;
  contract_tier?: string;
  notes?: string;
  integrations?: Record<string, unknown>;
}

export interface SeoSyncTriggerResponse {
  ok: boolean;
  source: string;
  customer_id: number;
  mode: 'queue' | 'none';
  job_id?: string | null;
  sync_run_id?: number | null;
  error?: string;
}

export interface SeoOAuthStartResponse {
  ok: boolean;
  authorization_url: string;
  provider: 'gsc' | 'ga4';
  customer_id: number;
  configured: boolean;
}
