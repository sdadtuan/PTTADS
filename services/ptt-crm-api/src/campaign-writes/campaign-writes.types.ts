export type CampaignWriteStatus =
  | 'pending_approval'
  | 'approved'
  | 'rejected'
  | 'executed'
  | 'execution_failed'
  | 'withdrawn';

export type CampaignChangeType = 'daily_budget' | 'status' | 'name';

export interface SubmitCampaignWriteBody {
  client_id: string;
  channel?: string;
  external_account_id?: string;
  external_campaign_id: string;
  external_campaign_name?: string;
  change_type?: CampaignChangeType;
  old_value?: Record<string, unknown>;
  new_value: Record<string, unknown>;
  submitted_by?: string;
}

export interface ApproveCampaignWriteBody {
  approved_by?: string;
  note?: string;
}

export interface CampaignWriteRow {
  id: string;
  client_id: string;
  channel: string;
  external_account_id: string | null;
  external_campaign_id: string;
  external_campaign_name: string | null;
  change_type: CampaignChangeType;
  old_value: Record<string, unknown>;
  new_value: Record<string, unknown>;
  status: CampaignWriteStatus;
  submitted_by: string;
  approved_by: string | null;
  approved_at: string | null;
  executed_at: string | null;
  execution_error: string | null;
  temporal_workflow_id: string | null;
  created_at: string;
}
