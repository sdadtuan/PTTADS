import type { StaffSectionCap, StoredStaffUser } from './auth';

export const API_BASE =
  (process.env.NEXT_PUBLIC_PTT_API_URL ?? 'http://127.0.0.1:3000').replace(/\/$/, '');

export interface StaffLoginResponse {
  access_token: string;
  refresh_token: string;
  token_type: string;
  expires_in: number;
  refresh_expires_in: number;
  user: StoredStaffUser;
}

export interface StaffMeResponse extends StoredStaffUser {
  caps: StaffSectionCap[];
}

export interface LeadRow {
  id: number;
  full_name: string;
  phone: string;
  email: string;
  status: string;
  source: string;
  channel: string;
  client_id: string | null;
  owner_id: number | null;
  created_at: string;
  received_at: string;
  is_duplicate: boolean;
}

export interface LeadsListResponse {
  leads: LeadRow[];
  total: number;
  limit: number;
  offset: number;
}

export class ApiError extends Error {
  constructor(
    message: string,
    readonly status: number,
  ) {
    super(message);
    this.name = 'ApiError';
  }
}

async function parseJson<T>(res: Response): Promise<T> {
  const text = await res.text();
  if (!text) {
    return {} as T;
  }
  try {
    return JSON.parse(text) as T;
  } catch {
    throw new ApiError('Invalid JSON response', res.status);
  }
}

function authHeaders(token: string): HeadersInit {
  return { Authorization: `Bearer ${token}` };
}

export async function staffLogin(email: string, password: string): Promise<StaffLoginResponse> {
  const res = await fetch(`${API_BASE}/api/v1/staff/auth/login`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ email, password }),
  });
  const body = await parseJson<StaffLoginResponse & { error?: string; message?: string }>(res);
  if (!res.ok) {
    throw new ApiError(body.error ?? body.message ?? 'Login failed', res.status);
  }
  return body;
}

export async function staffRefresh(refreshToken: string): Promise<StaffLoginResponse> {
  const res = await fetch(`${API_BASE}/api/v1/staff/auth/refresh`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ refresh_token: refreshToken }),
  });
  const body = await parseJson<StaffLoginResponse & { error?: string; message?: string }>(res);
  if (!res.ok) {
    throw new ApiError(body.error ?? body.message ?? 'Refresh failed', res.status);
  }
  return body;
}

export async function staffMe(token: string): Promise<StaffMeResponse> {
  const res = await fetch(`${API_BASE}/api/v1/staff/auth/me`, {
    headers: authHeaders(token),
    cache: 'no-store',
  });
  const body = await parseJson<StaffMeResponse & { error?: string }>(res);
  if (!res.ok) {
    throw new ApiError(body.error ?? 'Unauthorized', res.status);
  }
  return body;
}

export async function fetchLeads(
  token: string,
  params?: { q?: string; status?: string; limit?: number; offset?: number; hide_review_queue?: boolean },
): Promise<LeadsListResponse> {
  const qs = new URLSearchParams();
  if (params?.q) qs.set('q', params.q);
  if (params?.status) qs.set('status', params.status);
  if (params?.limit !== undefined) qs.set('limit', String(params.limit));
  if (params?.offset !== undefined) qs.set('offset', String(params.offset));
  if (params?.hide_review_queue === false) qs.set('hide_review_queue', '0');
  const suffix = qs.toString() ? `?${qs.toString()}` : '';
  const res = await fetch(`${API_BASE}/api/v1/leads${suffix}`, {
    headers: authHeaders(token),
    cache: 'no-store',
  });
  const body = await parseJson<LeadsListResponse & { error?: string; message?: string }>(res);
  if (!res.ok) {
    throw new ApiError(body.error ?? body.message ?? 'Leads fetch failed', res.status);
  }
  return body;
}

export async function fetchLead(token: string, id: number): Promise<LeadRow> {
  const res = await fetch(`${API_BASE}/api/v1/leads/${id}`, {
    headers: authHeaders(token),
    cache: 'no-store',
  });
  const body = await parseJson<LeadRow & { error?: string; message?: string }>(res);
  if (!res.ok) {
    throw new ApiError(body.error ?? body.message ?? 'Lead fetch failed', res.status);
  }
  return body;
}

export interface PatchLeadBody {
  owner_id?: number | null;
  status?: string;
  assigned_by?: string;
}

export async function patchLead(
  token: string,
  id: number,
  body: PatchLeadBody,
): Promise<LeadRow> {
  const res = await fetch(`${API_BASE}/api/v1/leads/${id}`, {
    method: 'PATCH',
    headers: {
      ...authHeaders(token),
      'Content-Type': 'application/json',
    },
    body: JSON.stringify(body),
  });
  const out = await parseJson<LeadRow & { error?: string; message?: string }>(res);
  if (!res.ok) {
    throw new ApiError(out.error ?? out.message ?? 'Lead update failed', res.status);
  }
  return out;
}

export interface LeadActivityRow {
  id: number;
  lead_id: number;
  user_id: number | null;
  user_name: string;
  activity_type: string;
  activity_type_label: string;
  content: string;
  result: string;
  next_action: string;
  next_action_at: string;
  created_at: string;
  created_by: string;
}

export interface LeadStatusLogRow {
  id: number;
  lead_id: number;
  old_status: string;
  new_status: string;
  changed_by: string;
  note: string;
  created_at: string;
}

export interface LeadAssignmentLogRow {
  id: number;
  lead_id: number;
  from_user_id: number | null;
  from_name: string;
  to_user_id: number | null;
  to_name: string;
  reason: string;
  created_by: string;
  created_at: string;
}

export interface LeadAuditBundle {
  status_logs: LeadStatusLogRow[];
  assignment_logs: LeadAssignmentLogRow[];
}

async function leadLegacyFetch<T>(token: string, path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(`${API_BASE}${path}`, {
    ...init,
    headers: {
      ...authHeaders(token),
      ...(init?.headers ?? {}),
    },
  });
  const body = await parseJson<T & { error?: string; message?: string }>(res);
  if (!res.ok) {
    throw new ApiError(body.error ?? body.message ?? 'Lead legacy request failed', res.status);
  }
  return body;
}

export async function fetchLeadActivities(
  token: string,
  leadId: number,
  limit = 50,
): Promise<LeadActivityRow[]> {
  const out = await leadLegacyFetch<{ activities: LeadActivityRow[] }>(
    token,
    `/api/crm/leads/${leadId}/activities?limit=${limit}`,
  );
  return out.activities ?? [];
}

export async function createLeadActivity(
  token: string,
  leadId: number,
  body: {
    activity_type?: string;
    content?: string;
    result?: string;
    next_action?: string;
    next_action_at?: string;
  },
): Promise<LeadActivityRow> {
  const out = await leadLegacyFetch<{ activity: LeadActivityRow }>(
    token,
    `/api/crm/leads/${leadId}/activities`,
    {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(body),
    },
  );
  return out.activity;
}

export async function fetchLeadAudit(token: string, leadId: number): Promise<LeadAuditBundle> {
  return leadLegacyFetch<LeadAuditBundle>(token, `/api/crm/leads/${leadId}/audit`);
}

export async function assignLead(
  token: string,
  leadId: number,
  body: { to_user_id: number; reason: string },
): Promise<LeadRow> {
  const out = await leadLegacyFetch<{ lead: LeadRow }>(token, `/api/crm/leads/${leadId}/assign`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
  });
  return out.lead;
}

// --- Wave B4: Lead funnel (care / review queue / presales) ---

export interface LeadFunnelSnapshot {
  lead_id: number;
  care_pipeline: {
    current_stage_key: string;
    current_stage_label: string;
    all_complete: boolean;
    stages: Array<{ key: string; label: string; hint: string; done: boolean; current: boolean }>;
  };
  presales_care_gate: { complete: boolean; message: string };
  review_queue: { active: boolean; message?: string; hours_waiting?: number | null };
  presales_on_lead_enabled: boolean;
  presales: {
    presales: { id: number; stage: string; service_slug: string; status: string };
    tasks: Record<string, Array<{ id: number; title: string; is_done: boolean }>>;
    advance: { can_advance_forward: boolean; block_reason: string; next_stage: string | null };
  } | null;
}

async function leadFunnelMutate<T>(token: string, path: string, init: RequestInit): Promise<T> {
  const res = await fetch(`${API_BASE}${path}`, {
    ...init,
    headers: { ...authHeaders(token), 'Content-Type': 'application/json', ...(init.headers ?? {}) },
  });
  const body = await parseJson<T & { error?: string; message?: string }>(res);
  if (!res.ok) throw new ApiError(body.error ?? body.message ?? 'Lead funnel API failed', res.status);
  return body;
}

export async function fetchLeadFunnel(token: string, leadId: number): Promise<LeadFunnelSnapshot> {
  return leadFunnelMutate(token, `/api/v1/leads/${leadId}/funnel`, { method: 'GET' });
}

export async function submitLeadCareReport(
  token: string,
  leadId: number,
  body: { stage?: string; content?: string; care_status?: string },
): Promise<{ ok: boolean; funnel: LeadFunnelSnapshot }> {
  return leadFunnelMutate(token, `/api/v1/leads/${leadId}/care-pipeline/report`, {
    method: 'POST',
    body: JSON.stringify({ stage: 'first_contact', care_status: 'da_lien_he_thanh_cong', ...body }),
  });
}

export async function completeLeadCareStage(
  token: string,
  leadId: number,
  note: string,
): Promise<{ ok: boolean; funnel: LeadFunnelSnapshot }> {
  return leadFunnelMutate(token, `/api/v1/leads/${leadId}/care-pipeline/complete`, {
    method: 'POST',
    body: JSON.stringify({ stage: 'first_contact', note }),
  });
}

export async function fetchReviewQueueCount(token: string): Promise<{ count: number }> {
  return leadFunnelMutate(token, '/api/v1/leads/review-queue/count', { method: 'GET' });
}

export async function fetchReviewQueueLeads(
  token: string,
  limit = 50,
): Promise<{ leads: Array<{ id: number; full_name: string; phone: string; review_queue: { message?: string } }> }> {
  return leadFunnelMutate(token, `/api/v1/leads/review-queue?limit=${limit}`, { method: 'GET' });
}

export async function releaseLeadReviewQueue(
  token: string,
  leadId: number,
  body: { mode: 'auto' | 'manual'; owner_id?: number; note?: string },
): Promise<{ ok: boolean }> {
  return leadFunnelMutate(token, `/api/v1/leads/${leadId}/review-queue/release`, {
    method: 'POST',
    body: JSON.stringify(body),
  });
}

export async function ensureLeadPresales(
  token: string,
  leadId: number,
  serviceSlug: string,
): Promise<{ ok: boolean; funnel: LeadFunnelSnapshot }> {
  return leadFunnelMutate(token, `/api/v1/leads/${leadId}/presales`, {
    method: 'POST',
    body: JSON.stringify({ service_slug: serviceSlug }),
  });
}

export async function fetchLeadPresalesConsultGate(
  token: string,
  leadId: number,
): Promise<{
  ok: boolean;
  gate: {
    ok: boolean;
    level: string;
    messages: string[];
    requires_confirm: boolean;
    requires_override: boolean;
    decision?: string;
    bant_total?: number;
  };
  presales_stage: string;
}> {
  return leadFunnelMutate(token, `/api/v1/leads/${leadId}/presales/consult-gate`, { method: 'GET' });
}

export async function advanceLeadPresales(
  token: string,
  leadId: number,
  body: { confirm?: boolean; override_reason?: string } = {},
): Promise<{ ok: boolean; funnel: LeadFunnelSnapshot }> {
  return leadFunnelMutate(token, `/api/v1/leads/${leadId}/presales/advance`, {
    method: 'POST',
    body: JSON.stringify(body),
  });
}

export async function fetchLeadPresalesMarketingPlan(
  token: string,
  leadId: number,
): Promise<{ ok: boolean; plan: Record<string, unknown>; validation: { ok: boolean; messages: string[] } }> {
  return leadFunnelMutate(token, `/api/v1/leads/${leadId}/presales/marketing-plan`, { method: 'GET' });
}

export async function patchLeadPresalesMarketingPlan(
  token: string,
  leadId: number,
  body: { name?: string; north_star?: string; objectives?: string; strategy_framework?: Record<string, string> },
): Promise<{ ok: boolean; funnel: LeadFunnelSnapshot; validation: { ok: boolean; messages: string[] } }> {
  return leadFunnelMutate(token, `/api/v1/leads/${leadId}/presales/marketing-plan`, {
    method: 'PATCH',
    body: JSON.stringify(body),
  });
}

export async function patchLeadPresalesTask(
  token: string,
  leadId: number,
  taskId: number,
  body: { is_done?: boolean },
): Promise<{ ok: boolean; funnel: LeadFunnelSnapshot }> {
  return leadFunnelMutate(token, `/api/v1/leads/${leadId}/presales/tasks/${taskId}`, {
    method: 'PATCH',
    body: JSON.stringify(body),
  });
}

// --- Wave B5 S0: Contract → lifecycle promote ---

export interface ContractReadinessCheck {
  key: string;
  ok: boolean;
  label: string;
  message?: string;
}

export interface LeadContractRow {
  id: number;
  lead_id: number | null;
  title: string;
  status: string;
  amount_vnd: number;
  service_slug: string;
  signed_on: string;
  notes: string;
}

export interface ContractApprovalRow {
  id: number;
  contract_id: number;
  lead_id: number;
  status: string;
  requested_by: string;
  decided_by: string;
  amount_vnd: number;
  notes: string;
  decision_notes: string;
  created_at: string;
  contract_title?: string;
  lead_name?: string;
}

export async function fetchLeadContractReadiness(token: string, leadId: number) {
  return leadFunnelMutate<{
    ok: boolean;
    checks: ContractReadinessCheck[];
    contract: LeadContractRow | null;
    approval: ContractApprovalRow | null;
    lifecycle_id?: number | null;
  }>(token, `/api/v1/leads/${leadId}/contract/readiness`, { method: 'GET' });
}

export async function fetchLeadContract(token: string, leadId: number) {
  return leadFunnelMutate<{ contract: LeadContractRow | null; approval: ContractApprovalRow | null }>(
    token,
    `/api/v1/leads/${leadId}/contract`,
    { method: 'GET' },
  );
}

export async function createLeadContract(
  token: string,
  leadId: number,
  body: { title?: string; amount_vnd?: number; notes?: string },
) {
  return leadFunnelMutate<LeadContractRow>(token, `/api/v1/leads/${leadId}/contract`, {
    method: 'POST',
    body: JSON.stringify(body),
  });
}

export async function patchLeadContract(
  token: string,
  leadId: number,
  contractId: number,
  body: { title?: string; amount_vnd?: number; notes?: string },
) {
  return leadFunnelMutate<LeadContractRow>(token, `/api/v1/leads/${leadId}/contract/${contractId}`, {
    method: 'PATCH',
    body: JSON.stringify(body),
  });
}

export async function submitLeadContract(
  token: string,
  leadId: number,
  contractId: number,
  body: { notes?: string },
) {
  return leadFunnelMutate<ContractApprovalRow>(
    token,
    `/api/v1/leads/${leadId}/contract/${contractId}/submit`,
    { method: 'POST', body: JSON.stringify(body) },
  );
}

export async function fetchPendingContractApprovals(token: string, limit = 50) {
  return leadFunnelMutate<{ approvals: ContractApprovalRow[] }>(
    token,
    `/api/v1/contracts/approvals/pending?limit=${limit}`,
    { method: 'GET' },
  );
}

export async function approveContractApproval(token: string, approvalId: number) {
  return leadFunnelMutate<{
    lifecycle_id: number;
    customer_id: number;
    contract: LeadContractRow;
  }>(token, `/api/v1/contracts/approvals/${approvalId}/approve`, { method: 'POST', body: '{}' });
}

export async function rejectContractApproval(
  token: string,
  approvalId: number,
  body: { decision_notes?: string },
) {
  return leadFunnelMutate<ContractApprovalRow>(token, `/api/v1/contracts/approvals/${approvalId}/reject`, {
    method: 'POST',
    body: JSON.stringify(body),
  });
}

export async function fetchAgencyClientContracts(token: string, clientId: string) {
  return leadFunnelMutate<{ contracts: LeadContractRow[] }>(
    token,
    `/api/v1/agency/clients/${encodeURIComponent(clientId)}/contracts`,
    { method: 'GET' },
  );
}

export async function patchLeadLegacy(
  token: string,
  id: number,
  body: PatchLeadBody & { audit_note?: string },
): Promise<LeadRow> {
  const out = await leadLegacyFetch<{ lead: LeadRow }>(token, `/api/crm/leads/${id}`, {
    method: 'PATCH',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
  });
  return out.lead;
}

export interface CustomerRow {
  id: number;
  name: string;
  phone: string;
  email: string;
  address: string;
  company: string;
  lead_source: string;
  lead_source_label?: string;
  profile_notes: string;
  created_at: string;
}

export interface CustomerDetailBundle {
  customer: CustomerRow & {
    lead_source_note?: string;
    date_of_birth?: string;
    gender?: string;
    occupation?: string;
    interests?: string;
  };
  relations: Array<{ id: number; relation_type_label: string; full_name: string; phone: string }>;
  purchases: Array<{ id: number; product_name: string; amount_vnd: number; status_label: string }>;
  issues: Array<{ id: number; title: string; status_label: string; priority_label: string }>;
  stats: {
    relations_total: number;
    purchases_total: number;
    issues_total: number;
    issues_open: number;
  };
}

export interface IntakeSessionRow {
  id: number;
  lead_id: number | null;
  lifecycle_id: number | null;
  service_slug: string;
  mode: string;
  status: string;
  contact_name: string;
  company_name: string;
  bant_total: number;
  decision: string;
  decision_reason: string;
  bant_json: Record<string, number>;
  answers_json: Record<string, unknown>;
  updated_at: string;
}

async function crmFetch<T>(token: string, path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(`${API_BASE}${path}`, {
    ...init,
    headers: {
      ...authHeaders(token),
      ...(init?.headers ?? {}),
    },
  });
  const body = await parseJson<T & { error?: string; message?: string }>(res);
  if (!res.ok) {
    throw new ApiError(body.error ?? body.message ?? 'CRM request failed', res.status);
  }
  return body;
}

export async function fetchCustomers(
  token: string,
  params?: { q?: string; limit?: number },
): Promise<CustomerRow[]> {
  const qs = new URLSearchParams();
  if (params?.q) qs.set('q', params.q);
  if (params?.limit !== undefined) qs.set('limit', String(params.limit));
  const suffix = qs.toString() ? `?${qs.toString()}` : '';
  const out = await crmFetch<{ customers: CustomerRow[] }>(token, `/api/crm/customers${suffix}`);
  return out.customers ?? [];
}

export async function fetchCustomerDetail(token: string, id: number): Promise<CustomerDetailBundle> {
  return crmFetch<CustomerDetailBundle>(token, `/api/crm/customers/${id}`);
}

export async function patchCustomer(
  token: string,
  id: number,
  body: Partial<CustomerRow>,
): Promise<CustomerRow> {
  return crmFetch<CustomerRow>(token, `/api/crm/customers/${id}`, {
    method: 'PATCH',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
  });
}

export async function fetchIntakeDefinitions(token: string): Promise<{
  slugs: string[];
  common_slug: string;
  bant_rows: Array<{ label: string; hint: string }>;
}> {
  return crmFetch(token, '/api/crm/intake/definitions');
}

export async function fetchIntakeSessions(
  token: string,
  params: { lead_id?: number; lifecycle_id?: number },
): Promise<IntakeSessionRow[]> {
  const qs = new URLSearchParams();
  if (params.lead_id) qs.set('lead_id', String(params.lead_id));
  if (params.lifecycle_id) qs.set('lifecycle_id', String(params.lifecycle_id));
  const out = await crmFetch<{ sessions: IntakeSessionRow[] }>(
    token,
    `/api/crm/intake/sessions?${qs.toString()}`,
  );
  return out.sessions ?? [];
}

export async function createIntakeSession(
  token: string,
  body: { lead_id?: number; lifecycle_id?: number; mode?: string; service_slug?: string },
): Promise<IntakeSessionRow> {
  return crmFetch<IntakeSessionRow>(token, '/api/crm/intake/sessions', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
  });
}

export async function patchIntakeSession(
  token: string,
  id: number,
  body: Record<string, unknown>,
): Promise<IntakeSessionRow> {
  return crmFetch<IntakeSessionRow>(token, `/api/crm/intake/sessions/${id}`, {
    method: 'PATCH',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
  });
}

export async function completeIntakeSession(token: string, id: number): Promise<IntakeSessionRow> {
  return crmFetch<IntakeSessionRow>(token, `/api/crm/intake/sessions/${id}/complete`, {
    method: 'POST',
  });
}

export async function fetchIntakeStats(
  token: string,
  params?: { am_id?: number; by_am?: boolean },
): Promise<Record<string, unknown>> {
  const qs = new URLSearchParams();
  if (params?.am_id != null) qs.set('am_id', String(params.am_id));
  if (params?.by_am) qs.set('by_am', '1');
  const suffix = qs.toString() ? `?${qs.toString()}` : '';
  return crmFetch(token, `/api/crm/intake/stats${suffix}`);
}

export async function reopenIntakeSession(token: string, id: number): Promise<IntakeSessionRow> {
  return crmFetch<IntakeSessionRow>(token, `/api/crm/intake/sessions/${id}/reopen`, {
    method: 'POST',
  });
}

export async function generateIntakeAiSummary(token: string, id: number): Promise<IntakeSessionRow> {
  return crmFetch<IntakeSessionRow>(token, `/api/crm/intake/sessions/${id}/ai-summary`, {
    method: 'POST',
  });
}

export async function createCustomerRelation(
  token: string,
  customerId: number,
  body: { relation_type?: string; full_name: string; phone?: string; email?: string; notes?: string },
): Promise<CustomerDetailBundle['relations'][number]> {
  return crmFetch(token, `/api/crm/customers/${customerId}/relations`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
  });
}

export async function createCustomerIssue(
  token: string,
  customerId: number,
  body: { title: string; issue_type?: string; priority?: string; description?: string },
): Promise<CustomerDetailBundle['issues'][number]> {
  return crmFetch(token, `/api/crm/customers/${customerId}/issues`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
  });
}

export interface CaseRow {
  id: number;
  customer_id: number;
  title: string;
  description: string;
  status: string;
  status_label: string;
  priority: string;
  priority_label: string;
  customer_name: string;
  customer_phone: string;
  assigned_to: string;
  created_at: string;
  updated_at: string;
}

export interface CaseDetail extends CaseRow {
  events: Array<{ id: number; kind: string; body: string; created_at: string }>;
  care_reports: Array<{
    id: number;
    summary: string;
    contact_type_label: string;
    care_status_label: string;
    created_at: string;
  }>;
}

export async function fetchCases(
  token: string,
  params?: { q?: string; staff_id?: number },
): Promise<CaseRow[]> {
  const qs = new URLSearchParams();
  if (params?.q) qs.set('q', params.q);
  if (params?.staff_id != null) qs.set('staff_id', String(params.staff_id));
  const suffix = qs.toString() ? `?${qs.toString()}` : '';
  const out = await crmFetch<{ cases: CaseRow[] }>(token, `/api/crm/cases${suffix}`);
  return out.cases ?? [];
}

export async function fetchCaseDetail(token: string, id: number): Promise<CaseDetail> {
  return crmFetch<CaseDetail>(token, `/api/crm/cases/${id}`);
}

export async function patchCase(
  token: string,
  id: number,
  body: Partial<{ title: string; status: string; priority: string; assigned_staff_id: number | null }>,
): Promise<CaseRow> {
  return crmFetch<CaseRow>(token, `/api/crm/cases/${id}`, {
    method: 'PATCH',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
  });
}

export async function addCaseEvent(
  token: string,
  caseId: number,
  body: { body: string },
): Promise<{ id: number; body: string; created_at: string }> {
  return crmFetch(token, `/api/crm/cases/${caseId}/events`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
  });
}

export async function addCaseCareReport(
  token: string,
  caseId: number,
  body: { summary: string; contact_type?: string; care_status?: string; next_action?: string },
): Promise<{ id: number; summary: string; created_at: string }> {
  return crmFetch(token, `/api/crm/cases/${caseId}/care-reports`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
  });
}

export interface MarketingPlanRow {
  id: number;
  code: string;
  name: string;
  status: string;
  status_label?: string;
  priority: string;
  fiscal_year: number;
  period_label: string;
  owner_name: string;
  linked_campaign_count?: number;
  milestone_total?: number;
  milestone_done?: number;
  updated_at: string;
}

export interface ServiceLifecycleRow {
  id: number;
  lead_id: number | null;
  customer_id: number | null;
  service_slug: string;
  stage: string;
  status: string;
  assigned_am: number | null;
  notes: string;
  updated_at: string;
}

export interface SopTemplateRow {
  id: number;
  code: string;
  name: string;
  channel: string;
  active: number;
}

export interface SopRunRow {
  id: number;
  name: string;
  status: string;
  template_id: number | null;
  template_name: string | null;
  start_date: string;
  updated_at: string;
}

export async function fetchMarketingPlans(
  token: string,
  params?: { fiscal_year?: number; status?: string; q?: string },
): Promise<MarketingPlanRow[]> {
  const qs = new URLSearchParams();
  if (params?.fiscal_year != null) qs.set('fiscal_year', String(params.fiscal_year));
  if (params?.status) qs.set('status', params.status);
  if (params?.q) qs.set('q', params.q);
  const suffix = qs.toString() ? `?${qs.toString()}` : '';
  const out = await crmFetch<{ plans: MarketingPlanRow[] }>(token, `/api/crm/marketing-plans${suffix}`);
  return out.plans ?? [];
}

export async function fetchMarketingPlanDetail(token: string, id: number): Promise<Record<string, unknown>> {
  return crmFetch(token, `/api/crm/marketing-plans/${id}`);
}

export async function createMarketingPlan(
  token: string,
  body: { name: string; fiscal_year?: number; status?: string },
): Promise<MarketingPlanRow> {
  return crmFetch<MarketingPlanRow>(token, '/api/crm/marketing-plans', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
  });
}

export async function patchMarketingPlan(
  token: string,
  id: number,
  body: Partial<{ name: string; status: string; priority: string; notes: string; objectives: string }>,
): Promise<MarketingPlanRow> {
  return crmFetch<MarketingPlanRow>(token, `/api/crm/marketing-plans/${id}`, {
    method: 'PATCH',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
  });
}

export async function fetchServiceLifecycles(
  token: string,
  params?: { service_slug?: string; include_draft?: boolean; am_id?: string },
): Promise<{ lifecycles: ServiceLifecycleRow[]; funnel_stats?: Record<string, number> }> {
  const qs = new URLSearchParams();
  if (params?.service_slug) qs.set('service_slug', params.service_slug);
  if (params?.include_draft) qs.set('include_draft', '1');
  if (params?.am_id) qs.set('am_id', params.am_id);
  const suffix = qs.toString() ? `?${qs.toString()}` : '';
  return crmFetch<{ lifecycles: ServiceLifecycleRow[]; funnel_stats?: Record<string, number> }>(
    token,
    `/api/crm/service-lifecycle${suffix}`,
  );
}

export async function fetchServiceLifecycleAdvanceInfo(
  token: string,
  id: number,
): Promise<Record<string, unknown>> {
  return crmFetch(token, `/api/crm/service-lifecycle/${id}/advance-info`);
}

export async function fetchServiceLifecycleTasks(
  token: string,
  id: number,
): Promise<{ tasks: Record<string, Array<Record<string, unknown>>> }> {
  return crmFetch(token, `/api/crm/service-lifecycle/${id}/tasks`);
}

export async function fetchServiceLifecycleProgress(
  token: string,
  id: number,
): Promise<{ progress: Record<string, { total: number; done: number; pct: number }> }> {
  return crmFetch(token, `/api/crm/service-lifecycle/${id}/progress`);
}

export async function patchServiceLifecycleTask(
  token: string,
  lifecycleId: number,
  taskId: number,
  body: Partial<{ is_done: boolean; notes: string; form_data: Record<string, unknown> }>,
): Promise<{ task: Record<string, unknown> }> {
  return crmFetch(token, `/api/crm/service-lifecycle/${lifecycleId}/tasks/${taskId}`, {
    method: 'PATCH',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
  });
}

export async function fetchServiceLifecycleMarketingPlan(
  token: string,
  id: number,
): Promise<{
  plan: Record<string, unknown> | null;
  validation: { ok: boolean; messages: string[] };
  tmmt_core_keys?: string[];
  tmmt_prof_keys?: string[];
  tmmt_min_filled?: number;
  filled_count?: number;
}> {
  return crmFetch(token, `/api/crm/service-lifecycle/${id}/marketing-plan`);
}

export async function fetchServiceLifecycleConsultBrief(
  token: string,
  id: number,
): Promise<Record<string, unknown>> {
  return crmFetch(token, `/api/crm/service-lifecycle/${id}/consult-brief`);
}

export async function postServiceLifecycleConsultPrefill(
  token: string,
  id: number,
  body: { overwrite?: boolean },
): Promise<{ task_id: number | null; filled: number; fields: string[]; skipped_existing: string[] }> {
  return crmFetch(token, `/api/crm/service-lifecycle/${id}/consult-prefill`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
  });
}

export async function patchServiceLifecycleMarketingPlan(
  token: string,
  id: number,
  body: Record<string, unknown>,
): Promise<{ plan: Record<string, unknown>; validation: { ok: boolean; messages: string[] } }> {
  return crmFetch(token, `/api/crm/service-lifecycle/${id}/marketing-plan`, {
    method: 'PATCH',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
  });
}

export async function fetchServiceLifecyclePresalesSummary(
  token: string,
  id: number,
): Promise<Record<string, unknown>> {
  return crmFetch(token, `/api/crm/service-lifecycle/${id}/presales-summary`);
}

export async function fetchServiceLifecycleFinanceSummary(
  token: string,
  id: number,
): Promise<Record<string, unknown>> {
  return crmFetch(token, `/api/crm/service-lifecycle/${id}/finance-summary`);
}

export async function fetchServiceLifecycleContext(
  token: string,
  id: number,
): Promise<Record<string, unknown>> {
  return crmFetch(token, `/api/crm/service-lifecycle/${id}/context`);
}

export async function createServiceLifecycleExpense(
  token: string,
  lifecycleId: number,
  body: { title?: string; category?: string; amount_vnd?: number; expense_on?: string; notes?: string },
): Promise<Record<string, unknown>> {
  return crmFetch(token, `/api/crm/service-lifecycle/${lifecycleId}/expenses`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
  });
}

export async function fetchServiceLifecycleDetail(token: string, id: number): Promise<Record<string, unknown>> {
  return crmFetch(token, `/api/crm/service-lifecycle/${id}`);
}

export async function patchServiceLifecycle(
  token: string,
  id: number,
  body: Partial<{ stage: string; notes: string; service_slug: string; assigned_am: number | null; assigned_sp: number | null }>,
): Promise<ServiceLifecycleRow> {
  return crmFetch<ServiceLifecycleRow>(token, `/api/crm/service-lifecycle/${id}`, {
    method: 'PATCH',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
  });
}

export async function fetchSopTemplates(token: string): Promise<SopTemplateRow[]> {
  const out = await crmFetch<{ templates: SopTemplateRow[] }>(token, '/api/crm/sop/templates');
  return out.templates ?? [];
}

export async function fetchSopRuns(token: string, status = 'active'): Promise<SopRunRow[]> {
  const out = await crmFetch<{ runs: SopRunRow[] }>(token, `/api/crm/sop/runs?status=${encodeURIComponent(status)}`);
  return out.runs ?? [];
}

export async function createSopRun(
  token: string,
  body: { name: string; template_id?: number; start_date?: string },
): Promise<SopRunRow> {
  return crmFetch<SopRunRow>(token, '/api/crm/sop/runs', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
  });
}

export interface SalesSummary {
  funnel?: Record<string, unknown>;
  active_plan?: Record<string, unknown> | null;
  counts?: Record<string, number>;
}

export interface SalesPlanRow {
  id: number;
  title: string;
  fiscal_year: number;
  status: string;
  revenue_target_vnd: number;
  updated_at: string;
}

export interface CrmStaffRow {
  id: number;
  name: string;
  internal_code: string;
  phone: string;
  email: string;
  job_title: string;
  department: string;
  active: number;
}

export interface KpiMetricRow {
  id: number;
  code: string;
  name: string;
  unit: string;
  active: number;
  sort_order: number;
}

export async function fetchSalesSummary(token: string): Promise<SalesSummary> {
  return crmFetch<SalesSummary>(token, '/api/crm/sales/summary');
}

export async function fetchSalesPlans(token: string): Promise<SalesPlanRow[]> {
  const out = await crmFetch<{ plans: SalesPlanRow[] }>(token, '/api/crm/sales/plans');
  return out.plans ?? [];
}

export async function createSalesPlan(
  token: string,
  body: { title: string; fiscal_year?: number },
): Promise<{ id: number }> {
  return crmFetch(token, '/api/crm/sales/plans', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
  });
}

export async function fetchSalesPipelineCases(
  token: string,
  stage?: string,
): Promise<Array<Record<string, unknown>>> {
  const qs = stage ? `?stage=${encodeURIComponent(stage)}` : '';
  const out = await crmFetch<{ cases: Array<Record<string, unknown>> }>(
    token,
    `/api/crm/sales/pipeline-cases${qs}`,
  );
  return out.cases ?? [];
}

export async function fetchSalesPartners(
  token: string,
  q?: string,
): Promise<Array<Record<string, unknown>>> {
  const qs = q ? `?q=${encodeURIComponent(q)}` : '';
  const out = await crmFetch<{ partners: Array<Record<string, unknown>> }>(
    token,
    `/api/crm/sales/partners${qs}`,
  );
  return out.partners ?? [];
}

export async function createSalesPartner(
  token: string,
  body: Record<string, unknown>,
): Promise<Record<string, unknown>> {
  return crmFetch(token, '/api/crm/sales/partners', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
  });
}

export async function fetchSalesTrainings(token: string): Promise<Array<Record<string, unknown>>> {
  const out = await crmFetch<{ trainings: Array<Record<string, unknown>> }>(token, '/api/crm/sales/trainings');
  return out.trainings ?? [];
}

export async function createSalesTraining(
  token: string,
  body: Record<string, unknown>,
): Promise<Record<string, unknown>> {
  return crmFetch(token, '/api/crm/sales/trainings', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
  });
}

export async function fetchSalesMarket(token: string): Promise<Array<Record<string, unknown>>> {
  const out = await crmFetch<{ research: Array<Record<string, unknown>> }>(token, '/api/crm/sales/market');
  return out.research ?? [];
}

export async function createSalesMarketEntry(
  token: string,
  body: Record<string, unknown>,
): Promise<Record<string, unknown>> {
  return crmFetch(token, '/api/crm/sales/market', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
  });
}

export async function fetchSalesTransactions(token: string): Promise<Array<Record<string, unknown>>> {
  const out = await crmFetch<{ transactions: Array<Record<string, unknown>> }>(
    token,
    '/api/crm/sales/transactions',
  );
  return out.transactions ?? [];
}

export async function fetchSalesReports(token: string): Promise<Record<string, unknown>> {
  return crmFetch(token, '/api/crm/sales/reports');
}

export async function fetchKpiAlerts(
  token: string,
  params?: { year?: number; month?: number; staff_id?: number },
): Promise<Array<Record<string, unknown>>> {
  const qs = new URLSearchParams();
  if (params?.year != null) qs.set('year', String(params.year));
  if (params?.month != null) qs.set('month', String(params.month));
  if (params?.staff_id != null) qs.set('staff_id', String(params.staff_id));
  const suffix = qs.toString() ? `?${qs.toString()}` : '';
  const out = await crmFetch<{ alerts: Array<Record<string, unknown>> }>(token, `/api/crm/kpi/alerts${suffix}`);
  return out.alerts ?? [];
}

export async function fetchKpiChart(
  token: string,
  params: { metric_id: number; year?: number; month?: number; staff_id?: number },
): Promise<Record<string, unknown>> {
  const qs = new URLSearchParams({ metric_id: String(params.metric_id) });
  if (params.year != null) qs.set('year', String(params.year));
  if (params.month != null) qs.set('month', String(params.month));
  if (params.staff_id != null) qs.set('staff_id', String(params.staff_id));
  return crmFetch(token, `/api/crm/kpi/chart?${qs.toString()}`);
}

export async function exportStaffKpi(
  token: string,
  params?: { year?: number; month?: number; staff_id?: number },
): Promise<Record<string, unknown>> {
  const qs = new URLSearchParams();
  if (params?.year != null) qs.set('year', String(params.year));
  if (params?.month != null) qs.set('month', String(params.month));
  if (params?.staff_id != null) qs.set('staff_id', String(params.staff_id));
  const suffix = qs.toString() ? `?${qs.toString()}` : '';
  return crmFetch(token, `/api/crm/staff/kpi/export${suffix}`);
}

export async function patchStaffKpiProgress(
  token: string,
  kpiId: number,
  body: Record<string, unknown>,
): Promise<Record<string, unknown>> {
  return crmFetch(token, `/api/crm/staff/kpi/${kpiId}`, {
    method: 'PATCH',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
  });
}

export async function fetchStaffLevels(token: string): Promise<Array<Record<string, unknown>>> {
  const out = await crmFetch<{ staff_levels: Array<Record<string, unknown>> }>(token, '/api/crm/staff/levels');
  return out.staff_levels ?? [];
}

export async function saveStaffLevels(
  token: string,
  staffLevels: Array<Record<string, unknown>>,
): Promise<Record<string, unknown>> {
  return crmFetch(token, '/api/crm/staff/levels', {
    method: 'PUT',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ staff_levels: staffLevels }),
  });
}

export async function fetchStaffCompetency(token: string): Promise<Record<string, unknown>> {
  const out = await crmFetch<{ competency: Record<string, unknown> }>(token, '/api/crm/staff/competency');
  return out.competency ?? {};
}

export async function saveStaffCompetency(
  token: string,
  competency: Record<string, unknown>,
): Promise<Record<string, unknown>> {
  return crmFetch(token, '/api/crm/staff/competency', {
    method: 'PUT',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ competency }),
  });
}

export async function importCrmStaff(
  token: string,
  rows: Array<Record<string, unknown>>,
): Promise<Record<string, unknown>> {
  return crmFetch(token, '/api/crm/staff/import', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ rows }),
  });
}

export interface ProposalRow {
  id: number;
  customer_id: number;
  lifecycle_id: number | null;
  service_slugs: string[];
  total_vnd: number;
  timeline_months: number;
  notes: string;
  created_at: string;
  updated_at: string;
}

export async function fetchProposals(token: string, customerId: number): Promise<ProposalRow[]> {
  const out = await crmFetch<{ proposals: ProposalRow[] }>(
    token,
    `/api/crm/proposals?customer_id=${customerId}`,
  );
  return out.proposals ?? [];
}

export async function fetchProposalDetail(token: string, id: number): Promise<ProposalRow> {
  return crmFetch<ProposalRow>(token, `/api/crm/proposals/${id}`);
}

export async function createProposal(
  token: string,
  body: {
    customer_id: number;
    service_slugs: string[];
    total_vnd?: number;
    timeline_months?: number;
    notes?: string;
    lifecycle_id?: number | null;
  },
): Promise<ProposalRow> {
  return crmFetch<ProposalRow>(token, '/api/crm/proposals', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
  });
}

export async function deleteProposal(token: string, id: number): Promise<void> {
  await crmFetch(token, `/api/crm/proposals/${id}`, { method: 'DELETE' });
}

export async function generateProposal(token: string, id: number): Promise<Record<string, unknown>> {
  return crmFetch(token, `/api/crm/proposals/${id}/generate`, { method: 'POST' });
}

export interface ReProjectRow {
  id: number;
  code: string;
  name: string;
  project_type: string;
  project_type_label?: string;
  status: string;
  city: string;
  district: string;
  total_units: number;
  sold_units: number;
  updated_at: string;
}

export async function fetchReProjects(token: string, q?: string): Promise<ReProjectRow[]> {
  const qs = q ? `?q=${encodeURIComponent(q)}` : '';
  const out = await crmFetch<{ projects: ReProjectRow[] }>(token, `/api/crm/re-projects${qs}`);
  return out.projects ?? [];
}

export async function fetchReProjectDetail(token: string, id: number): Promise<Record<string, unknown>> {
  return crmFetch(token, `/api/crm/re-projects/${id}`);
}

export async function fetchReProjectSummary(token: string, id: number): Promise<Record<string, unknown>> {
  return crmFetch(token, `/api/crm/re-projects/${id}/summary`);
}

export async function createReProject(
  token: string,
  body: Record<string, unknown>,
): Promise<Record<string, unknown>> {
  return crmFetch(token, '/api/crm/re-projects', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
  });
}

export async function fetchReProjectProducts(
  token: string,
  projectId: number,
): Promise<Array<Record<string, unknown>>> {
  const out = await crmFetch<{ products: Array<Record<string, unknown>> }>(
    token,
    `/api/crm/re-projects/${projectId}/products`,
  );
  return out.products ?? [];
}

export async function fetchReProjectInventoryByZone(
  token: string,
  projectId: number,
): Promise<Array<Record<string, unknown>>> {
  const out = await crmFetch<{ zones: Array<Record<string, unknown>> }>(
    token,
    `/api/crm/re-projects/${projectId}/inventory-by-zone`,
  );
  return out.zones ?? [];
}

export async function fetchReProjectAccountingDashboard(
  token: string,
  projectId: number,
): Promise<Record<string, unknown>> {
  return crmFetch(token, `/api/crm/re-projects/${projectId}/accounting/dashboard`);
}

export async function fetchReProjectCashFlow(
  token: string,
  projectId: number,
): Promise<Array<Record<string, unknown>>> {
  const out = await crmFetch<{ lines: Array<Record<string, unknown>> }>(
    token,
    `/api/crm/re-projects/${projectId}/accounting/cash-flow`,
  );
  return out.lines ?? [];
}

export async function createReProjectCashFlow(
  token: string,
  projectId: number,
  body: Record<string, unknown>,
): Promise<Record<string, unknown>> {
  return crmFetch(token, `/api/crm/re-projects/${projectId}/accounting/cash-flow`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
  });
}

export async function syncReProjectAccountingFromPlans(
  token: string,
  projectId: number,
): Promise<Record<string, unknown>> {
  return crmFetch(token, `/api/crm/re-projects/${projectId}/accounting/sync-from-plans`, { method: 'POST' });
}

export async function syncReProjectAccountingInventory(
  token: string,
  projectId: number,
): Promise<Record<string, unknown>> {
  return crmFetch(token, `/api/crm/re-projects/${projectId}/accounting/sync-inventory-revenue`, {
    method: 'POST',
  });
}

export async function fetchReProjectAccountingForecast(
  token: string,
  projectId: number,
  monthsAhead = 3,
): Promise<Record<string, unknown>> {
  return crmFetch(
    token,
    `/api/crm/re-projects/${projectId}/accounting/forecast?months_ahead=${monthsAhead}`,
  );
}

export async function fetchReProjectAccountingRisks(
  token: string,
  projectId: number,
): Promise<Record<string, unknown>> {
  return crmFetch(token, `/api/crm/re-projects/${projectId}/accounting/risk-predictions`);
}

export async function exportReProjectAccounting(
  token: string,
  projectId: number,
): Promise<Record<string, unknown>> {
  return crmFetch(token, `/api/crm/re-projects/${projectId}/accounting/export`);
}

export async function fetchReProjectKpis(
  token: string,
  projectId: number,
): Promise<{ kpis: Array<Record<string, unknown>>; board: Record<string, unknown> | null }> {
  return crmFetch(token, `/api/crm/re-projects/${projectId}/kpis`);
}

export async function createReProjectKpi(
  token: string,
  projectId: number,
  body: Record<string, unknown>,
): Promise<Record<string, unknown>> {
  return crmFetch(token, `/api/crm/re-projects/${projectId}/kpis`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
  });
}

export async function syncReProjectKpisToStaff(
  token: string,
  projectId: number,
): Promise<Record<string, unknown>> {
  return crmFetch(token, `/api/crm/re-projects/${projectId}/kpis/sync-to-staff`, { method: 'POST' });
}

export async function pullReProjectKpisFromStaff(
  token: string,
  projectId: number,
): Promise<Record<string, unknown>> {
  return crmFetch(token, `/api/crm/re-projects/${projectId}/kpis/pull-from-staff`, { method: 'POST' });
}

export async function refreshReProjectLeadsNewKpi(
  token: string,
  projectId: number,
  body?: Record<string, unknown>,
): Promise<Record<string, unknown>> {
  return crmFetch(token, `/api/crm/re-projects/${projectId}/kpis/refresh-leads-new`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body ?? {}),
  });
}

export async function fetchReProjectBudget(
  token: string,
  projectId: number,
): Promise<Array<Record<string, unknown>>> {
  const out = await crmFetch<{ lines: Array<Record<string, unknown>> }>(
    token,
    `/api/crm/re-projects/${projectId}/budget`,
  );
  return out.lines ?? [];
}

export async function createReProjectBudgetLine(
  token: string,
  projectId: number,
  body: Record<string, unknown>,
): Promise<Record<string, unknown>> {
  return crmFetch(token, `/api/crm/re-projects/${projectId}/budget`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
  });
}

export async function fetchReProjectRisks(
  token: string,
  projectId: number,
): Promise<Array<Record<string, unknown>>> {
  const out = await crmFetch<{ risks: Array<Record<string, unknown>> }>(
    token,
    `/api/crm/re-projects/${projectId}/risks`,
  );
  return out.risks ?? [];
}

export async function createReProjectRisk(
  token: string,
  projectId: number,
  body: Record<string, unknown>,
): Promise<Record<string, unknown>> {
  return crmFetch(token, `/api/crm/re-projects/${projectId}/risks`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
  });
}

export async function fetchReProjectStaff(
  token: string,
  projectId: number,
): Promise<Array<Record<string, unknown>>> {
  const out = await crmFetch<{ staff: Array<Record<string, unknown>> }>(
    token,
    `/api/crm/re-projects/${projectId}/staff`,
  );
  return out.staff ?? [];
}

export async function addReProjectStaff(
  token: string,
  projectId: number,
  body: Record<string, unknown>,
): Promise<Record<string, unknown>> {
  return crmFetch(token, `/api/crm/re-projects/${projectId}/staff`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
  });
}

export async function fetchReProjectLeadConfig(
  token: string,
  projectId: number,
): Promise<Record<string, unknown>> {
  const out = await crmFetch<{ config: Record<string, unknown> }>(
    token,
    `/api/crm/re-projects/${projectId}/lead-config`,
  );
  return out.config ?? {};
}

export async function saveReProjectLeadConfig(
  token: string,
  projectId: number,
  body: Record<string, unknown>,
): Promise<Record<string, unknown>> {
  const out = await crmFetch<{ config: Record<string, unknown> }>(
    token,
    `/api/crm/re-projects/${projectId}/lead-config`,
    {
      method: 'PUT',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(body),
    },
  );
  return out.config ?? {};
}

export async function fetchReProjectWorkflow(
  token: string,
  projectId: number,
): Promise<Record<string, unknown>> {
  return crmFetch(token, `/api/crm/re-projects/${projectId}/workflow`);
}

export async function exportReProject(
  token: string,
  projectId: number,
  report = 'full',
): Promise<Record<string, unknown>> {
  const qs = report ? `?report=${encodeURIComponent(report)}` : '';
  return crmFetch(token, `/api/crm/re-projects/${projectId}/export${qs}`);
}

export async function fetchPayrollDashboard(
  token: string,
  params?: { year?: number; month?: number },
): Promise<Record<string, unknown>> {
  const qs = new URLSearchParams();
  if (params?.year != null) qs.set('year', String(params.year));
  if (params?.month != null) qs.set('month', String(params.month));
  const suffix = qs.toString() ? `?${qs.toString()}` : '';
  return crmFetch(token, `/api/crm/payroll/dashboard${suffix}`);
}

export async function fetchPayrollPeriod(
  token: string,
  year: number,
  month: number,
): Promise<{ payroll: Record<string, unknown> | null; lines: Array<Record<string, unknown>> }> {
  return crmFetch(token, `/api/crm/payroll?year=${year}&month=${month}`);
}

export async function computePayroll(
  token: string,
  body: { year: number; month: number; workdays_standard?: number },
): Promise<{ payroll: Record<string, unknown>; lines: Array<Record<string, unknown>> }> {
  return crmFetch(token, '/api/crm/payroll/compute', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
  });
}

export async function fetchPayrollPolicy(token: string): Promise<Record<string, unknown>> {
  const out = await crmFetch<{ policy: Record<string, unknown> }>(token, '/api/crm/payroll/policy');
  return out.policy ?? {};
}

export async function fetchPayrollAttendance(
  token: string,
  params?: { staff_id?: number; from?: string; to?: string },
): Promise<Array<Record<string, unknown>>> {
  const qs = new URLSearchParams();
  if (params?.staff_id != null) qs.set('staff_id', String(params.staff_id));
  if (params?.from) qs.set('from', params.from);
  if (params?.to) qs.set('to', params.to);
  const suffix = qs.toString() ? `?${qs.toString()}` : '';
  const out = await crmFetch<{ attendance: Array<Record<string, unknown>> }>(
    token,
    `/api/crm/payroll/attendance${suffix}`,
  );
  return out.attendance ?? [];
}

export async function exportPayrollJson(
  token: string,
  params?: { year?: number; month?: number },
): Promise<Record<string, unknown>> {
  const qs = new URLSearchParams({ period: 'month' });
  if (params?.year != null) qs.set('year', String(params.year));
  if (params?.month != null) qs.set('month', String(params.month));
  return crmFetch(token, `/api/crm/payroll/export?${qs.toString()}`);
}

export async function fetchFinanceBusinessDashboard(
  token: string,
  params?: { year?: number; month?: number; trend_months?: number },
): Promise<Record<string, unknown>> {
  const qs = new URLSearchParams();
  if (params?.year != null) qs.set('year', String(params.year));
  if (params?.month != null) qs.set('month', String(params.month));
  if (params?.trend_months != null) qs.set('trend_months', String(params.trend_months));
  const suffix = qs.toString() ? `?${qs.toString()}` : '';
  return crmFetch(token, `/api/crm/finance/business-dashboard${suffix}`);
}

export async function fetchFinanceKpiAlerts(
  token: string,
  params?: { year?: number; month?: number },
): Promise<Record<string, unknown>> {
  const qs = new URLSearchParams();
  if (params?.year != null) qs.set('year', String(params.year));
  if (params?.month != null) qs.set('month', String(params.month));
  const suffix = qs.toString() ? `?${qs.toString()}` : '';
  return crmFetch(token, `/api/crm/finance/kpi-alerts${suffix}`);
}

export async function fetchFinanceKpiTrends(
  token: string,
  params?: { year?: number; month?: number; trend_months?: number },
): Promise<Record<string, unknown>> {
  const qs = new URLSearchParams();
  if (params?.year != null) qs.set('year', String(params.year));
  if (params?.month != null) qs.set('month', String(params.month));
  if (params?.trend_months != null) qs.set('trend_months', String(params.trend_months));
  const suffix = qs.toString() ? `?${qs.toString()}` : '';
  return crmFetch(token, `/api/crm/finance/kpi-trends${suffix}`);
}

export async function fetchFinanceKpiConfig(token: string): Promise<Record<string, unknown>> {
  return crmFetch(token, '/api/crm/finance/kpi-config');
}

export async function patchFinanceKpiConfig(
  token: string,
  body: Record<string, unknown>,
): Promise<Record<string, unknown>> {
  return crmFetch(token, '/api/crm/finance/kpi-config', {
    method: 'PATCH',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
  });
}

export async function fetchFinanceFinancials(
  token: string,
  params?: { year?: number; month?: number },
): Promise<Record<string, unknown>> {
  const qs = new URLSearchParams();
  if (params?.year != null) qs.set('year', String(params.year));
  if (params?.month != null) qs.set('month', String(params.month));
  const suffix = qs.toString() ? `?${qs.toString()}` : '';
  return crmFetch(token, `/api/crm/finance/financials${suffix}`);
}

export async function fetchFinanceArAging(token: string): Promise<Record<string, unknown>> {
  return crmFetch(token, '/api/crm/finance/ar-aging');
}

export async function fetchOwnerWeeklyDashboard(
  token: string,
  params?: { year?: number; week?: number; trend_weeks?: number; week_end?: string },
): Promise<Record<string, unknown>> {
  const qs = new URLSearchParams();
  if (params?.year != null) qs.set('year', String(params.year));
  if (params?.week != null) qs.set('week', String(params.week));
  if (params?.trend_weeks != null) qs.set('trend_weeks', String(params.trend_weeks));
  if (params?.week_end) qs.set('week_end', params.week_end);
  const suffix = qs.toString() ? `?${qs.toString()}` : '';
  return crmFetch(token, `/api/crm/owner-weekly${suffix}`);
}

export async function fetchOwnerWeeklyConfig(token: string): Promise<Record<string, unknown>> {
  return crmFetch(token, '/api/crm/owner-weekly/config');
}

export async function patchOwnerWeeklyConfig(
  token: string,
  body: Record<string, unknown>,
): Promise<Record<string, unknown>> {
  return crmFetch(token, '/api/crm/owner-weekly/config', {
    method: 'PATCH',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
  });
}

export async function fetchOwnerWeeklyCashSnapshots(
  token: string,
  params?: { limit?: number },
): Promise<Array<Record<string, unknown>>> {
  const qs = new URLSearchParams();
  if (params?.limit != null) qs.set('limit', String(params.limit));
  const suffix = qs.toString() ? `?${qs.toString()}` : '';
  const out = await crmFetch<{ snapshots: Array<Record<string, unknown>> }>(
    token,
    `/api/crm/owner-weekly/cash-snapshots${suffix}`,
  );
  return out.snapshots ?? [];
}

export async function exportOwnerWeekly(
  token: string,
  params?: { year?: number; week?: number; week_end?: string },
): Promise<Record<string, unknown>> {
  const qs = new URLSearchParams();
  if (params?.year != null) qs.set('year', String(params.year));
  if (params?.week != null) qs.set('week', String(params.week));
  if (params?.week_end) qs.set('week_end', params.week_end);
  const suffix = qs.toString() ? `?${qs.toString()}` : '';
  return crmFetch(token, `/api/crm/owner-weekly/export${suffix}`);
}

export interface CrmBoardModuleCard {
  id: string;
  label: string;
  href: string;
  description: string;
}

export interface CrmBoardResponse {
  title: string;
  modules: CrmBoardModuleCard[];
  caps_count: number;
}

export async function fetchCrmBoard(token: string): Promise<CrmBoardResponse> {
  return crmFetch(token, '/api/crm/board');
}

export async function fetchSvcFinanceSummary(
  token: string,
  lifecycleId: number,
): Promise<Record<string, unknown>> {
  return crmFetch(token, `/api/crm/svc-finance/${lifecycleId}/summary`);
}

export async function createSvcPayment(
  token: string,
  body: Record<string, unknown>,
): Promise<Record<string, unknown>> {
  return crmFetch(token, '/api/crm/svc-payments', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
  });
}

export async function patchSvcPayment(
  token: string,
  paymentId: number,
  body: Record<string, unknown>,
): Promise<Record<string, unknown>> {
  return crmFetch(token, `/api/crm/svc-payments/${paymentId}`, {
    method: 'PATCH',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
  });
}

export async function deleteSvcPayment(token: string, paymentId: number): Promise<void> {
  await crmFetch(token, `/api/crm/svc-payments/${paymentId}`, { method: 'DELETE' });
}

export async function fetchCrmStaffList(
  token: string,
  params?: { q?: string },
): Promise<{ staff: CrmStaffRow[]; summary: Record<string, number> }> {
  const qs = params?.q ? `?q=${encodeURIComponent(params.q)}` : '';
  return crmFetch(token, `/api/crm/staff${qs}`);
}

export async function fetchCrmStaffWorkspace(
  token: string,
  staffId: number,
): Promise<Record<string, unknown>> {
  return crmFetch(token, `/api/crm/staff/${staffId}/workspace`);
}

export async function fetchKpiMetrics(token: string): Promise<KpiMetricRow[]> {
  const out = await crmFetch<{ metrics: KpiMetricRow[] }>(token, '/api/crm/kpi/metrics');
  return out.metrics ?? [];
}

export async function fetchStaffKpiAutoMetrics(
  token: string,
  staffId: number,
  params?: { role?: string; year?: number; month?: number },
): Promise<Record<string, unknown>> {
  const qs = new URLSearchParams();
  if (params?.role) qs.set('role', params.role);
  if (params?.year != null) qs.set('year', String(params.year));
  if (params?.month != null) qs.set('month', String(params.month));
  const suffix = qs.toString() ? `?${qs.toString()}` : '';
  return crmFetch(token, `/api/crm/staff-kpi/${staffId}/metrics${suffix}`);
}

export interface CatalogServiceRow {
  id: number;
  slug: string;
  name: string;
  description: string;
  sort_order: number;
  active: boolean;
}

export interface CatalogIndustryRow {
  id: number;
  slug: string;
  name: string;
  description: string;
  traits: Record<string, unknown>;
  sort_order: number;
  active: boolean;
}

export interface AssignScopeRow {
  id: number;
  staff_id: number;
  industry_slug: string;
  service_slug: string;
  active: boolean;
  staff_name: string;
}

export interface CatalogStaffOption {
  id: number;
  name: string;
  internal_code: string;
}

export interface CatalogBundle {
  services: CatalogServiceRow[];
  industries: CatalogIndustryRow[];
  scopes: AssignScopeRow[];
  staff: CatalogStaffOption[];
}

async function catalogFetch<T>(token: string, path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(`${API_BASE}${path}`, {
    ...init,
    headers: {
      ...authHeaders(token),
      ...(init?.headers ?? {}),
    },
  });
  const body = await parseJson<T & { error?: string; message?: string }>(res);
  if (!res.ok) {
    throw new ApiError(body.error ?? body.message ?? 'Catalog request failed', res.status);
  }
  return body;
}

export async function fetchCatalogBundle(token: string): Promise<CatalogBundle> {
  const [pub, scopesPayload] = await Promise.all([
    catalogFetch<{ services: CatalogServiceRow[]; industries: CatalogIndustryRow[] }>(
      token,
      '/api/crm/catalog',
    ),
    catalogFetch<{ scopes: AssignScopeRow[]; staff: CatalogStaffOption[] }>(
      token,
      '/api/crm/assign-scopes',
    ),
  ]);
  return {
    services: pub.services ?? [],
    industries: pub.industries ?? [],
    scopes: scopesPayload.scopes ?? [],
    staff: scopesPayload.staff ?? [],
  };
}

export async function createCatalogService(
  token: string,
  body: { slug: string; name: string; description?: string; sort_order?: number },
): Promise<CatalogServiceRow> {
  const out = await catalogFetch<{ service: CatalogServiceRow }>(token, '/api/crm/catalog/services', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
  });
  return out.service;
}

export async function patchCatalogService(
  token: string,
  id: number,
  body: { name?: string; active?: boolean; sort_order?: number },
): Promise<CatalogServiceRow> {
  const out = await catalogFetch<{ service: CatalogServiceRow }>(
    token,
    `/api/crm/catalog/services/${id}`,
    {
      method: 'PATCH',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(body),
    },
  );
  return out.service;
}

export async function createCatalogIndustry(
  token: string,
  body: { slug: string; name: string; description?: string; sort_order?: number },
): Promise<CatalogIndustryRow> {
  const out = await catalogFetch<{ industry: CatalogIndustryRow }>(
    token,
    '/api/crm/catalog/industries',
    {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(body),
    },
  );
  return out.industry;
}

export async function patchCatalogIndustry(
  token: string,
  id: number,
  body: { name?: string; active?: boolean; sort_order?: number },
): Promise<CatalogIndustryRow> {
  const out = await catalogFetch<{ industry: CatalogIndustryRow }>(
    token,
    `/api/crm/catalog/industries/${id}`,
    {
      method: 'PATCH',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(body),
    },
  );
  return out.industry;
}

export async function createAssignScope(
  token: string,
  body: { staff_id: number; industry_slug?: string; service_slug?: string },
): Promise<AssignScopeRow> {
  const out = await catalogFetch<{ scope: AssignScopeRow }>(token, '/api/crm/assign-scopes', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
  });
  return out.scope;
}

export async function deleteAssignScope(token: string, id: number): Promise<void> {
  await catalogFetch<{ ok: boolean }>(token, `/api/crm/assign-scopes/${id}`, { method: 'DELETE' });
}

export async function fetchNestHealth(): Promise<Record<string, unknown>> {
  const res = await fetch(`${API_BASE}/health`, { cache: 'no-store' });
  return parseJson(res);
}

export interface AgencyClient {
  id: string;
  code: string;
  name: string;
  industry_slug: string | null;
  status: string;
  owner_am_id: string | null;
  notes?: string | null;
  channels?: string;
  channel_accounts?: Array<{
    id: string;
    channel: string;
    external_account_id: string | null;
    display_name: string | null;
    status: string | null;
    has_token?: boolean;
    token_status?: string | null;
    token_expires_at?: string | null;
    facebook_page_id?: string | null;
  }>;
  side_effects?: {
    domain_event_id?: string | null;
    jobs_enqueued?: Array<{ id: string; job_type: string; status: string; created?: boolean }>;
    workflow_signal?: string;
  };
  created_at: string | null;
  updated_at: string | null;
}

export interface AgencyStats {
  pg_ready: boolean;
  clients: Record<string, number>;
  jobs: Record<string, number>;
}

export interface PerformanceRow {
  performance_date: string | null;
  external_campaign_name: string | null;
  external_campaign_id: string | null;
  spend: number;
  leads_crm: number;
  cpl: number | null;
  target_cpl_vnd: number | null;
  cpl_delta_pct: number | null;
  roas: number | null;
}

export interface PerformanceResponse {
  ok: boolean;
  rows: PerformanceRow[];
  summary: Record<string, unknown>;
}

export interface FacebookHubClient {
  id: string;
  code: string | null;
  name: string | null;
  status: string | null;
  spend: number;
  leads_crm: number;
  cpl: number | null;
  campaigns: number;
  unmapped_campaigns: number;
  over_target_rows: number;
  meta_has_token?: boolean;
  token_status?: string;
}

export interface FacebookHubAlert {
  severity: 'warn' | 'danger';
  message: string;
  link: string;
  link_label: string;
}

export interface FacebookHubResponse {
  ok: boolean;
  summary: Record<string, unknown>;
  clients: FacebookHubClient[];
  alerts: FacebookHubAlert[];
  date_from: string;
  date_to: string;
  window_days?: number;
  filters?: {
    client_id?: string | null;
    status?: string | null;
    q?: string | null;
  };
}

export interface FacebookHubQuery {
  days?: number;
  date_to?: string;
  date_from?: string;
  status?: string;
  client_id?: string;
  q?: string;
}

export interface FacebookAdsMigrationStatus {
  ok: boolean;
  flask_meta_ads_admin_retired: boolean;
  ops_web_hub_url: string;
  ops_web_hub_path?: string;
  legacy_rs_path?: string;
  canonical_upstream: string;
  webhooks_nest_meta?: boolean;
  webhooks_flask_fallback?: boolean;
  horizon1_expect_meta_hub_retired?: boolean;
  gate_m1_g09: boolean;
  gate_m1_g06?: boolean;
  gate_m1_g06_config?: boolean;
  gate_m1_g06_live?: boolean | null;
  nginx_redirect_live_skipped?: boolean;
  nginx_deploy_config_ok?: boolean;
  gate_m1_g11?: boolean;
  retirement_dry_run_ok?: boolean | null;
  retirement_dry_run_artifact_present?: boolean;
  retirement_env_pending_changes?: number | null;
  retirement_env_already_applied?: boolean | null;
  retirement_next_apply_command?: string;
  gate_m1_g12?: boolean;
  retirement_applied_ok?: boolean | null;
  retirement_env_applied_ok?: boolean | null;
  retirement_apply_artifact_present?: boolean;
  gate_m1_g07?: boolean;
  autosync_standalone_ok?: boolean;
  autosync_unit_present?: boolean;
  autosync_daemon_present?: boolean;
  autosync_gunicorn_background_off?: boolean;
  autosync_unit_no_ptt_dependency?: boolean;
  gate_m1_g08?: boolean;
  soak_7d_ok?: boolean;
  soak_span_days?: number | null;
  soak_sample_count?: number;
  soak_required_days?: number;
  soak_min_samples?: number;
  soak_failure_count?: number;
  soak_latest_recorded_at?: string | null;
  soak_error?: string | null;
  manual_uat?: MetaMigrationManualUat;
  manual_uat_updated_at?: string | null;
  signoff_path?: string;
  ops_web_migration_url?: string;
}

export type MetaMigrationManualUatField =
  | 'ops_web_hub_cpl_summary'
  | 'webhook_test_lead_created'
  | 'autosync_single_process'
  | 'portal_meta_readonly'
  | 'campaign_write_approve_smoke';

export type MetaMigrationManualUat = Record<MetaMigrationManualUatField, boolean>;

export interface MetaMigrationSignoffResponse {
  ok: boolean;
  path: string;
  manual_uat: MetaMigrationManualUat;
  updated_at: string | null;
  signed_at: string | null;
  created_from_template?: boolean;
}

export interface HubMapRow {
  map_id?: string;
  hub_campaign_id: number | null;
  channel: string;
  external_campaign_id: string | null;
  external_campaign_name: string | null;
  external_account_id?: string | null;
  target_cpl_vnd: number | null;
  active: boolean;
  client_id?: string;
  client_code?: string | null;
  client_name?: string | null;
}

export interface HubMapCreateBody {
  channel?: string;
  external_campaign_id: string;
  external_campaign_name?: string;
  external_account_id?: string;
  target_cpl_vnd?: number;
}

export interface HubMapUpdateBody {
  external_campaign_id?: string;
  external_campaign_name?: string | null;
  external_account_id?: string | null;
  target_cpl_vnd?: number | null;
  active?: boolean;
}

async function agencyFetch<T>(token: string, path: string): Promise<T> {
  const res = await fetch(`${API_BASE}${path}`, {
    headers: authHeaders(token),
    cache: 'no-store',
  });
  const body = await parseJson<T & { error?: string; message?: string }>(res);
  if (!res.ok) {
    throw new ApiError(body.error ?? body.message ?? 'Agency API failed', res.status);
  }
  return body;
}

async function agencyMutate<T>(
  token: string,
  path: string,
  init: RequestInit,
): Promise<T> {
  const res = await fetch(`${API_BASE}${path}`, {
    ...init,
    headers: {
      ...authHeaders(token),
      'Content-Type': 'application/json',
      ...(init.headers ?? {}),
    },
  });
  const body = await parseJson<T & { error?: string; message?: string }>(res);
  if (!res.ok) {
    throw new ApiError(body.error ?? body.message ?? 'Agency API failed', res.status);
  }
  return body;
}

export async function fetchAgencyStats(token: string): Promise<AgencyStats> {
  return agencyFetch(token, '/api/v1/agency/stats');
}

export async function fetchAgencyClients(
  token: string,
  params?: { q?: string; status?: string },
): Promise<{ clients: AgencyClient[] }> {
  const qs = new URLSearchParams();
  if (params?.q) qs.set('q', params.q);
  if (params?.status) qs.set('status', params.status);
  const suffix = qs.toString() ? `?${qs.toString()}` : '';
  return agencyFetch(token, `/api/v1/clients${suffix}`);
}

export async function fetchAgencyClient(token: string, id: string): Promise<AgencyClient> {
  return agencyFetch(token, `/api/v1/clients/${id}`);
}

export async function fetchClientPerformance(
  token: string,
  clientId: string,
  params?: { from?: string; to?: string; group_by?: string },
): Promise<PerformanceResponse> {
  const qs = new URLSearchParams();
  if (params?.from) qs.set('from', params.from);
  if (params?.to) qs.set('to', params.to);
  if (params?.group_by) qs.set('group_by', params.group_by);
  const suffix = qs.toString() ? `?${qs.toString()}` : '';
  return agencyFetch(token, `/api/v1/clients/${clientId}/performance${suffix}`);
}

export async function fetchFacebookAdsMigrationStatus(
  token: string,
): Promise<FacebookAdsMigrationStatus> {
  return agencyFetch(token, '/api/v1/facebook-ads/migration-status');
}

export async function fetchFacebookAdsMigrationSignoff(
  token: string,
): Promise<MetaMigrationSignoffResponse> {
  return agencyFetch(token, '/api/v1/facebook-ads/migration-signoff');
}

export async function patchFacebookAdsMigrationManualUat(
  token: string,
  updates: Partial<MetaMigrationManualUat>,
): Promise<{ ok: boolean; manual_uat: MetaMigrationManualUat; updated_at: string; path: string }> {
  return agencyMutate(token, '/api/v1/facebook-ads/migration-signoff/manual-uat', {
    method: 'PATCH',
    body: JSON.stringify(updates),
  });
}

export async function fetchFacebookHub(
  token: string,
  params: FacebookHubQuery = {},
): Promise<FacebookHubResponse> {
  const qs = new URLSearchParams();
  if (params.days != null) qs.set('days', String(params.days));
  if (params.date_to) qs.set('date_to', params.date_to);
  if (params.date_from) qs.set('date_from', params.date_from);
  if (params.status) qs.set('status', params.status);
  if (params.client_id) qs.set('client_id', params.client_id);
  if (params.q) qs.set('q', params.q);
  const suffix = qs.toString() ? `?${qs.toString()}` : '';
  return agencyFetch(token, `/api/v1/facebook-ads/hub${suffix}`);
}

export async function downloadFacebookHubExport(
  token: string,
  params: FacebookHubQuery & { scope?: 'clients' | 'campaigns' } = {},
): Promise<{ blob: Blob; filename: string }> {
  const qs = new URLSearchParams();
  if (params.days != null) qs.set('days', String(params.days));
  if (params.date_to) qs.set('date_to', params.date_to);
  if (params.date_from) qs.set('date_from', params.date_from);
  if (params.status) qs.set('status', params.status);
  if (params.client_id) qs.set('client_id', params.client_id);
  if (params.q) qs.set('q', params.q);
  if (params.scope) qs.set('scope', params.scope);
  const suffix = qs.toString() ? `?${qs.toString()}` : '';
  const res = await fetch(`${API_BASE}/api/v1/facebook-ads/hub/export${suffix}`, {
    headers: { Authorization: `Bearer ${token}` },
  });
  if (!res.ok) {
    const text = await res.text();
    throw new Error(text || `Export failed (${res.status})`);
  }
  const cd = res.headers.get('content-disposition') ?? '';
  const match = /filename="([^"]+)"/.exec(cd);
  const filename = match?.[1] ?? 'meta-hub-export.csv';
  const blob = await res.blob();
  return { blob, filename };
}

export async function fetchHubCampaignMaps(
  token: string,
  params?: { client_id?: string; campaign_id?: string },
): Promise<{ ok: boolean; maps: HubMapRow[]; count: number }> {
  const qs = new URLSearchParams();
  if (params?.client_id) qs.set('client_id', params.client_id);
  if (params?.campaign_id) qs.set('campaign_id', params.campaign_id);
  const suffix = qs.toString() ? `?${qs.toString()}` : '';
  return agencyFetch(token, `/api/v1/crm/hub-campaign-maps${suffix}`);
}

export interface JobRow {
  id: string;
  job_type: string;
  status: string;
  client_code: string | null;
  channel: string | null;
  last_error: string | null;
  created_at: string | null;
}

export async function fetchAgencyJobs(
  token: string,
  status?: string,
): Promise<{ stats: Record<string, number>; jobs: JobRow[] }> {
  const qs = status ? `?status=${encodeURIComponent(status)}` : '';
  return agencyFetch(token, `/api/v1/jobs${qs}`);
}

export interface NotificationRow {
  id: string;
  category: string;
  title: string;
  body: string | null;
  link_url: string | null;
  read: boolean;
  created_at: string | null;
}

export async function fetchAgencyNotifications(
  token: string,
): Promise<{ notifications: NotificationRow[]; unread: number }> {
  return agencyFetch(token, '/api/v1/notifications?limit=50');
}

export interface CreateClientBody {
  code: string;
  name: string;
  industry_slug?: string;
  owner_am_id?: string;
}

export async function createAgencyClient(
  token: string,
  body: CreateClientBody,
): Promise<AgencyClient> {
  return agencyMutate(token, '/api/v1/clients', { method: 'POST', body: JSON.stringify(body) });
}

export interface UpdateClientBody {
  name?: string;
  industry_slug?: string;
  owner_am_id?: string;
  notes?: string;
  status?: string;
}

export async function patchAgencyClient(
  token: string,
  clientId: string,
  body: UpdateClientBody,
): Promise<AgencyClient> {
  return agencyMutate(token, `/api/v1/clients/${clientId}`, {
    method: 'PATCH',
    body: JSON.stringify(body),
  });
}

export interface OnboardingItem {
  id: string;
  item_key: string;
  label: string;
  sort_order: number;
  completed: boolean;
  completed_at: string | null;
  completed_by: string | null;
  note: string | null;
}

export interface OnboardingResponse {
  items: OnboardingItem[];
  progress: { total: number; completed: number; percent: number };
}

export async function fetchClientOnboarding(
  token: string,
  clientId: string,
): Promise<OnboardingResponse> {
  return agencyFetch(token, `/api/v1/clients/${clientId}/onboarding`);
}

export async function patchClientOnboardingItem(
  token: string,
  clientId: string,
  itemKey: string,
  body: { completed: boolean; completed_by?: string; note?: string },
): Promise<OnboardingResponse> {
  return agencyMutate(token, `/api/v1/clients/${clientId}/onboarding/${encodeURIComponent(itemKey)}`, {
    method: 'PATCH',
    body: JSON.stringify(body),
  });
}

export async function activateAgencyClient(
  token: string,
  clientId: string,
  force = false,
): Promise<AgencyClient> {
  const qs = force ? '?force=1' : '';
  return agencyMutate(token, `/api/v1/clients/${clientId}/activate${qs}`, { method: 'POST', body: '{}' });
}

export async function addClientChannelAccount(
  token: string,
  clientId: string,
  body: { channel: string; external_account_id: string; display_name?: string; facebook_page_id?: string },
): Promise<AgencyClient> {
  return agencyMutate(token, `/api/v1/clients/${clientId}/channel-accounts`, {
    method: 'POST',
    body: JSON.stringify(body),
  });
}

export async function patchClientChannelAccount(
  token: string,
  clientId: string,
  accountId: string,
  body: { display_name?: string; external_account_id?: string; status?: string; facebook_page_id?: string },
): Promise<AgencyClient> {
  return agencyMutate(token, `/api/v1/clients/${clientId}/channel-accounts/${accountId}`, {
    method: 'PATCH',
    body: JSON.stringify(body),
  });
}

export async function deleteClientChannelAccount(
  token: string,
  clientId: string,
  accountId: string,
): Promise<{ ok: boolean }> {
  return agencyMutate(token, `/api/v1/clients/${clientId}/channel-accounts/${accountId}`, {
    method: 'DELETE',
    body: '{}',
  });
}

export async function setClientChannelToken(
  token: string,
  clientId: string,
  accountId: string,
  body: { access_token?: string; credential_ref?: string; token_expires_at?: string; revoke?: boolean },
): Promise<AgencyClient> {
  return agencyMutate(token, `/api/v1/clients/${clientId}/channel-accounts/${accountId}/token`, {
    method: 'PATCH',
    body: JSON.stringify(body),
  });
}

export async function syncClientInsights(
  token: string,
  clientId: string,
): Promise<{ ok: boolean; jobs_enqueued?: NonNullable<AgencyClient['side_effects']>['jobs_enqueued'] }> {
  return agencyMutate(token, `/api/v1/clients/${clientId}/sync/insights`, {
    method: 'POST',
    body: '{}',
  });
}

export interface ClientLeadSummary {
  id: string;
  full_name: string | null;
  phone: string | null;
  email: string | null;
  status: string | null;
  channel: string | null;
  created_at: string | null;
}

export async function fetchClientLeads(
  token: string,
  clientId: string,
): Promise<{ leads: ClientLeadSummary[] }> {
  return agencyFetch(token, `/api/v1/clients/${clientId}/leads`);
}

export async function fetchOnboardingWorkflowStatus(
  token: string,
  clientId: string,
): Promise<{ ok: boolean; status?: string; workflow_id?: string }> {
  return agencyFetch(token, `/api/v1/clients/${clientId}/onboarding/workflow-status`);
}

export async function createKpiDefinition(
  token: string,
  body: { code: string; name: string; formula: string; granularity?: string; description?: string },
): Promise<{ definition: KpiDefinition }> {
  return agencyMutate(token, '/api/v1/kpi-definitions', { method: 'POST', body: JSON.stringify(body) });
}

export async function updateKpiDefinition(
  token: string,
  code: string,
  body: { name?: string; formula?: string; granularity?: string; description?: string },
): Promise<{ ok: boolean }> {
  return agencyMutate(token, `/api/v1/kpi-definitions/${encodeURIComponent(code)}`, {
    method: 'PATCH',
    body: JSON.stringify(body),
  });
}

export async function deleteKpiDefinition(token: string, code: string): Promise<{ ok: boolean }> {
  return agencyMutate(token, `/api/v1/kpi-definitions/${encodeURIComponent(code)}`, {
    method: 'DELETE',
    body: '{}',
  });
}

export async function replayAgencyJob(
  token: string,
  jobId: string,
): Promise<{ id: string; status: string; replayed: boolean }> {
  return agencyMutate(token, `/api/v1/jobs/${jobId}/replay`, { method: 'POST', body: '{}' });
}

export async function markAgencyNotificationRead(
  token: string,
  notificationId: string,
  recipientId = 'ops',
): Promise<{ ok: boolean }> {
  const qs = recipientId ? `?recipient_id=${encodeURIComponent(recipientId)}` : '';
  return agencyMutate(token, `/api/v1/notifications/${notificationId}/read${qs}`, {
    method: 'PATCH',
    body: '{}',
  });
}

export async function markAllAgencyNotificationsRead(
  token: string,
  recipientId = 'ops',
): Promise<{ marked: number }> {
  const qs = recipientId ? `?recipient_id=${encodeURIComponent(recipientId)}` : '';
  return agencyMutate(token, `/api/v1/notifications/mark-all-read${qs}`, {
    method: 'POST',
    body: '{}',
  });
}

export interface KpiDefinition {
  code: string;
  name: string;
  formula: string;
  granularity: string | null;
  description: string | null;
}

export async function fetchKpiDefinitions(
  token: string,
): Promise<{ definitions: KpiDefinition[] }> {
  return agencyFetch(token, '/api/v1/kpi-definitions');
}

export async function fetchClientHubCampaignMaps(
  token: string,
  clientId: string,
  params?: { include_inactive?: boolean },
): Promise<{ ok: boolean; maps: HubMapRow[]; count: number; client_id: string }> {
  const qs = new URLSearchParams();
  if (params?.include_inactive) qs.set('include_inactive', '1');
  const suffix = qs.toString() ? `?${qs.toString()}` : '';
  return agencyFetch(token, `/api/v1/clients/${clientId}/hub-campaign-maps${suffix}`);
}

export async function createClientHubCampaignMap(
  token: string,
  clientId: string,
  body: HubMapCreateBody,
): Promise<{ ok: boolean; map: HubMapRow; jobs_enqueued?: Array<{ id: string; job_type: string }> }> {
  return agencyMutate(token, `/api/v1/clients/${clientId}/hub-campaign-maps`, {
    method: 'POST',
    body: JSON.stringify(body),
  });
}

export async function createHubCampaignMap(
  token: string,
  body: HubMapCreateBody & { client_id: string },
): Promise<{ ok: boolean; map: HubMapRow; jobs_enqueued?: Array<{ id: string; job_type: string }> }> {
  return agencyMutate(token, '/api/v1/crm/hub-campaign-maps', {
    method: 'POST',
    body: JSON.stringify(body),
  });
}

export async function updateHubCampaignMap(
  token: string,
  mapId: string,
  body: HubMapUpdateBody,
  clientId?: string,
): Promise<{ ok: boolean; map: HubMapRow; jobs_enqueued?: Array<{ id: string; job_type: string }> }> {
  const qs = clientId ? `?client_id=${encodeURIComponent(clientId)}` : '';
  return agencyMutate(token, `/api/v1/crm/hub-campaign-maps/${mapId}${qs}`, {
    method: 'PATCH',
    body: JSON.stringify(body),
  });
}

export async function updateClientHubCampaignMap(
  token: string,
  clientId: string,
  mapId: string,
  body: HubMapUpdateBody,
): Promise<{ ok: boolean; map: HubMapRow; jobs_enqueued?: Array<{ id: string; job_type: string }> }> {
  return agencyMutate(token, `/api/v1/clients/${clientId}/hub-campaign-maps/${mapId}`, {
    method: 'PATCH',
    body: JSON.stringify(body),
  });
}

export async function deleteHubCampaignMap(
  token: string,
  mapId: string,
  clientId?: string,
): Promise<{ ok: boolean }> {
  const qs = clientId ? `?client_id=${encodeURIComponent(clientId)}` : '';
  return agencyMutate(token, `/api/v1/crm/hub-campaign-maps/${mapId}${qs}`, {
    method: 'DELETE',
  });
}

export async function deleteClientHubCampaignMap(
  token: string,
  clientId: string,
  mapId: string,
): Promise<{ ok: boolean }> {
  return agencyMutate(token, `/api/v1/clients/${clientId}/hub-campaign-maps/${mapId}`, {
    method: 'DELETE',
  });
}

export interface SeoHubClientRow {
  customer_id: number;
  customer_name: string;
  customer_company: string;
  settings_ok: boolean;
  domains: string[];
  markets: string[];
  contract_tier: string;
  active_projects: number;
  active_initiatives: number;
  aeo_queries: number;
  aeo_visible: number;
  aeo_coverage_pct: number;
  critical_issues: number;
  content_overdue: number;
  health_score: number;
  health_tier: 'good' | 'warn' | 'bad';
}

export interface SeoHubAlert {
  severity: 'warn' | 'danger';
  message: string;
  link: string;
  link_label: string;
}

export interface SeoHubResponse {
  ok: boolean;
  summary: {
    seo_clients: number;
    active_lifecycles: number;
    aeo_queries_total: number;
    aeo_visible_total: number;
    aeo_coverage_pct: number;
    settings_missing: number;
    active_initiatives: number;
    critical_issues: number;
    open_alerts: number;
    failed_sync_runs: number;
    organic_growth_pct: number;
    publish_sla_pct: number;
  };
  clients: SeoHubClientRow[];
  alerts: SeoHubAlert[];
  executive: {
    gsc_totals: Record<string, unknown>;
    content_delivery: Record<string, number>;
  };
}

export async function fetchSeoHub(
  token: string,
  params?: { customer_id?: number; days?: number; market?: string },
): Promise<SeoHubResponse> {
  const qs = new URLSearchParams();
  if (params?.customer_id != null) qs.set('customer_id', String(params.customer_id));
  if (params?.days != null) qs.set('days', String(params.days));
  if (params?.market) qs.set('market', params.market);
  const suffix = qs.toString() ? `?${qs.toString()}` : '';
  return agencyFetch(token, `/api/v1/seo/hub${suffix}`);
}

export async function fetchSeoClients(
  token: string,
  params?: { customer_id?: number; market?: string },
): Promise<{ ok: boolean; clients: SeoHubClientRow[]; total: number }> {
  const qs = new URLSearchParams();
  if (params?.customer_id != null) qs.set('customer_id', String(params.customer_id));
  if (params?.market) qs.set('market', params.market);
  const suffix = qs.toString() ? `?${qs.toString()}` : '';
  return agencyFetch(token, `/api/v1/seo/clients${suffix}`);
}

export interface EmailHubSummary {
  workspaces: number;
  contacts: number;
  emails_sent: number;
  open_rate_pct: number;
  complaint_rate_pct: number;
  pending_approvals: number;
  send_queue_lag_minutes: number;
  revenue_attrib: number;
}

export interface EmailHubClientRow {
  client_id: string;
  client_code: string;
  client_name: string;
  workspace_name: string | null;
  primary_domain: string | null;
  domain_health: 'healthy' | 'at_risk' | 'unknown';
  complaint_rate_pct: number;
  last_send_at: string | null;
  pending_campaigns: number;
}

export interface EmailHubAlert {
  severity: 'info' | 'warn' | 'danger';
  message: string;
  link: string;
  link_label: string;
}

export interface EmailHubResponse {
  ok: boolean;
  schema_ready: boolean;
  summary: EmailHubSummary;
  clients: EmailHubClientRow[];
  pending_approvals: Array<{
    campaign_id: string;
    client_id: string;
    client_name: string;
    campaign_name: string;
    scheduled_at: string | null;
    audience_count: number | null;
  }>;
  send_calendar: Array<{
    campaign_id: string;
    client_name: string;
    campaign_name: string;
    scheduled_at: string;
    status: string;
  }>;
  alerts: EmailHubAlert[];
  filters: { client_id?: string | null; days: number; domain?: string | null };
}

export interface EmailGovernanceRule {
  id: string;
  scope: string;
  client_id: string | null;
  rule_type: string;
  config_json: Record<string, unknown>;
  priority: number;
  enabled: boolean;
  created_at: string;
}

export interface EmailGovernanceResponse {
  ok: boolean;
  read_only: boolean;
  schema_ready: boolean;
  rules: EmailGovernanceRule[];
  audit_log: Array<{
    id: number;
    client_id: string | null;
    actor: string;
    action: string;
    entity_type: string;
    entity_id: string | null;
    created_at: string;
  }>;
  filters: { scope?: string | null };
}

export async function fetchEmailHub(
  token: string,
  params?: { client_id?: string; days?: number; domain?: string },
): Promise<EmailHubResponse> {
  const qs = new URLSearchParams();
  if (params?.client_id) qs.set('client_id', params.client_id);
  if (params?.days != null) qs.set('days', String(params.days));
  if (params?.domain) qs.set('domain', params.domain);
  const suffix = qs.toString() ? `?${qs.toString()}` : '';
  return agencyFetch(token, `/api/v1/email/hub${suffix}`);
}

export async function fetchEmailGovernance(
  token: string,
  params?: { scope?: string },
): Promise<EmailGovernanceResponse> {
  const qs = new URLSearchParams();
  if (params?.scope) qs.set('scope', params.scope);
  const suffix = qs.toString() ? `?${qs.toString()}` : '';
  return agencyFetch(token, `/api/v1/email/governance${suffix}`);
}

export interface EmailClientListRow {
  client_id: string;
  client_code: string;
  client_name: string;
  client_status: string;
  workspace_id: string | null;
  workspace_name: string | null;
  esp_provider: string | null;
  contact_count: number;
  has_workspace: boolean;
}

export interface EmailWorkspaceRow {
  id: string;
  client_id: string;
  client_code: string;
  client_name: string;
  name: string;
  default_from_name: string | null;
  default_from_email: string | null;
  default_reply_to: string | null;
  esp_provider: string;
  daily_send_cap: number;
  frequency_cap_7d: number;
  timezone: string;
  status: string;
  contact_count: number;
  subscriber_count: number;
  suppressed_count: number;
  created_at: string;
  updated_at: string;
}

export interface EmailContactRow {
  id: string;
  client_id: string;
  client_name: string;
  email: string;
  first_name: string | null;
  last_name: string | null;
  lifecycle_stage: string | null;
  consent_status: string | null;
  suppressed: boolean;
  created_at: string;
  updated_at: string;
}

export interface EmailConsentRow {
  id: string;
  client_id: string;
  contact_id: string;
  contact_email: string;
  topic: string;
  status: string;
  source: string;
  consent_version: string | null;
  recorded_at: string;
  recorded_by: string | null;
}

export interface EmailSuppressionRow {
  id: string;
  client_id: string | null;
  client_name: string | null;
  email_normalized: string;
  reason: string;
  scope: string;
  expires_at: string | null;
  created_at: string;
  created_by: string | null;
}

export interface EmailPaged<T> {
  ok: boolean;
  items: T[];
  total: number;
  limit: number;
  offset: number;
}

export async function fetchEmailClients(
  token: string,
  params?: { q?: string; has_workspace?: boolean; limit?: number; offset?: number },
): Promise<EmailPaged<EmailClientListRow>> {
  const qs = new URLSearchParams();
  if (params?.q) qs.set('q', params.q);
  if (params?.has_workspace != null) qs.set('has_workspace', params.has_workspace ? '1' : '0');
  if (params?.limit != null) qs.set('limit', String(params.limit));
  if (params?.offset != null) qs.set('offset', String(params.offset));
  const suffix = qs.toString() ? `?${qs.toString()}` : '';
  return agencyFetch(token, `/api/v1/email/clients${suffix}`);
}

export async function fetchEmailWorkspaces(
  token: string,
  params?: { client_id?: string; limit?: number; offset?: number },
): Promise<EmailPaged<EmailWorkspaceRow>> {
  const qs = new URLSearchParams();
  if (params?.client_id) qs.set('client_id', params.client_id);
  if (params?.limit != null) qs.set('limit', String(params.limit));
  if (params?.offset != null) qs.set('offset', String(params.offset));
  const suffix = qs.toString() ? `?${qs.toString()}` : '';
  return agencyFetch(token, `/api/v1/email/workspaces${suffix}`);
}

export async function createEmailWorkspace(
  token: string,
  body: {
    client_id: string;
    name?: string;
    default_from_name?: string;
    default_from_email?: string;
    default_reply_to?: string;
    esp_provider?: string;
    daily_send_cap?: number;
    frequency_cap_7d?: number;
    timezone?: string;
  },
): Promise<EmailWorkspaceRow> {
  const res = await fetch(`${API_BASE}/api/v1/email/workspaces`, {
    method: 'POST',
    headers: {
      Authorization: `Bearer ${token}`,
      'Content-Type': 'application/json',
    },
    body: JSON.stringify(body),
  });
  const out = await parseJson<EmailWorkspaceRow & { error?: string }>(res);
  if (!res.ok) throw new ApiError(out.error ?? 'Create workspace failed', res.status);
  return out;
}

export async function patchEmailWorkspace(
  token: string,
  workspaceId: string,
  patch: Record<string, unknown>,
): Promise<EmailWorkspaceRow> {
  const res = await fetch(`${API_BASE}/api/v1/email/workspaces/${workspaceId}`, {
    method: 'PATCH',
    headers: {
      Authorization: `Bearer ${token}`,
      'Content-Type': 'application/json',
    },
    body: JSON.stringify(patch),
  });
  const out = await parseJson<EmailWorkspaceRow & { error?: string }>(res);
  if (!res.ok) throw new ApiError(out.error ?? 'Update workspace failed', res.status);
  return out;
}

export async function fetchEmailContacts(
  token: string,
  params?: { client_id?: string; q?: string; limit?: number; offset?: number },
): Promise<EmailPaged<EmailContactRow>> {
  const qs = new URLSearchParams();
  if (params?.client_id) qs.set('client_id', params.client_id);
  if (params?.q) qs.set('q', params.q);
  if (params?.limit != null) qs.set('limit', String(params.limit));
  if (params?.offset != null) qs.set('offset', String(params.offset));
  const suffix = qs.toString() ? `?${qs.toString()}` : '';
  return agencyFetch(token, `/api/v1/email/contacts${suffix}`);
}

export async function importEmailContacts(
  token: string,
  body: {
    client_id: string;
    rows: Array<{ email: string; first_name?: string; last_name?: string; lifecycle_stage?: string }>;
  },
): Promise<{ ok: boolean; created: number; updated: number; skipped: number; errors: string[] }> {
  const res = await fetch(`${API_BASE}/api/v1/email/contacts/import`, {
    method: 'POST',
    headers: {
      Authorization: `Bearer ${token}`,
      'Content-Type': 'application/json',
    },
    body: JSON.stringify(body),
  });
  const out = await parseJson<{ ok: boolean; created: number; updated: number; skipped: number; errors: string[]; error?: string }>(res);
  if (!res.ok) throw new ApiError(out.error ?? 'Import failed', res.status);
  return out;
}

export async function fetchEmailConsent(
  token: string,
  params?: { client_id?: string; contact_id?: string; topic?: string; limit?: number; offset?: number },
): Promise<EmailPaged<EmailConsentRow>> {
  const qs = new URLSearchParams();
  if (params?.client_id) qs.set('client_id', params.client_id);
  if (params?.contact_id) qs.set('contact_id', params.contact_id);
  if (params?.topic) qs.set('topic', params.topic);
  if (params?.limit != null) qs.set('limit', String(params.limit));
  if (params?.offset != null) qs.set('offset', String(params.offset));
  const suffix = qs.toString() ? `?${qs.toString()}` : '';
  return agencyFetch(token, `/api/v1/email/consent${suffix}`);
}

export async function recordEmailConsent(
  token: string,
  body: {
    client_id: string;
    contact_id?: string;
    email?: string;
    topic?: string;
    status: string;
    source?: string;
    consent_version?: string;
  },
): Promise<{ ok: boolean; consent_id: string; contact_id: string; preference_token?: string }> {
  const res = await fetch(`${API_BASE}/api/v1/email/consent`, {
    method: 'POST',
    headers: {
      Authorization: `Bearer ${token}`,
      'Content-Type': 'application/json',
    },
    body: JSON.stringify(body),
  });
  const out = await parseJson<{ ok: boolean; consent_id: string; contact_id: string; preference_token?: string; error?: string }>(res);
  if (!res.ok) throw new ApiError(out.error ?? 'Record consent failed', res.status);
  return out;
}

export async function fetchEmailSuppression(
  token: string,
  params?: { client_id?: string; q?: string; limit?: number; offset?: number },
): Promise<EmailPaged<EmailSuppressionRow>> {
  const qs = new URLSearchParams();
  if (params?.client_id) qs.set('client_id', params.client_id);
  if (params?.q) qs.set('q', params.q);
  if (params?.limit != null) qs.set('limit', String(params.limit));
  if (params?.offset != null) qs.set('offset', String(params.offset));
  const suffix = qs.toString() ? `?${qs.toString()}` : '';
  return agencyFetch(token, `/api/v1/email/suppression${suffix}`);
}

export async function addEmailSuppression(
  token: string,
  body: { client_id?: string; email: string; reason: string; scope?: string },
): Promise<{ ok: boolean; id: string }> {
  const res = await fetch(`${API_BASE}/api/v1/email/suppression`, {
    method: 'POST',
    headers: {
      Authorization: `Bearer ${token}`,
      'Content-Type': 'application/json',
    },
    body: JSON.stringify(body),
  });
  const out = await parseJson<{ ok: boolean; id: string; error?: string }>(res);
  if (!res.ok) throw new ApiError(out.error ?? 'Add suppression failed', res.status);
  return out;
}

export async function fetchPublicEmailPreferences(token: string) {
  const res = await fetch(`${API_BASE}/api/v1/email/public/preferences/${encodeURIComponent(token)}`);
  return parseJson<{
    ok: boolean;
    client_name: string;
    email: string;
    topics: Array<{ topic: string; status: string }>;
    token_purpose: string;
    error?: string;
  }>(res);
}

export async function updatePublicEmailPreferences(
  token: string,
  body: { marketing?: boolean; topics?: Array<{ topic: string; opted_in: boolean }> },
) {
  const res = await fetch(`${API_BASE}/api/v1/email/public/preferences/${encodeURIComponent(token)}`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
  });
  return parseJson<{ ok: boolean; error?: string }>(res);
}

export async function publicEmailUnsubscribe(token: string) {
  const res = await fetch(`${API_BASE}/api/v1/email/public/unsubscribe/${encodeURIComponent(token)}`, {
    method: 'POST',
  });
  return parseJson<{ ok: boolean; email: string; error?: string }>(res);
}

export async function publicEmailConfirm(token: string) {
  const res = await fetch(`${API_BASE}/api/v1/email/public/confirm/${encodeURIComponent(token)}`, {
    method: 'POST',
  });
  return parseJson<{ ok: boolean; email: string; error?: string }>(res);
}

export interface EmailSegmentRow {
  id: string;
  client_id: string;
  client_name: string;
  name: string;
  segment_type: string;
  definition_json?: Record<string, unknown>;
  member_count: number;
  last_computed_at: string | null;
  status: string;
}

export interface EmailSegmentComputeResult {
  ok: boolean;
  segment_id: string;
  member_count: number;
  excluded_suppression: number;
  excluded_consent: number;
}

export interface EmailTemplateRow {
  id: string;
  client_id: string;
  client_name: string;
  name: string;
  subject_template: string;
  html_body: string;
  text_body: string | null;
  version: number;
  status: string;
}

export interface EmailCampaignRow {
  id: string;
  client_id: string;
  client_name: string;
  name: string;
  segment_id: string | null;
  segment_name: string | null;
  template_id: string;
  template_name: string;
  status: string;
  scheduled_at: string | null;
  audience_count: number | null;
}

export interface EmailPreflightCheck {
  id: string;
  label: string;
  status: 'pass' | 'warn' | 'fail';
  message: string;
}

async function emailPost<T>(token: string, path: string, body?: unknown): Promise<T> {
  const res = await fetch(`${API_BASE}${path}`, {
    method: 'POST',
    headers: { Authorization: `Bearer ${token}`, 'Content-Type': 'application/json' },
    body: body ? JSON.stringify(body) : undefined,
  });
  const out = await parseJson<T & { error?: string }>(res);
  if (!res.ok) throw new ApiError((out as { error?: string }).error ?? 'Request failed', res.status);
  return out;
}

async function emailPatch<T>(token: string, path: string, body: unknown): Promise<T> {
  const res = await fetch(`${API_BASE}${path}`, {
    method: 'PATCH',
    headers: { Authorization: `Bearer ${token}`, 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
  });
  const out = await parseJson<T & { error?: string }>(res);
  if (!res.ok) throw new ApiError((out as { error?: string }).error ?? 'Request failed', res.status);
  return out;
}

export async function fetchEmailSegments(
  token: string,
  params?: { client_id?: string; limit?: number },
): Promise<EmailPaged<EmailSegmentRow>> {
  const qs = new URLSearchParams();
  if (params?.client_id) qs.set('client_id', params.client_id);
  if (params?.limit != null) qs.set('limit', String(params.limit));
  const suffix = qs.toString() ? `?${qs.toString()}` : '';
  return agencyFetch(token, `/api/v1/email/segments${suffix}`);
}

export async function createEmailSegment(
  token: string,
  body: { client_id: string; name: string; segment_type?: string; definition_json?: Record<string, unknown> },
): Promise<EmailSegmentRow> {
  return emailPost(token, '/api/v1/email/segments', body);
}

export async function fetchEmailSegment(token: string, segmentId: string): Promise<EmailSegmentRow> {
  return agencyFetch(token, `/api/v1/email/segments/${segmentId}`);
}

export async function patchEmailSegment(
  token: string,
  segmentId: string,
  body: { name?: string; segment_type?: string; definition_json?: Record<string, unknown> },
): Promise<EmailSegmentRow> {
  const res = await fetch(`${API_BASE}/api/v1/email/segments/${encodeURIComponent(segmentId)}`, {
    method: 'PATCH',
    headers: {
      Authorization: `Bearer ${token}`,
      'Content-Type': 'application/json',
    },
    body: JSON.stringify(body),
  });
  const out = await parseJson<EmailSegmentRow & { error?: string }>(res);
  if (!res.ok) throw new ApiError(out.error ?? 'Update segment failed', res.status);
  return out;
}

export async function computeEmailSegment(
  token: string,
  segmentId: string,
): Promise<EmailSegmentComputeResult> {
  return emailPost(token, `/api/v1/email/segments/${segmentId}/compute`, {});
}

export async function fetchEmailTemplates(
  token: string,
  params?: { client_id?: string; limit?: number },
): Promise<EmailPaged<EmailTemplateRow>> {
  const qs = new URLSearchParams();
  if (params?.client_id) qs.set('client_id', params.client_id);
  if (params?.limit != null) qs.set('limit', String(params.limit));
  const suffix = qs.toString() ? `?${qs.toString()}` : '';
  return agencyFetch(token, `/api/v1/email/templates${suffix}`);
}

export async function createEmailTemplate(
  token: string,
  body: { client_id: string; name: string; subject_template: string; html_body: string; text_body?: string },
): Promise<EmailTemplateRow> {
  return emailPost(token, '/api/v1/email/templates', body);
}

export async function fetchEmailTemplate(token: string, id: string): Promise<EmailTemplateRow> {
  return agencyFetch(token, `/api/v1/email/templates/${id}`);
}

export async function patchEmailTemplate(
  token: string,
  id: string,
  patch: Partial<{ name: string; subject_template: string; html_body: string; text_body: string }>,
): Promise<EmailTemplateRow> {
  const res = await fetch(`${API_BASE}/api/v1/email/templates/${id}`, {
    method: 'PATCH',
    headers: { Authorization: `Bearer ${token}`, 'Content-Type': 'application/json' },
    body: JSON.stringify(patch),
  });
  const out = await parseJson<EmailTemplateRow & { error?: string }>(res);
  if (!res.ok) throw new ApiError(out.error ?? 'Update template failed', res.status);
  return out;
}

export async function preflightEmailTemplate(
  token: string,
  id: string,
): Promise<{ ok: boolean; passed: boolean; checks: EmailPreflightCheck[] }> {
  return emailPost(token, `/api/v1/email/templates/${id}/preflight`, {});
}

export async function fetchEmailCampaigns(
  token: string,
  params?: { client_id?: string; status?: string; limit?: number },
): Promise<EmailPaged<EmailCampaignRow>> {
  const qs = new URLSearchParams();
  if (params?.client_id) qs.set('client_id', params.client_id);
  if (params?.status) qs.set('status', params.status);
  if (params?.limit != null) qs.set('limit', String(params.limit));
  const suffix = qs.toString() ? `?${qs.toString()}` : '';
  return agencyFetch(token, `/api/v1/email/campaigns${suffix}`);
}

export async function createEmailCampaign(
  token: string,
  body: { client_id: string; name: string; template_id: string; segment_id?: string },
): Promise<EmailCampaignRow> {
  return emailPost(token, '/api/v1/email/campaigns', body);
}

export async function fetchEmailCampaign(token: string, id: string): Promise<EmailCampaignRow> {
  return agencyFetch(token, `/api/v1/email/campaigns/${id}`);
}

export async function preflightEmailCampaign(
  token: string,
  id: string,
): Promise<{ ok: boolean; passed: boolean; checks: EmailPreflightCheck[] }> {
  return emailPost(token, `/api/v1/email/campaigns/${id}/preflight`, {});
}

export async function submitEmailCampaign(token: string, id: string): Promise<EmailCampaignRow> {
  return emailPost(token, `/api/v1/email/campaigns/${id}/submit`, {});
}

export async function approveEmailCampaign(
  token: string,
  id: string,
  body?: { scheduled_at?: string; note?: string },
): Promise<EmailCampaignRow & { prepare_job_id?: string | null }> {
  return emailPost(token, `/api/v1/email/campaigns/${id}/approve`, body ?? {});
}

export async function scheduleEmailCampaign(
  token: string,
  id: string,
  scheduledAt: string,
): Promise<EmailCampaignRow> {
  return emailPost(token, `/api/v1/email/campaigns/${id}/schedule`, { scheduled_at: scheduledAt });
}

export interface EmailJourneyRow {
  id: string;
  client_id: string;
  client_name: string;
  name: string;
  trigger_type: string;
  graph_json: Record<string, unknown>;
  entry_segment_id: string | null;
  entry_segment_name: string | null;
  status: string;
  enrolled_count: number;
  steps?: Array<{
    id: string;
    step_key: string;
    step_type: string;
    config_json: Record<string, unknown>;
    sort_order: number;
  }>;
}

export interface EmailDeliverabilityDomainRow {
  id: string;
  client_id: string;
  client_name: string;
  domain: string;
  spf_status: string;
  dkim_status: string;
  dmarc_status: string;
  last_checked_at: string | null;
  warm_up_stage: number;
  status: string;
}

export interface EmailReportsSummary {
  ok: boolean;
  days: number;
  sent: number;
  delivered: number;
  opens: number;
  clicks: number;
  unsubscribes: number;
  open_rate_pct: number;
  click_rate_pct: number;
  revenue_attrib: number;
}

export interface EmailDeliverabilityReport {
  ok: boolean;
  days: number;
  domains: EmailDeliverabilityDomainRow[];
  bounce_rate_pct: number;
  complaint_rate_pct: number;
  paused_domains: number;
}

export interface EmailEngagementPoint {
  date: string;
  opens: number;
  clicks: number;
}

export async function fetchEmailJourneys(
  token: string,
  params?: { client_id?: string; status?: string; limit?: number },
): Promise<EmailPaged<EmailJourneyRow>> {
  const qs = new URLSearchParams();
  if (params?.client_id) qs.set('client_id', params.client_id);
  if (params?.status) qs.set('status', params.status);
  if (params?.limit != null) qs.set('limit', String(params.limit));
  const suffix = qs.toString() ? `?${qs.toString()}` : '';
  return agencyFetch(token, `/api/v1/email/journeys${suffix}`);
}

export async function createEmailJourney(
  token: string,
  body: {
    client_id: string;
    name: string;
    entry_segment_id?: string;
    trigger_type?: string;
  },
): Promise<EmailJourneyRow> {
  return emailPost(token, '/api/v1/email/journeys', body);
}

export async function fetchEmailJourney(token: string, id: string): Promise<EmailJourneyRow> {
  return agencyFetch(token, `/api/v1/email/journeys/${id}`);
}

export async function activateEmailJourney(token: string, id: string): Promise<EmailJourneyRow> {
  return emailPost(token, `/api/v1/email/journeys/${id}/activate`, {});
}

export async function patchEmailJourney(
  token: string,
  id: string,
  body: { name?: string; graph_json?: Record<string, unknown>; entry_segment_id?: string | null; status?: string },
): Promise<EmailJourneyRow> {
  return emailPatch(token, `/api/v1/email/journeys/${id}`, body);
}

export interface EmailExperimentVariantRow {
  id: string;
  experiment_id: string;
  variant_key: string;
  label: string;
  config_json: Record<string, unknown>;
  split_pct: number;
  created_at: string;
}

export interface EmailExperimentRow {
  id: string;
  client_id: string;
  client_name: string;
  campaign_id: string | null;
  campaign_name: string | null;
  name: string;
  experiment_type: string;
  hypothesis: string | null;
  status: string;
  winner_variant_key: string | null;
  config_json: Record<string, unknown>;
  started_at: string | null;
  ended_at: string | null;
  created_by: string | null;
  created_at: string;
  updated_at: string;
  variants?: EmailExperimentVariantRow[];
}

export async function fetchCampaignExperiment(
  token: string,
  campaignId: string,
): Promise<EmailExperimentRow | null> {
  return agencyFetch(token, `/api/v1/email/campaigns/${campaignId}/experiment`);
}

export async function createEmailExperiment(
  token: string,
  body: {
    client_id: string;
    campaign_id: string;
    name: string;
    hypothesis?: string;
    variants: Array<{ variant_key: string; label: string; subject?: string; split_pct?: number }>;
  },
): Promise<EmailExperimentRow> {
  return emailPost(token, '/api/v1/email/experiments', body);
}

export async function startEmailExperiment(token: string, id: string): Promise<EmailExperimentRow> {
  return emailPost(token, `/api/v1/email/experiments/${id}/start`, {});
}

export async function rollupEmailExperiment(
  token: string,
  id: string,
): Promise<{ ok: boolean; experiment_id: string; job_id?: string | null }> {
  return emailPost(token, `/api/v1/email/experiments/${id}/rollup`, {});
}

export async function declareEmailExperimentWinner(
  token: string,
  id: string,
  variantKey: string,
  rationale?: string,
): Promise<EmailExperimentRow> {
  return emailPost(token, `/api/v1/email/experiments/${id}/declare-winner`, {
    variant_key: variantKey,
    rationale,
  });
}

export async function fetchEmailDeliverabilityDomains(
  token: string,
  params?: { client_id?: string; limit?: number },
): Promise<EmailPaged<EmailDeliverabilityDomainRow>> {
  const qs = new URLSearchParams();
  if (params?.client_id) qs.set('client_id', params.client_id);
  if (params?.limit != null) qs.set('limit', String(params.limit));
  const suffix = qs.toString() ? `?${qs.toString()}` : '';
  return agencyFetch(token, `/api/v1/email/deliverability/domains${suffix}`);
}

export async function registerEmailDomain(
  token: string,
  body: { client_id: string; domain: string },
): Promise<EmailDeliverabilityDomainRow> {
  return emailPost(token, '/api/v1/email/deliverability/domains', body);
}

export async function verifyEmailDomain(token: string, id: string): Promise<EmailDeliverabilityDomainRow> {
  return emailPost(token, `/api/v1/email/deliverability/domains/${id}/verify`, {});
}

export async function pauseEmailDomain(token: string, id: string): Promise<EmailDeliverabilityDomainRow> {
  return emailPost(token, `/api/v1/email/deliverability/domains/${id}/pause`, {});
}

export async function fetchEmailReportsSummary(
  token: string,
  params?: { client_id?: string; days?: number },
): Promise<EmailReportsSummary> {
  const qs = new URLSearchParams();
  if (params?.client_id) qs.set('client_id', params.client_id);
  if (params?.days != null) qs.set('days', String(params.days));
  const suffix = qs.toString() ? `?${qs.toString()}` : '';
  return agencyFetch(token, `/api/v1/email/reports/summary${suffix}`);
}

export async function fetchEmailDeliverabilityReport(
  token: string,
  params?: { client_id?: string; days?: number },
): Promise<EmailDeliverabilityReport> {
  const qs = new URLSearchParams();
  if (params?.client_id) qs.set('client_id', params.client_id);
  if (params?.days != null) qs.set('days', String(params.days));
  const suffix = qs.toString() ? `?${qs.toString()}` : '';
  return agencyFetch(token, `/api/v1/email/reports/deliverability${suffix}`);
}

export async function fetchEmailEngagementSeries(
  token: string,
  params?: { client_id?: string; days?: number },
): Promise<{ ok: boolean; points: EmailEngagementPoint[] }> {
  const qs = new URLSearchParams();
  if (params?.client_id) qs.set('client_id', params.client_id);
  if (params?.days != null) qs.set('days', String(params.days));
  const suffix = qs.toString() ? `?${qs.toString()}` : '';
  return agencyFetch(token, `/api/v1/email/reports/engagement${suffix}`);
}

export interface EmailReportScheduleRow {
  id: string;
  client_id: string;
  client_name: string;
  report_type: string;
  cadence: string;
  day_of_week: number;
  day_of_month: number;
  recipient_emails: string[];
  cc_emails: string[];
  bcc_emails: string[];
  active: boolean;
  next_run_at: string | null;
  last_sent_at: string | null;
}

export async function exportEmailClickhouse(
  token: string,
  params?: { fact_date?: string; client_id?: string },
): Promise<{ ok: boolean; job_id: string | null; mode: string }> {
  const qs = new URLSearchParams();
  if (params?.fact_date) qs.set('fact_date', params.fact_date);
  if (params?.client_id) qs.set('client_id', params.client_id);
  const suffix = qs.toString() ? `?${qs.toString()}` : '';
  return emailPost(token, `/api/v1/email/reports/export-clickhouse${suffix}`, {});
}

export async function fetchEmailReportSchedules(
  token: string,
  clientId: string,
): Promise<{ ok: boolean; items: EmailReportScheduleRow[]; total: number }> {
  const qs = new URLSearchParams({ client_id: clientId });
  return agencyFetch(token, `/api/v1/email/reports/schedules?${qs.toString()}`);
}

export async function createEmailReportSchedule(
  token: string,
  body: {
    client_id: string;
    report_type?: string;
    cadence?: string;
    day_of_week?: number;
    recipient_emails?: string[];
  },
): Promise<EmailReportScheduleRow> {
  return emailPost(token, '/api/v1/email/reports/schedules', body);
}

export async function runEmailReportSchedule(
  token: string,
  scheduleId: string,
): Promise<{ ok: boolean; job_id: string | null }> {
  return emailPost(token, `/api/v1/email/reports/schedules/${scheduleId}/run`, {});
}
