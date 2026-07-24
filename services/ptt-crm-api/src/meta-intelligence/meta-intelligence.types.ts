export type MetaAnomalyAlertType = 'spend_spike' | 'cpl_spike' | 'roas_low';

export interface MetaAnomalyRow {
  id: string;
  client_id: string;
  client_code: string | null;
  client_name: string | null;
  external_campaign_id: string | null;
  alert_type: MetaAnomalyAlertType | string;
  severity: string;
  metric_value: number | null;
  threshold_value: number | null;
  spike_pct: number | null;
  message: string;
  performance_date: string | null;
  created_at: string;
}

export interface MetaAnomaliesListResponse {
  ok: boolean;
  disabled?: boolean;
  anomalies: MetaAnomalyRow[];
  count: number;
  attribution: import('../meta-attribution.util').MetaAttributionMeta;
}

export interface MetaRoasSeriesPoint {
  performance_date: string;
  spend: number;
  conversion_value: number;
  roas: number | null;
  roas_stub: boolean;
}

export interface MetaRoasSummary {
  total_spend: number;
  total_conversion_value: number;
  avg_roas: number | null;
  roas_stub: boolean;
}

export interface MetaRoasResponse {
  ok: boolean;
  disabled?: boolean;
  date_from: string;
  date_to: string;
  summary: MetaRoasSummary;
  series: MetaRoasSeriesPoint[];
  attribution: import('../meta-attribution.util').MetaAttributionMeta;
}

export interface MetaBudgetWriteRequestHint {
  change_type: 'daily_budget';
  external_campaign_id: string;
  daily_budget_vnd: number;
}

export interface MetaBudgetRecommendationRow {
  client_id: string;
  client_code: string | null;
  client_name: string | null;
  external_campaign_id: string | null;
  external_campaign_name: string | null;
  recommendation_type: 'decrease_budget' | 'increase_budget';
  current_daily_spend_vnd: number;
  suggested_daily_budget_vnd: number;
  change_pct: number;
  rationale: string;
  write_request: MetaBudgetWriteRequestHint;
}

export interface MetaBudgetRecommendationsResponse {
  ok: boolean;
  disabled?: boolean;
  read_only: boolean;
  date_from: string;
  date_to: string;
  recommendations: MetaBudgetRecommendationRow[];
  count: number;
  attribution: import('../meta-attribution.util').MetaAttributionMeta;
}

export type MetaInsightLevel = 'campaign' | 'adset' | 'ad';

export interface MetaDailyInsightRow {
  client_id: string;
  client_code: string | null;
  client_name: string | null;
  external_campaign_id: string | null;
  external_campaign_name: string | null;
  external_adset_id: string | null;
  external_adset_name: string | null;
  insight_level: MetaInsightLevel | string;
  performance_date: string;
  spend: number;
  impressions: number;
  clicks: number;
  leads_crm: number;
  conversion_value: number;
}

export interface MetaDailyInsightsResponse {
  ok: boolean;
  disabled?: boolean;
  reason?: string;
  hint?: string;
  enabled_level?: MetaInsightLevel | string;
  level: MetaInsightLevel | string;
  date_from: string;
  date_to: string;
  rows: MetaDailyInsightRow[];
  count: number;
  attribution: import('../meta-attribution.util').MetaAttributionMeta;
}
