export const API_BASE =
  (process.env.NEXT_PUBLIC_PTT_API_URL ?? 'http://127.0.0.1:3000').replace(/\/$/, '');

export interface PortalUser {
  id: string;
  email: string;
  client_id: string;
  role: string;
}

export interface PerformanceRow {
  performance_date?: string | null;
  channel?: string | null;
  external_campaign_id: string | null;
  external_campaign_name: string | null;
  spend: number;
  currency: string;
  impressions: number;
  clicks: number;
  leads_crm: number;
  leads_platform: number;
  cpl: number | null;
  target_cpl_vnd: number | null;
  cpl_delta_vnd: number | null;
  cpl_delta_pct: number | null;
  conversion_value: number;
  roas: number | null;
  roas_stub: boolean;
  hub_mapped: boolean;
  synced_at: string | null;
}

export interface PerformanceSummary {
  row_count: number;
  total_spend: number;
  total_leads_crm: number;
  avg_cpl: number | null;
  total_conversion_value: number;
  avg_roas: number | null;
  roas_stub: boolean;
  latest_performance_date: string | null;
  latest_synced_at: string | null;
  campaigns_tracked: number;
  mapped_rows: number;
  over_target_rows: number;
}

export type PerformanceChannel = 'meta' | 'google';

export interface PerformanceListResponse {
  ok: boolean;
  client_id: string;
  date_from: string;
  date_to: string;
  group_by: 'day' | 'campaign';
  channel?: PerformanceChannel | null;
  rows: PerformanceRow[];
  summary: PerformanceSummary;
  error?: string;
}

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
}

export interface LoginResponse {
  access_token: string;
  token_type: string;
  expires_in: number;
  user: PortalUser;
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

export async function portalLogin(email: string, password: string): Promise<LoginResponse> {
  const res = await fetch(`${API_BASE}/api/v1/portal/auth/login`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ email, password }),
  });
  const body = await parseJson<LoginResponse & { error?: string; message?: string }>(res);
  if (!res.ok) {
    throw new ApiError(body.error ?? body.message ?? 'Login failed', res.status);
  }
  return body;
}

export async function portalMe(token: string): Promise<PortalUser> {
  const res = await fetch(`${API_BASE}/api/v1/portal/auth/me`, {
    headers: { Authorization: `Bearer ${token}` },
    cache: 'no-store',
  });
  const body = await parseJson<PortalUser & { error?: string }>(res);
  if (!res.ok) {
    throw new ApiError(body.error ?? 'Unauthorized', res.status);
  }
  return body;
}

export async function fetchNestHealth(): Promise<Record<string, unknown>> {
  const res = await fetch(`${API_BASE}/health`, { cache: 'no-store' });
  return parseJson(res);
}

export async function fetchPerformance(
  token: string,
  params?: { from?: string; to?: string; group_by?: 'day' | 'campaign'; channel?: PerformanceChannel },
): Promise<PerformanceListResponse> {
  const qs = new URLSearchParams();
  if (params?.from) qs.set('from', params.from);
  if (params?.to) qs.set('to', params.to);
  if (params?.group_by) qs.set('group_by', params.group_by);
  if (params?.channel) qs.set('channel', params.channel);
  const suffix = qs.toString() ? `?${qs.toString()}` : '';
  const res = await fetch(`${API_BASE}/api/v1/performance${suffix}`, {
    headers: { Authorization: `Bearer ${token}` },
    cache: 'no-store',
  });
  const body = await parseJson<PerformanceListResponse & { error?: string; message?: string }>(res);
  if (!res.ok) {
    throw new ApiError(body.error ?? body.message ?? 'Performance fetch failed', res.status);
  }
  return body;
}

export async function fetchPendingCreatives(token: string): Promise<CreativePendingResponse> {
  const res = await fetch(`${API_BASE}/api/v1/creatives/pending`, {
    headers: { Authorization: `Bearer ${token}` },
    cache: 'no-store',
  });
  const body = await parseJson<CreativePendingResponse & { error?: string; message?: string }>(res);
  if (!res.ok) {
    throw new ApiError(body.error ?? body.message ?? 'Creative inbox fetch failed', res.status);
  }
  return body;
}

export async function approveCreative(
  token: string,
  creativeId: string,
): Promise<CreativeDecisionResponse> {
  const res = await fetch(`${API_BASE}/api/v1/creatives/${creativeId}/approve`, {
    method: 'POST',
    headers: { Authorization: `Bearer ${token}` },
  });
  const body = await parseJson<CreativeDecisionResponse & { error?: string; message?: string }>(res);
  if (!res.ok) {
    throw new ApiError(body.error ?? body.message ?? 'Approve failed', res.status);
  }
  return body;
}

export async function rejectCreative(
  token: string,
  creativeId: string,
  note?: string,
): Promise<CreativeDecisionResponse> {
  const res = await fetch(`${API_BASE}/api/v1/creatives/${creativeId}/reject`, {
    method: 'POST',
    headers: {
      Authorization: `Bearer ${token}`,
      'Content-Type': 'application/json',
    },
    body: JSON.stringify({ note: note?.trim() || undefined }),
  });
  const body = await parseJson<CreativeDecisionResponse & { error?: string; message?: string }>(res);
  if (!res.ok) {
    throw new ApiError(body.error ?? body.message ?? 'Reject failed', res.status);
  }
  return body;
}
