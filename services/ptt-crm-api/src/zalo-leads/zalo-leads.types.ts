export interface ZaloLeadRow {
  id: string;
  full_name: string | null;
  phone: string | null;
  email: string | null;
  status: string | null;
  channel: string | null;
  external_lead_id: string | null;
  form_id: string | null;
  oa_id: string | null;
  is_duplicate: boolean;
  created_at: string | null;
}

export interface ZaloLeadsListResponse {
  ok: boolean;
  leads: ZaloLeadRow[];
  total: number;
  filters?: {
    client_id?: string | null;
    form_id?: string | null;
    q?: string | null;
  };
}

export interface ZaloFormSyncRow {
  client_id: string;
  client_code: string | null;
  client_name: string | null;
  oa_id: string;
  form_id: string;
  channel_account_id: string;
  last_form_data_id: string | null;
  last_polled_at: string | null;
  last_status: string | null;
  last_error: string | null;
  has_token: boolean;
}

export interface ZaloFormsListResponse {
  ok: boolean;
  forms: ZaloFormSyncRow[];
}

export interface ZaloLeadEventRow {
  id: string;
  lead_id: string | null;
  client_id: string | null;
  event_type: string;
  payload_json: Record<string, unknown>;
  created_at: string | null;
}

export interface ZaloLeadEventsResponse {
  ok: boolean;
  lead_id: string;
  events: ZaloLeadEventRow[];
}

export interface ZaloFormPollResponse {
  ok: boolean;
  jobs_enqueued: Array<{ id: string; job_type: string; status: string; created?: boolean }>;
}
