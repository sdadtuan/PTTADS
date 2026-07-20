export interface EmailHubSummary {
  workspaces: number;
  contacts: number;
  emails_sent: number;
  open_rate_pct: number;
  complaint_rate_pct: number;
  pending_approvals: number;
  send_queue_lag_minutes: number;
  revenue_attrib: number;
}

export interface EmailHubClientRow {
  client_id: string;
  client_code: string;
  client_name: string;
  workspace_name: string | null;
  primary_domain: string | null;
  domain_health: 'healthy' | 'at_risk' | 'unknown';
  complaint_rate_pct: number;
  last_send_at: string | null;
  pending_campaigns: number;
}

export interface EmailHubPendingApproval {
  campaign_id: string;
  client_id: string;
  client_name: string;
  campaign_name: string;
  scheduled_at: string | null;
  audience_count: number | null;
}

export interface EmailHubSendCalendarItem {
  campaign_id: string;
  client_name: string;
  campaign_name: string;
  scheduled_at: string;
  status: string;
}

export interface EmailHubAlert {
  severity: 'info' | 'warn' | 'danger';
  message: string;
  link: string;
  link_label: string;
}

export interface EmailHubResponse {
  ok: boolean;
  schema_ready: boolean;
  summary: EmailHubSummary;
  clients: EmailHubClientRow[];
  pending_approvals: EmailHubPendingApproval[];
  send_calendar: EmailHubSendCalendarItem[];
  alerts: EmailHubAlert[];
  filters: {
    client_id?: string | null;
    days: number;
    domain?: string | null;
  };
}

export interface EmailGovernanceRule {
  id: string;
  scope: string;
  client_id: string | null;
  rule_type: string;
  config_json: Record<string, unknown>;
  priority: number;
  enabled: boolean;
  created_at: string;
}

export interface EmailGovernanceAuditRow {
  id: number;
  client_id: string | null;
  actor: string;
  action: string;
  entity_type: string;
  entity_id: string | null;
  created_at: string;
}

export interface EmailGovernanceResponse {
  ok: boolean;
  read_only: boolean;
  schema_ready: boolean;
  rules: EmailGovernanceRule[];
  audit_log: EmailGovernanceAuditRow[];
  filters: {
    scope?: string | null;
  };
}

export interface EmailWorkspaceRow {
  id: string;
  client_id: string;
  client_code: string;
  client_name: string;
  name: string;
  default_from_name: string | null;
  default_from_email: string | null;
  default_reply_to: string | null;
  esp_provider: string;
  daily_send_cap: number;
  frequency_cap_7d: number;
  timezone: string;
  status: string;
  contact_count: number;
  subscriber_count: number;
  suppressed_count: number;
  created_at: string;
  updated_at: string;
}

export interface EmailClientListRow {
  client_id: string;
  client_code: string;
  client_name: string;
  client_status: string;
  workspace_id: string | null;
  workspace_name: string | null;
  esp_provider: string | null;
  contact_count: number;
  has_workspace: boolean;
}

export interface EmailContactRow {
  id: string;
  client_id: string;
  client_name: string;
  email: string;
  first_name: string | null;
  last_name: string | null;
  lifecycle_stage: string | null;
  consent_status: string | null;
  suppressed: boolean;
  created_at: string;
  updated_at: string;
}

export interface EmailConsentRow {
  id: string;
  client_id: string;
  contact_id: string;
  contact_email: string;
  topic: string;
  status: string;
  source: string;
  consent_version: string | null;
  recorded_at: string;
  recorded_by: string | null;
}

export interface EmailSuppressionRow {
  id: string;
  client_id: string | null;
  client_name: string | null;
  email_normalized: string;
  reason: string;
  scope: string;
  expires_at: string | null;
  created_at: string;
  created_by: string | null;
}

export interface EmailListResponse<T> {
  ok: boolean;
  items: T[];
  total: number;
  limit: number;
  offset: number;
}

export interface EmailImportResult {
  ok: boolean;
  created: number;
  updated: number;
  skipped: number;
  errors: string[];
}

export interface EmailPreferencePublicView {
  ok: boolean;
  client_name: string;
  email: string;
  topics: Array<{ topic: string; status: string }>;
  token_purpose: string;
}

export interface EmailSegmentRow {
  id: string;
  client_id: string;
  client_name: string;
  name: string;
  segment_type: string;
  definition_json: Record<string, unknown>;
  member_count: number;
  last_computed_at: string | null;
  status: string;
  created_at: string;
  updated_at: string;
}

export interface EmailTemplateRow {
  id: string;
  client_id: string;
  client_name: string;
  name: string;
  subject_template: string;
  html_body: string;
  text_body: string | null;
  locale: string | null;
  version: number;
  status: string;
  created_at: string;
  updated_at: string;
}

export interface EmailCampaignRow {
  id: string;
  client_id: string;
  client_name: string;
  workspace_id: string;
  name: string;
  campaign_type: string;
  segment_id: string | null;
  segment_name: string | null;
  template_id: string;
  template_name: string;
  status: string;
  scheduled_at: string | null;
  sent_at: string | null;
  audience_count: number | null;
  created_by: string | null;
  created_at: string;
  updated_at: string;
}

export interface EmailPreflightItem {
  id: string;
  label: string;
  status: 'pass' | 'warn' | 'fail';
  message: string;
}

export interface EmailPreflightResponse {
  ok: boolean;
  passed: boolean;
  checks: EmailPreflightItem[];
}

export interface EmailSegmentComputeResult {
  ok: boolean;
  segment_id: string;
  member_count: number;
  excluded_suppression: number;
  excluded_consent: number;
}

export interface EmailJourneyStepRow {
  id: string;
  journey_id: string;
  step_key: string;
  step_type: string;
  config_json: Record<string, unknown>;
  sort_order: number;
  created_at: string;
}

export interface EmailJourneyRow {
  id: string;
  client_id: string;
  client_name: string;
  name: string;
  trigger_type: string;
  graph_json: Record<string, unknown>;
  entry_segment_id: string | null;
  entry_segment_name: string | null;
  status: string;
  enrolled_count: number;
  created_by: string | null;
  created_at: string;
  updated_at: string;
  steps?: EmailJourneyStepRow[];
}

export interface EmailDeliverabilityDomainRow {
  id: string;
  client_id: string;
  client_name: string;
  domain: string;
  spf_status: string;
  dkim_status: string;
  dmarc_status: string;
  last_checked_at: string | null;
  warm_up_stage: number;
  daily_volume_cap: number | null;
  status: string;
  created_at: string;
}

export interface EmailReportsSummary {
  ok: boolean;
  days: number;
  client_id: string | null;
  sent: number;
  delivered: number;
  opens: number;
  clicks: number;
  unsubscribes: number;
  open_rate_pct: number;
  click_rate_pct: number;
  revenue_attrib: number;
}

export interface EmailReportsCampaignStats {
  ok: boolean;
  campaign_id: string;
  campaign_name: string;
  client_id: string;
  client_name: string;
  status: string;
  audience_count: number | null;
  sent: number;
  delivered: number;
  opens: number;
  clicks: number;
  unsubscribes: number;
  complaints: number;
  bounces: number;
}

export interface EmailDeliverabilityReport {
  ok: boolean;
  days: number;
  client_id: string | null;
  domains: EmailDeliverabilityDomainRow[];
  bounce_rate_pct: number;
  complaint_rate_pct: number;
  paused_domains: number;
}

export interface EmailEngagementSeriesPoint {
  date: string;
  opens: number;
  clicks: number;
}

export interface EmailExperimentVariantRow {
  id: string;
  experiment_id: string;
  variant_key: string;
  label: string;
  config_json: Record<string, unknown>;
  split_pct: number;
  created_at: string;
}

export interface EmailExperimentObservationRow {
  id: string;
  experiment_id: string;
  variant_key: string;
  metric_name: string;
  metric_value: number;
  sample_size: number;
  observed_at: string;
  source: string;
}

export interface EmailExperimentDecisionRow {
  id: string;
  experiment_id: string;
  decision: string;
  rationale: string | null;
  decided_by: string | null;
  decided_at: string;
}

export interface EmailExperimentRow {
  id: string;
  client_id: string;
  client_name: string;
  campaign_id: string | null;
  campaign_name: string | null;
  name: string;
  experiment_type: string;
  hypothesis: string | null;
  status: string;
  winner_variant_key: string | null;
  config_json: Record<string, unknown>;
  started_at: string | null;
  ended_at: string | null;
  created_by: string | null;
  created_at: string;
  updated_at: string;
  variants?: EmailExperimentVariantRow[];
  observations?: EmailExperimentObservationRow[];
  decisions?: EmailExperimentDecisionRow[];
}

export interface EmailExperimentRollupResult {
  ok: boolean;
  experiment_id: string;
  variants: Array<{
    variant_key: string;
    sent: number;
    opens: number;
    clicks: number;
    open_rate: number;
    click_rate: number;
  }>;
  winner_metric: string;
  winner_variant_key: string | null;
  min_sample: number;
  job_id?: string | null;
}

export interface EmailReportScheduleRow {
  id: string;
  client_id: string;
  client_name: string;
  report_type: 'executive' | 'campaign' | 'deliverability' | string;
  cadence: 'weekly' | 'monthly' | string;
  day_of_week: number;
  day_of_month: number;
  recipient_emails: string[];
  cc_emails: string[];
  bcc_emails: string[];
  active: boolean;
  next_run_at: string | null;
  last_sent_at: string | null;
  created_at: string;
  updated_at: string;
}

export interface EmailClickhouseExportResult {
  ok: boolean;
  job_id: string | null;
  mode: string;
}
