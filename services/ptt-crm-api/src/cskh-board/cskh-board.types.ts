export interface CskhBoardQuery {
  owner_id?: number;
  status?: string;
  source?: string;
  channel?: string;
  q?: string;
  sla_filter?: 'all' | 'breach' | 'warning' | 'open';
  limit?: number;
  offset?: number;
}

export interface CskhBoardRow {
  id: number;
  full_name: string;
  phone: string;
  email: string;
  status: string;
  source: string;
  channel: string;
  owner_id: number | null;
  owner_name: string | null;
  received_at: string;
  created_at: string;
  first_call_at: string | null;
  sla_state: string;
  sla_minutes_elapsed: number | null;
  sla_deadline_at: string | null;
  next_follow_up_at: string | null;
}

export interface CskhBoardResponse {
  ok: boolean;
  items: CskhBoardRow[];
  total: number;
  limit: number;
  offset: number;
  summary: {
    total: number;
    breach: number;
    warning: number;
    ok: number;
  };
}

export interface CskhBulkAssignBody {
  lead_ids: number[];
  to_user_id: number;
  reason: string;
}

export interface CskhBulkRescheduleBody {
  lead_ids: number[];
  follow_up_at: string;
  note?: string;
}
