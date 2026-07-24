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
