export interface SeoAlertRow {
  id: number;
  customer_id: number | null;
  alert_type: string;
  severity: string;
  message: string;
  link: string;
  status: string;
  created_at: string | null;
  resolved_at: string | null;
}

export interface SeoReportScheduleRow {
  id: number;
  customer_id: number;
  dashboard_type: string;
  cadence: string;
  day_of_week: number;
  day_of_month: number;
  recipient_emails: string[];
  cc_emails: string[];
  bcc_emails: string[];
  active: boolean;
  next_run_at: string | null;
  last_run_at: string | null;
  created_at: string | null;
}

export interface SeoDashboardResponse {
  type: string;
  customer_id: number | null;
  days?: number;
  gsc?: Record<string, unknown>;
  gsc_trend?: Array<{ stat_date: string; clicks: number; impressions: number }>;
  content_by_status?: Record<string, number>;
  content_chart?: Array<{ label: string; value: number }>;
  severity?: Record<string, number>;
  severity_chart?: Array<{ label: string; value: number }>;
  issues?: Array<Record<string, unknown>>;
  critical_issues?: number;
  aeo?: Record<string, unknown>;
  sync_runs?: Array<Record<string, unknown>>;
  sync_runs_recent?: Array<Record<string, unknown>>;
  open_alerts?: number;
}
