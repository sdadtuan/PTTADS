export type AttributionModel = 'last_touch_crm';

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
  attribution_model: AttributionModel;
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

export interface TestPixelResponse {
  ok: boolean;
  stub?: boolean;
  pixel_id?: string;
  events_received?: number;
  fbtrace_id?: string | null;
  error?: string;
  graph_response?: Record<string, unknown>;
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

export interface ConversionRuleMutationResponse {
  ok: boolean;
  rule: ConversionRuleRow;
}

export interface CapiRetryResponse {
  ok: boolean;
  log_id: string;
  status: string;
  job?: {
    id: string;
    job_type: string;
    status: string;
    created: boolean;
  } | null;
  skipped?: boolean;
  reason?: string;
}

export interface CapiFlushResponse {
  ok: boolean;
  processed: number;
  enqueued: number;
  skipped: number;
  jobs: Array<{
    log_id: string;
    job_id?: string;
    skipped?: boolean;
    reason?: string;
  }>;
}
