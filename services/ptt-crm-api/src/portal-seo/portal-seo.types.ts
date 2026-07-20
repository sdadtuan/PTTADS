export interface PortalSeoSummary {
  ok?: boolean;
  seo_enabled: boolean;
  customer_id?: number;
  pending_client_review?: number;
  executive?: Record<string, unknown>;
  error?: string;
}

export interface PortalSeoContentRow {
  id: number;
  title: string;
  content_type: string;
  due_date?: string | null;
  updated_at?: string | null;
}

export interface PortalSeoContentDetail {
  id: number;
  title: string;
  content_type: string;
  workflow_status: string;
  body_html: string;
  brief: Record<string, unknown>;
  approvals: Array<Record<string, unknown>>;
}

export interface PortalSeoReviewBody {
  approved: boolean;
  notes?: string;
}

export type PortalSeoReportType = 'executive' | 'seo' | 'aeo' | 'technical' | 'content';

export interface PortalSeoExecutiveReport {
  ok: boolean;
  customer_id: number;
  dashboard_type: PortalSeoReportType;
  report: Record<string, unknown>;
  generated_at: string;
}

export interface PortalSeoWidgetMetric {
  label: string;
  value: unknown;
  unit?: string;
  sparkline?: number[];
}

export interface PortalSeoWidgets {
  ok: boolean;
  customer_id: number;
  widgets: Record<string, PortalSeoWidgetMetric>;
}
