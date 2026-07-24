/** Meta Enterprise hub types (ops-web). */

export type MetaBadgeVariant = 'ok' | 'warn' | 'error' | 'muted';

export type MetaHubTab = 'clients' | 'campaigns' | 'alerts';

export interface HubAttributionMeta {
  attribution_model: 'last_touch_crm';
  unmapped_spend_pct: number;
  spend_source: 'meta_api';
  data_freshness: {
    through_date: string;
    synced_at: string | null;
  };
}

export interface FacebookHubClient {
  id: string;
  code: string | null;
  name: string | null;
  status: string | null;
  spend: number;
  leads_crm: number;
  cpl: number | null;
  campaigns: number;
  unmapped_campaigns: number;
  over_target_rows: number;
  meta_has_token?: boolean;
  token_status?: string;
}

export interface FacebookHubAlert {
  severity: 'warn' | 'danger';
  message: string;
  link: string;
  link_label: string;
}

export interface FacebookHubResponse {
  ok: boolean;
  summary: Record<string, unknown>;
  clients: FacebookHubClient[];
  alerts: FacebookHubAlert[];
  date_from: string;
  date_to: string;
  window_days?: number;
  attribution?: HubAttributionMeta;
  filters?: {
    client_id?: string | null;
    status?: string | null;
    q?: string | null;
  };
}

export interface FacebookHubQuery {
  days?: number;
  date_to?: string;
  date_from?: string;
  status?: string;
  client_id?: string;
  q?: string;
}

export type FacebookHubExportScope = 'clients' | 'campaigns';

export interface MetaHubFilterState {
  days: number;
  dateTo: string;
  dateFrom: string;
  clientId: string;
  status: string;
  q: string;
  exportScope: FacebookHubExportScope;
}

export interface FacebookHubCampaignRow {
  client_id: string;
  client_code: string | null;
  client_name: string | null;
  external_campaign_id: string | null;
  external_campaign_name: string | null;
  spend: number;
  leads_crm: number;
  cpl: number | null;
  target_cpl_vnd: number | null;
  hub_mapped: boolean;
  cpl_delta_vnd: number | null;
  cpl_delta_pct: number | null;
  over_target: boolean;
}

export interface FacebookHubCampaignsResponse {
  ok: boolean;
  date_from: string;
  date_to: string;
  window_days: number;
  campaigns: FacebookHubCampaignRow[];
  count: number;
  attribution: HubAttributionMeta;
  filters?: FacebookHubResponse['filters'];
}

export interface MetaAlertRow {
  id: string;
  client_id: string;
  channel: string;
  external_campaign_id: string | null;
  alert_type: string;
  severity: string;
  metric_value: number | null;
  threshold_value: number | null;
  message: string;
  performance_date: string | null;
  dedupe_key: string;
  acknowledged_at: string | null;
  created_at: string;
  client_code?: string | null;
  client_name?: string | null;
}

export interface MetaAlertsListResponse {
  ok: boolean;
  alerts: MetaAlertRow[];
  count: number;
  open_count: number;
}

export interface MetaAlertAckResponse {
  ok: boolean;
  alert: MetaAlertRow;
}

export interface MetaSyncStatusGlobal {
  last_sync_at: string | null;
  last_success_at: string | null;
  last_error: string | null;
  accounts_total: number;
  accounts_failed: number;
  status: 'ok' | 'warn' | 'error';
}

export interface MetaSyncStatusClientRow {
  client_id: string;
  client_code: string | null;
  client_name: string | null;
  last_job_id: string | null;
  last_job_status: string | null;
  last_job_finished_at: string | null;
  last_job_error: string | null;
  token_status: string | null;
  sync_status: 'ok' | 'warn' | 'error';
}

export interface MetaSyncStatusResponse {
  ok: boolean;
  global: MetaSyncStatusGlobal;
  clients: MetaSyncStatusClientRow[];
  count: number;
}

export interface MetaHubMapSuggestBody {
  client_id?: string;
  date_from?: string;
  date_to?: string;
  dry_run?: boolean;
}

export interface MetaHubMapSuggestItem {
  client_id: string;
  external_campaign_id: string;
  external_campaign_name: string | null;
  hub_campaign_id: number;
  hub_campaign_code: string;
  hub_campaign_name: string;
  utm_campaign: string;
  match_score: number;
  spend_vnd: number;
  map_id?: string;
}

export interface MetaHubMapSuggestResponse {
  ok: boolean;
  date_from: string;
  date_to: string;
  suggestions: MetaHubMapSuggestItem[];
  inserted: MetaHubMapSuggestItem[];
  inserted_count: number;
  dry_run: boolean;
}

export interface TrackingHealthGlobal {
  sent: number;
  failed: number;
  skipped: number;
  pending: number;
  fail_rate_pct: number;
  match_hint_pct: number | null;
  avg_latency_ms: number | null;
}

export interface TrackingHealthAccountRow {
  client_id: string;
  channel_account_id: string;
  client_code: string | null;
  client_name: string | null;
  pixel_id: string | null;
  page_id: string | null;
  capi_enabled: boolean;
  last_sent_at: string | null;
  pixel_test_ok: boolean | null;
}

export interface TrackingHealthResponse {
  ok: boolean;
  disabled?: boolean;
  window_days: number;
  global: TrackingHealthGlobal;
  accounts: TrackingHealthAccountRow[];
  attribution_model: 'last_touch_crm';
}

export interface CapiEventRow {
  id: string;
  client_id: string;
  event_name: string;
  event_id: string;
  lead_id: number | null;
  pixel_id: string | null;
  status: string;
  error_message: string | null;
  created_at: string;
  sent_at: string | null;
  client_code?: string | null;
  client_name?: string | null;
}

export interface CapiEventsListResponse {
  ok: boolean;
  disabled?: boolean;
  events: CapiEventRow[];
  count: number;
}

export interface ConversionRuleRow {
  id: string;
  client_id: string | null;
  lead_status: string;
  event_name: string;
  enabled: boolean;
  require_meta_attribution: boolean;
  value_vnd: number;
  notes: string;
  created_at: string;
  updated_at: string;
}

export interface ConversionRulesListResponse {
  ok: boolean;
  disabled?: boolean;
  rules: ConversionRuleRow[];
  count: number;
}

export interface TestPixelResponse {
  ok: boolean;
  stub?: boolean;
  pixel_id?: string;
  events_received?: number;
  fbtrace_id?: string | null;
  error?: string;
  graph_response?: Record<string, unknown>;
}

export interface PreflightItem {
  key: string;
  label: string;
  passed: boolean;
  note?: string;
}

export interface CreateConversionRuleBody {
  client_id?: string | null;
  lead_status: string;
  event_name: string;
  enabled?: boolean;
  require_meta_attribution?: boolean;
  value_vnd?: number;
  notes?: string;
}

export interface PatchConversionRuleBody {
  enabled?: boolean;
  value_vnd?: number;
  require_meta_attribution?: boolean;
  notes?: string;
}

export interface CapiRetryResponse {
  ok: boolean;
  log_id: string;
  status: string;
  job?: { id: string; job_type: string; status: string; created: boolean } | null;
  skipped?: boolean;
  reason?: string;
}

export interface CapiFlushResponse {
  ok: boolean;
  processed: number;
  enqueued: number;
  skipped: number;
}

export interface MetaAnomalyRow {
  id: string;
  client_id: string;
  client_code?: string | null;
  client_name?: string | null;
  external_campaign_id: string | null;
  alert_type: string;
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
  attribution: HubAttributionMeta;
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
  attribution: HubAttributionMeta;
}

export interface MetaBudgetWriteRequestHint {
  change_type: 'daily_budget';
  external_campaign_id: string;
  daily_budget_vnd: number;
}

export interface MetaBudgetRecommendationRow {
  client_id: string;
  client_code?: string | null;
  client_name?: string | null;
  external_campaign_id: string | null;
  external_campaign_name?: string | null;
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
  attribution: HubAttributionMeta;
}

export interface MetaDailyInsightRow {
  client_id: string;
  client_code?: string | null;
  client_name?: string | null;
  external_campaign_id: string | null;
  external_campaign_name?: string | null;
  external_adset_id?: string | null;
  external_adset_name?: string | null;
  insight_level: string;
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
  enabled_level?: string;
  level: string;
  date_from: string;
  date_to: string;
  rows: MetaDailyInsightRow[];
  count: number;
  attribution: HubAttributionMeta;
}
