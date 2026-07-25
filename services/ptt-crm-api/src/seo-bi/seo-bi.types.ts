export interface SeoBiDashboardResponse {
  type: 'bi';
  customer_id: number | null;
  days: number;
  gsc_series: Array<{ stat_date: string; clicks: number; impressions: number }>;
  totals: { clicks: number; impressions: number };
  clickhouse_configured: boolean;
}

export interface SeoBiFactRow {
  customer_id: number;
  fact_date: string;
  metric_name: string;
  metric_value: number;
  dimensions: string;
}

export interface SeoBiParityResponse {
  ok: boolean;
  days: number;
  fact_date: string;
  metrics: string[];
  sample_facts: SeoBiFactRow[];
  totals_by_metric: Record<string, number>;
}

export interface SeoBiStatusResponse {
  ok: boolean;
  clickhouse_configured: boolean;
  bi_export_enabled: boolean;
  cwv_stub: boolean;
  serp_provider: string;
  grafana_dashboard: string;
  gate_d_flags: Record<string, boolean | string | number>;
  gate_e_flags: Record<string, boolean | string | number>;
}

export interface SeoAttributionSummary {
  customer_id: number;
  days: number;
  sessions: number;
  users: number;
  conversions: number;
  revenue: number;
  landing_pages: number;
  revenue_per_session: number;
  conversion_rate: number;
}

export interface SeoAttributionLandingPage {
  landing_page: string;
  sessions: number;
  revenue: number;
  conversions: number;
  revenue_per_session: number;
}

export interface SeoClickhouseExportResult {
  ok: boolean;
  job_id?: string;
  mode: string;
  error?: string;
}
