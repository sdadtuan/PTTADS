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
