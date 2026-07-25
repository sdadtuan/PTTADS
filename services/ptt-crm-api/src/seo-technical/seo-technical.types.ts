export interface SeoTechnicalIssueRow {
  id: number;
  customer_id: number;
  page_id: number | null;
  url: string;
  issue_type: string;
  severity: string;
  status: string;
  description: string;
  impact_notes: string;
  assignee_id: number | null;
  discovered_at: string | null;
  resolved_at: string | null;
  crm_task_id: number | null;
  lifecycle_id: number | null;
}

export interface SeoSeverityMatrix {
  critical: number;
  high: number;
  medium: number;
  low: number;
}

export interface SeoCwvSnapshotRow {
  id: number;
  customer_id: number;
  url: string;
  lcp_ms: number | null;
  cls: number | null;
  inp_ms: number | null;
  performance_score: number | null;
  cwv_rating: string;
  source: string;
  checked_at: string | null;
}

export interface SeoCwvSummary {
  pass_rate_pct: number;
  avg_lcp_ms: number | null;
  avg_cls: number | null;
  avg_performance_score: number | null;
  snapshot_count: number;
}

export interface SeoCwvCaptureResult {
  customer_id: number;
  captured: number;
  snapshots: Array<{ snapshot_id: number; url: string; cwv_rating: string }>;
  errors: string[];
  skipped?: boolean;
  reason?: string;
}
