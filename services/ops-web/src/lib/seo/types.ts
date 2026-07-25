export type {
  SeoHubAlert,
  SeoHubClientRow,
  SeoHubResponse,
} from '@/lib/api';

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
  client: import('@/lib/api').SeoHubClientRow;
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
  contract_tier?: string;
  notes?: string;
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

export type SeoClientTab = 'overview' | 'tasks' | 'settings';
