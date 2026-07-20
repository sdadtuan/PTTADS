export interface IntakeSessionRow {
  id: number;
  lead_id: number | null;
  lifecycle_id: number | null;
  service_slug: string;
  mode: string;
  status: string;
  am_id: number | null;
  contact_name: string;
  contact_role: string;
  company_name: string;
  source: string;
  bant_json: Record<string, unknown>;
  bant_total: number;
  lead_temperature: string;
  decision: string;
  decision_reason: string;
  answers_json: Record<string, unknown>;
  stakeholders_json: Array<Record<string, string>>;
  commitments_json: Array<Record<string, string>>;
  next_meeting_at: string;
  next_meeting_note: string;
  proposal_date: string;
  ai_summary: string;
  ai_suggested_questions: string[];
  started_at: string;
  completed_at: string;
  created_at: string;
  updated_at: string;
}

export interface CreateIntakeSessionBody {
  lifecycle_id?: number;
  lead_id?: number;
  service_slug?: string;
  mode?: string;
  am_id?: number;
  contact_name?: string;
  contact_role?: string;
  company_name?: string;
  source?: string;
}

export interface PatchIntakeSessionBody {
  mode?: string;
  contact_name?: string;
  contact_role?: string;
  company_name?: string;
  source?: string;
  lead_temperature?: string;
  decision?: string;
  decision_reason?: string;
  next_meeting_at?: string;
  next_meeting_note?: string;
  proposal_date?: string;
  status?: string;
  bant_json?: Record<string, unknown>;
  answers_json?: Record<string, unknown>;
  stakeholders_json?: Array<Record<string, string>>;
  commitments_json?: Array<Record<string, string>>;
}

export const VALID_MODES = new Set(['phone', 'in_person']);
export const VALID_DECISIONS = new Set(['go', 'nurture', 'no_go', '']);
export const VALID_TEMPERATURES = new Set(['hot', 'warm', 'cold', '']);
export const VALID_STATUS = new Set(['draft', 'completed']);

export const STAKEHOLDER_ROLES: Array<[string, string]> = [
  ['decision_maker', 'Decision Maker'],
  ['influencer', 'Influencer'],
  ['gatekeeper', 'Gatekeeper'],
  ['user', 'User'],
];

export interface IntakeStatsResult {
  total_lifecycles: number;
  lifecycles_with_completed_intake: number;
  completed_intake_sessions: number;
  intake_coverage_pct: number;
  avg_bant_total: number;
  lifecycle_table_exists: boolean;
  am_id?: number;
  by_am?: Array<{
    staff_id: number;
    name: string;
    lifecycle_count: number;
    intake_completed: number;
    avg_bant: number;
  }>;
}

export interface IntakeEntryResult {
  ok: boolean;
  lead_id?: number;
  lifecycle_id?: number | null;
  service_slug?: string;
  is_common_form?: boolean;
  redirect_url?: string;
  error?: string;
}
