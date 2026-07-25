export interface SeoCmsTargetRow {
  customer_id: number;
  cms_type: string;
  base_url: string;
  auth: Record<string, unknown>;
  active: boolean;
  updated_at: string | null;
}

export interface SeoCmsPublishJobRow {
  id: number;
  customer_id: number;
  content_id: number;
  cms_type: string;
  status: string;
  remote_url: string;
  payload: Record<string, unknown>;
  response: Record<string, unknown>;
  error_message: string;
  created_at: string | null;
  finished_at: string | null;
}

export interface SeoCmsPublishResult {
  job_id: number;
  status: string;
  remote_url?: string;
  response?: Record<string, unknown>;
  message?: string;
  payload?: Record<string, unknown>;
  dry_run?: boolean;
}
