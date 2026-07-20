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
}

export interface AgencyChannelAccount {
  id: string;
  channel: string;
  external_account_id: string | null;
  display_name: string | null;
  status: string | null;
}

export interface AgencyStatsResponse {
  pg_ready: boolean;
  clients: Record<string, number>;
  jobs: Record<string, number>;
}

export interface HubCampaignMapRow {
  hub_campaign_id: number | null;
  channel: string;
  external_campaign_id: string | null;
  external_campaign_name: string | null;
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
  client_id: string;
  client_code: string | null;
  client_name: string | null;
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

export interface FacebookHubResponse {
  ok: boolean;
  pg_ready: boolean;
  date_from: string;
  date_to: string;
  window_days: number;
  summary: Record<string, unknown>;
  clients: FacebookHubClientRow[];
  alerts: string[];
}
