export type CreativeStatus = 'pending_client' | 'approved' | 'rejected' | 'withdrawn';

export interface CreativeRow {
  id: string;
  client_id: string;
  title: string;
  description: string | null;
  external_campaign_id: string | null;
  external_campaign_name: string | null;
  version: number;
  asset_url: string | null;
  asset_type: string;
  status: CreativeStatus;
  submitted_by: string | null;
  submitted_at: string;
  reviewed_by: string | null;
  reviewed_at: string | null;
  review_note: string | null;
  temporal_workflow_id: string | null;
}

export interface CreativePendingResponse {
  ok: boolean;
  client_id: string;
  count: number;
  rows: CreativeRow[];
}

export interface CreativeDecisionResponse {
  ok: boolean;
  creative: CreativeRow;
  event_id: string | null;
  temporal_signal: 'sent' | 'stub' | 'skipped';
  launch_qa_sync?: {
    synced: boolean;
    run_id?: string;
    launch_ready?: boolean;
    reason?: string;
  } | null;
}

export interface CreateCreativeBody {
  client_id: string;
  title: string;
  description?: string;
  external_campaign_id?: string;
  external_campaign_name?: string;
  version?: number;
  asset_url?: string;
  asset_type?: string;
  submitted_by?: string;
}

export interface CreateCreativeResponse {
  ok: boolean;
  creative: CreativeRow;
  workflow_id: string;
  workflow_started: boolean;
  temporal_run_id: string | null;
}

export interface RejectCreativeBody {
  note?: string;
}
