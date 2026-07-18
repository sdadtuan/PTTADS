export type PerformanceGroupBy = 'day' | 'campaign';
export type PerformanceChannel = 'meta' | 'google';

export interface PerformanceQuery {
  client_id?: string;
  from?: string;
  to?: string;
  date_from?: string;
  date_to?: string;
  group_by?: string;
  channel?: string;
}

export interface PerformanceRow {
  performance_date?: string | null;
  channel?: string | null;
  external_campaign_id: string | null;
  external_campaign_name: string | null;
  spend: number;
  currency: string;
  impressions: number;
  clicks: number;
  leads_crm: number;
  leads_platform: number;
  cpl: number | null;
  target_cpl_vnd: number | null;
  cpl_delta_vnd: number | null;
  cpl_delta_pct: number | null;
  conversion_value: number;
  roas: number | null;
  roas_stub: boolean;
  hub_campaign_map_id: string | null;
  hub_campaign_id: number | null;
  hub_mapped: boolean;
  synced_at: string | null;
}

export interface PerformanceSummary {
  row_count: number;
  total_spend: number;
  total_leads_crm: number;
  avg_cpl: number | null;
  total_conversion_value: number;
  avg_roas: number | null;
  roas_stub: boolean;
  latest_performance_date: string | null;
  latest_synced_at: string | null;
  campaigns_tracked: number;
  mapped_rows: number;
  over_target_rows: number;
}

export interface PerformanceListResponse {
  ok: boolean;
  client_id: string;
  date_from: string;
  date_to: string;
  group_by: PerformanceGroupBy;
  channel?: PerformanceChannel | null;
  rows: PerformanceRow[];
  summary: PerformanceSummary;
  error?: string;
}
