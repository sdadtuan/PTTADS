export interface PortalEmailDashboard {
  ok: boolean;
  email_enabled: boolean;
  client_id: string;
  pending_approvals: number;
  campaigns_sent_28d: number;
  open_rate_pct: number;
  revenue_attrib: number;
  recent_campaigns: PortalEmailCampaignRow[];
}

export interface PortalEmailCampaignRow {
  id: string;
  name: string;
  status: string;
  audience_count: number | null;
  scheduled_at: string | null;
  sent_at: string | null;
  updated_at: string;
}

export interface PortalEmailApprovalRow {
  campaign_id: string;
  name: string;
  audience_count: number | null;
  template_name: string;
  requested_at: string;
  status: string;
}

export interface PortalEmailApprovalPreview {
  ok: boolean;
  campaign_id: string;
  name: string;
  subject_template: string;
  html_body: string;
  audience_count: number | null;
  scheduled_at: string | null;
  template_name: string;
  status: string;
}

export interface PortalEmailCampaignStats {
  ok: boolean;
  campaign_id: string;
  campaign_name: string;
  status: string;
  audience_count: number | null;
  sent: number;
  delivered: number;
  opens: number;
  clicks: number;
  unsubscribes: number;
  complaints: number;
  open_rate_pct: number;
  click_rate_pct: number;
  revenue_attrib: number;
}

export interface PortalEmailReportsSummary {
  ok: boolean;
  client_id: string;
  days: number;
  sent: number;
  opens: number;
  clicks: number;
  open_rate_pct: number;
  revenue_attrib: number;
}

export interface PortalEmailApprovalDecision {
  note?: string;
}
