export interface MetaAdsOpsPilotCheck {
  allowed: boolean;
  reason?: string | null;
  pilot_mode?: boolean;
}

export type MetaAdsOpsChangeType =
  | 'create_campaign'
  | 'create_adset'
  | 'create_ad'
  | 'update_ad_creative'
  | 'update_ad_copy';

export interface MetaAdsOpsTemplate {
  id: string;
  label: string;
  objective: string;
  optimization_goal: string;
  billing_event: string;
  default_daily_budget_vnd: number;
  description: string;
}

export interface MetaAdsOpsPreflightItem {
  key: string;
  label: string;
  passed: boolean;
  note: string;
}

export interface MetaAdsOpsPreflightResponse {
  ok: boolean;
  disabled?: boolean;
  client_id: string;
  ready: boolean;
  items: MetaAdsOpsPreflightItem[];
  pilot: MetaAdsOpsPilotCheck;
}

export interface MetaAdsOpsLaunchBody {
  client_id: string;
  external_account_id: string;
  template_id?: string;
  campaign_name: string;
  adset_name: string;
  ad_name: string;
  daily_budget_vnd: number;
  creative_submission_id: string;
  external_creative_id?: string;
  submitted_by?: string;
  preflight_ack?: boolean;
}

export interface MetaAdsOpsEditSnapshotResponse {
  ok: boolean;
  client_id: string;
  external_ad_id: string;
  effective_status: string;
  headline: string;
  primary_text: string;
  description: string;
  call_to_action: string;
  creative_submission_id: string | null;
  external_creative_id: string | null;
  stub?: boolean;
}

export interface MetaAdsOpsEditSubmitBody {
  client_id: string;
  external_ad_id: string;
  external_campaign_id?: string;
  action: 'update_ad_creative' | 'update_ad_copy';
  old_value: Record<string, unknown>;
  new_value: Record<string, unknown>;
  disapproved_ack?: boolean;
  submitted_by?: string;
}

export interface MetaAdsOpsSubmitResponse {
  ok: boolean;
  request_id?: string;
  workflow_id?: string | null;
  change_type?: string;
  pilot?: MetaAdsOpsPilotCheck;
  diff?: Record<string, unknown>;
}
