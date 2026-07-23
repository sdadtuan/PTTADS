export interface AgencyClientRow {
  id: string;
  code: string;
  name: string;
  industry_slug: string | null;
  status: string;
  owner_am_id: string | null;
  notes: string | null;
  created_at: string | null;
  updated_at: string | null;
  channels?: string | null;
}

export interface AgencyClientsListResponse {
  clients: AgencyClientRow[];
}

export interface CreateClientBody {
  code: string;
  name: string;
  industry_slug?: string;
  owner_am_id?: string;
  notes?: string;
}

export interface AgencyClientDetail extends AgencyClientRow {
  channel_accounts?: AgencyChannelAccount[];
  progress?: Record<string, unknown>;
  side_effects?: AgencySideEffectsSummary;
}

export interface AgencySideEffectsSummary {
  domain_event_id?: string | null;
  jobs_enqueued?: Array<{ id: string; job_type: string; status: string; created: boolean }>;
  workflow_signal?: string;
}

export interface AgencyChannelAccount {
  id: string;
  channel: string;
  external_account_id: string | null;
  display_name: string | null;
  status: string | null;
  has_token?: boolean;
  token_status?: string | null;
  token_expires_at?: string | null;
  credential_ref?: string | null;
  pixel_id?: string | null;
  facebook_page_id?: string | null;
}

export interface AgencyStatsResponse {
  pg_ready: boolean;
  clients: Record<string, number>;
  jobs: Record<string, number>;
}

export interface HubCampaignMapRow {
  map_id: string;
  hub_campaign_id: number | null;
  channel: string;
  external_campaign_id: string | null;
  external_campaign_name: string | null;
  external_account_id: string | null;
  target_cpl_vnd: number | null;
  active: boolean;
  updated_at: string | null;
  hub_url: string;
}

export interface HubCampaignMapsResponse {
  ok: boolean;
  client_id: string;
  maps: HubCampaignMapRow[];
  count: number;
}

export interface HubCampaignGlobalRow extends HubCampaignMapRow {
  map_id: string;
  client_id: string;
  client_code: string | null;
  client_name: string | null;
}

export interface OnboardingItemRow {
  id: string;
  item_key: string;
  label: string;
  sort_order: number;
  completed: boolean;
  completed_at: string | null;
  completed_by: string | null;
  note: string | null;
}

export interface OnboardingProgress {
  total: number;
  completed: number;
  percent: number;
}

export interface OnboardingResponse {
  items: OnboardingItemRow[];
  progress: OnboardingProgress;
  side_effects?: AgencySideEffectsSummary;
}

export interface OnboardingWorkflowSnapshot {
  workflow_id: string;
  status: string;
  run_id: string | null;
  found: boolean;
  temporal_enabled: boolean;
}

export interface OnboardingLifecycleLink {
  lifecycle_id: number;
  stage: string;
  status: string;
  service_slug: string;
  contract_id: number;
  contract_title: string;
  service_delivery_url: string;
}

export interface OnboardingSummaryResponse extends OnboardingResponse {
  client_id: string;
  client_status: string;
  client_code: string;
  client_name: string;
  workflow: OnboardingWorkflowSnapshot;
  strict_onboarding: boolean;
  activation_ready: boolean;
  linked_lifecycles: OnboardingLifecycleLink[];
}

export interface KpiDefinitionRow {
  code: string;
  name: string;
  formula: string;
  granularity: string | null;
  description: string | null;
}

export interface UpdateClientBody {
  name?: string;
  industry_slug?: string;
  owner_am_id?: string;
  notes?: string;
  status?: string;
}

export interface AddChannelAccountBody {
  channel: string;
  external_account_id: string;
  display_name?: string;
  /** Meta Page ID for webhook → client resolution (digits only stored). */
  facebook_page_id?: string;
}

export interface UpdateChannelAccountBody {
  display_name?: string;
  external_account_id?: string;
  status?: string;
  facebook_page_id?: string;
}

export interface SetChannelTokenBody {
  access_token?: string;
  credential_ref?: string;
  token_expires_at?: string;
  revoke?: boolean;
}

export interface CreateKpiDefinitionBody {
  code: string;
  name: string;
  formula: string;
  granularity?: string;
  description?: string;
}

export interface UpdateKpiDefinitionBody {
  name?: string;
  formula?: string;
  granularity?: string;
  description?: string;
}

export interface ClientLeadRow {
  id: string;
  full_name: string | null;
  phone: string | null;
  email: string | null;
  status: string | null;
  channel: string | null;
  created_at: string | null;
}

export interface PatchHubCampaignMapBody {
  client_id: string;
  hub_campaign_id: number;
  external_campaign_id: string;
}

export interface CreateHubCampaignMapBody {
  client_id: string;
  channel?: string;
  external_campaign_id: string;
  external_campaign_name?: string;
  external_account_id?: string;
  target_cpl_vnd?: number;
  hub_campaign_id?: number;
}

export interface UpdateHubCampaignMapBody {
  external_campaign_id?: string;
  external_campaign_name?: string;
  external_account_id?: string;
  target_cpl_vnd?: number | null;
  active?: boolean;
}

export interface JobRow {
  id: string;
  job_type: string;
  status: string;
  idempotency_key: string | null;
  correlation_id: string | null;
  attempts: number;
  max_attempts: number;
  last_error: string | null;
  scheduled_at: string | null;
  finished_at: string | null;
  created_at: string | null;
  client_id: string | null;
  client_code: string | null;
  channel: string | null;
}

export interface JobsListResponse {
  stats: Record<string, number>;
  jobs: JobRow[];
}

export interface NotificationRow {
  id: string;
  category: string;
  title: string;
  body: string | null;
  link_url: string | null;
  client_id: string | null;
  read: boolean;
  created_at: string | null;
}

export interface NotificationsListResponse {
  notifications: NotificationRow[];
  unread: number;
}

export interface FacebookHubClientRow {
  id: string;
  code: string | null;
  name: string | null;
  status: string | null;
  owner_am_id: string | null;
  meta_account_count: number;
  spend: number;
  leads_crm: number;
  cpl: number | null;
  campaigns: number;
  unmapped_campaigns: number;
  over_target_rows: number;
  meta_has_token: boolean;
  token_status: string;
}

export interface FacebookHubAlert {
  severity: 'warn' | 'danger';
  message: string;
  link: string;
  link_label: string;
}

export interface FacebookHubResponse {
  ok: boolean;
  pg_ready: boolean;
  date_from: string;
  date_to: string;
  window_days: number;
  summary: Record<string, unknown>;
  clients: FacebookHubClientRow[];
  alerts: FacebookHubAlert[];
  filters?: {
    client_id?: string | null;
    status?: string | null;
    q?: string | null;
  };
}
