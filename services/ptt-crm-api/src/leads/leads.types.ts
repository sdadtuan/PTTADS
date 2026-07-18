export interface LeadV1 {
  id: number;
  full_name: string;
  phone: string;
  email: string;
  status: string;
  source: string;
  channel: string;
  client_id: string | null;
  campaign_id: string | null;
  external_lead_id: string | null;
  owner_id: number | null;
  created_at: string;
  received_at: string;
  is_duplicate: boolean;
}

export interface LeadsListResponseV1 {
  leads: LeadV1[];
  total: number;
  limit: number;
  offset: number;
}

export interface LeadRow {
  id: number;
  full_name: string | null;
  phone: string | null;
  email: string | null;
  status: string | null;
  source: string | null;
  owner_id: number | null;
  created_at: string | null;
  is_duplicate: number | null;
  meta_json: string | null;
}

export interface PgLeadRow {
  sqlite_lead_id: number | string;
  full_name: string | null;
  phone: string | null;
  email: string | null;
  status: string | null;
  source: string | null;
  owner_id: number | null;
  is_duplicate: boolean | null;
  agency_client_id: string | null;
  channel: string | null;
  external_lead_id: string | null;
  campaign_id: string | null;
  received_at: Date | string | null;
  created_at: Date | string | null;
}

export interface ListLeadsQuery {
  client_id?: string;
  status?: string;
  source?: string;
  channel?: string;
  q?: string;
  limit?: number;
  offset?: number;
}

export interface CreateLeadV1Body {
  full_name: string;
  phone?: string;
  email?: string;
  status?: string;
  source?: string;
  channel?: string;
  client_id?: string | null;
  campaign_id?: string | null;
  external_lead_id?: string | null;
  owner_id?: number | null;
}

export interface PatchLeadV1Body {
  owner_id?: number | null;
  status?: string;
  score?: number;
  assigned_by?: string;
}

export interface PatchLeadResult {
  lead: LeadV1;
  assigned: boolean;
  scored: boolean;
}
