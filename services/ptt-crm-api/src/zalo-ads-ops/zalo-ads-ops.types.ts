export interface ZaloAdsOpsLaunchBody {
  client_id: string;
  external_account_id: string;
  campaign_name?: string;
  daily_budget_vnd: number;
  objective?: string;
  creative_submission_id?: string;
  preflight_ack?: boolean;
  submitted_by?: string;
}

export interface ZaloAdsOpsStatusBody {
  client_id: string;
  external_campaign_id: string;
  status: 'ACTIVE' | 'PAUSED' | 'STOPPED' | 'ARCHIVED';
  submitted_by?: string;
}

export interface ZaloAdsOpsSubmitResponse {
  ok: boolean;
  request_id: string;
  workflow_id: string | null;
  change_type: string;
  pilot: {
    allowed: boolean;
    stub_mode: boolean;
    pilot_mode: boolean;
    warning?: string | null;
    reason?: string | null;
  };
}
