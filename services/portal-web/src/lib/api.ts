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

export interface PerformanceDataFreshness {
  through_date: string;
  synced_at: string | null;
}

export interface PerformanceListResponse {
  ok: boolean;
  client_id: string;
  date_from: string;
  date_to: string;
  group_by: 'day' | 'campaign';
  channel?: PerformanceChannel | null;
  rows: PerformanceRow[];
  summary: PerformanceSummary;
  attribution_model?: 'last_touch_crm';
  unmapped_spend_pct?: number;
  spend_source?: 'meta_api';
  data_freshness?: PerformanceDataFreshness;
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
  refresh_token?: string;
  token_type: string;
  expires_in: number;
  refresh_expires_in?: number;
  user: PortalUser;
}

export interface PortalSettingsResponse {
  ok: boolean;
  client_id: string;
  client_name: string | null;
  display_name: string | null;
  logo_url: string | null;
  am_contact_name: string | null;
  am_contact_email: string | null;
  accent_color: string | null;
  updated_at: string | null;
  table_ready: boolean;
}

export interface CreativeHistoryResponse {
  ok: boolean;
  client_id: string;
  days: number;
  count: number;
  rows: CreativeRow[];
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

export function isTenantArchivedError(err: unknown): boolean {
  if (!(err instanceof ApiError)) return false;
  return err.message === 'tenant_archived' || err.status === 403;
}

export function tenantArchivedMessage(): string {
  return 'Client đã archived — portal không còn truy cập được.';
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

export async function portalRefresh(refreshToken: string): Promise<LoginResponse> {
  const res = await fetch(`${API_BASE}/api/v1/portal/auth/refresh`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ refresh_token: refreshToken }),
  });
  const body = await parseJson<LoginResponse & { error?: string; message?: string }>(res);
  if (!res.ok) {
    throw new ApiError(body.error ?? body.message ?? 'Refresh failed', res.status);
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

export async function fetchCreativeHistory(
  token: string,
  days = 30,
): Promise<CreativeHistoryResponse> {
  const res = await fetch(`${API_BASE}/api/v1/creatives/history?days=${days}`, {
    headers: { Authorization: `Bearer ${token}` },
    cache: 'no-store',
  });
  const body = await parseJson<CreativeHistoryResponse & { error?: string; message?: string }>(res);
  if (!res.ok) {
    throw new ApiError(body.error ?? body.message ?? 'Creative history fetch failed', res.status);
  }
  return body;
}

export async function fetchPendingCreativeCount(token: string): Promise<number> {
  const res = await fetch(`${API_BASE}/api/v1/creatives/pending/count`, {
    headers: { Authorization: `Bearer ${token}` },
    cache: 'no-store',
  });
  const body = await parseJson<{ ok?: boolean; count?: number; error?: string }>(res);
  if (!res.ok) {
    return 0;
  }
  return Number(body.count ?? 0);
}

export async function fetchPortalSettings(token: string): Promise<PortalSettingsResponse> {
  const res = await fetch(`${API_BASE}/api/v1/portal/settings`, {
    headers: { Authorization: `Bearer ${token}` },
    cache: 'no-store',
  });
  const body = await parseJson<PortalSettingsResponse & { error?: string; message?: string }>(res);
  if (!res.ok) {
    throw new ApiError(body.error ?? body.message ?? 'Settings fetch failed', res.status);
  }
  return body;
}

export async function patchPortalSettings(
  token: string,
  input: Partial<
    Pick<
      PortalSettingsResponse,
      'display_name' | 'logo_url' | 'am_contact_name' | 'am_contact_email' | 'accent_color'
    >
  >,
): Promise<PortalSettingsResponse> {
  const res = await fetch(`${API_BASE}/api/v1/portal/settings`, {
    method: 'PATCH',
    headers: {
      Authorization: `Bearer ${token}`,
      'Content-Type': 'application/json',
    },
    body: JSON.stringify(input),
  });
  const body = await parseJson<PortalSettingsResponse & { error?: string; message?: string }>(res);
  if (!res.ok) {
    throw new ApiError(body.error ?? body.message ?? 'Settings update failed', res.status);
  }
  return body;
}

export function performanceExportUrl(params?: {
  from?: string;
  to?: string;
  group_by?: 'day' | 'campaign';
  channel?: PerformanceChannel;
  format?: 'csv' | 'pdf';
}): string {
  const qs = new URLSearchParams();
  if (params?.from) qs.set('from', params.from);
  if (params?.to) qs.set('to', params.to);
  if (params?.group_by) qs.set('group_by', params.group_by);
  if (params?.channel) qs.set('channel', params.channel);
  const suffix = qs.toString() ? `?${qs.toString()}` : '';
  const ext = params?.format === 'pdf' ? 'export.pdf' : 'export.csv';
  return `${API_BASE}/api/v1/performance/${ext}${suffix}`;
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

export interface PortalSeoSummaryResponse {
  seo_enabled: boolean;
  customer_id?: number;
  pending_client_review?: number;
  executive?: Record<string, unknown>;
  error?: string;
}

export interface PortalSeoWidgetMetric {
  label: string;
  value: unknown;
  unit?: string;
  sparkline?: number[];
}

export interface PortalSeoWidgetsResponse {
  ok: boolean;
  customer_id: number;
  widgets: Record<string, PortalSeoWidgetMetric>;
}

export type PortalSeoReportType = 'executive' | 'seo' | 'aeo' | 'technical' | 'content';

export interface PortalSeoExecutiveReportResponse {
  ok: boolean;
  customer_id: number;
  dashboard_type: PortalSeoReportType;
  report: Record<string, unknown>;
  generated_at: string;
}

export async function portalSeoSummary(token: string): Promise<PortalSeoSummaryResponse> {
  const res = await fetch(`${API_BASE}/api/v1/portal/seo/summary`, {
    headers: { Authorization: `Bearer ${token}` },
    cache: 'no-store',
  });
  const body = await parseJson<PortalSeoSummaryResponse & { error?: string; message?: string }>(res);
  if (!res.ok) {
    throw new ApiError(body.error ?? body.message ?? 'SEO summary failed', res.status);
  }
  return body;
}

export async function portalSeoWidgets(token: string): Promise<PortalSeoWidgetsResponse> {
  const res = await fetch(`${API_BASE}/api/v1/portal/seo/widgets`, {
    headers: { Authorization: `Bearer ${token}` },
    cache: 'no-store',
  });
  const body = await parseJson<PortalSeoWidgetsResponse & { error?: string; message?: string }>(res);
  if (!res.ok) {
    throw new ApiError(body.error ?? body.message ?? 'SEO widgets failed', res.status);
  }
  return body;
}

export async function portalSeoExecutiveReport(
  token: string,
  type: PortalSeoReportType = 'executive',
): Promise<PortalSeoExecutiveReportResponse> {
  const qs = type !== 'executive' ? `?type=${encodeURIComponent(type)}` : '';
  const res = await fetch(`${API_BASE}/api/v1/portal/seo/reports/executive${qs}`, {
    headers: { Authorization: `Bearer ${token}` },
    cache: 'no-store',
  });
  const body = await parseJson<PortalSeoExecutiveReportResponse & { error?: string; message?: string }>(res);
  if (!res.ok) {
    throw new ApiError(body.error ?? body.message ?? 'Executive report failed', res.status);
  }
  return body;
}

export async function portalSeoPendingContent(
  token: string,
): Promise<{ ok: boolean; items: Array<{ id: number; title: string; content_type: string }> }> {
  const res = await fetch(`${API_BASE}/api/v1/portal/seo/content/pending`, {
    headers: { Authorization: `Bearer ${token}` },
    cache: 'no-store',
  });
  const body = await parseJson<
    { ok: boolean; items: Array<{ id: number; title: string; content_type: string }> } & {
      error?: string;
      message?: string;
    }
  >(res);
  if (!res.ok) {
    throw new ApiError(body.error ?? body.message ?? 'Pending content failed', res.status);
  }
  return body;
}

export async function portalSeoContentDetail(
  token: string,
  contentId: string,
): Promise<Record<string, unknown>> {
  const res = await fetch(`${API_BASE}/api/v1/portal/seo/content/${encodeURIComponent(contentId)}`, {
    headers: { Authorization: `Bearer ${token}` },
    cache: 'no-store',
  });
  const body = await parseJson<Record<string, unknown> & { error?: string; message?: string }>(res);
  if (!res.ok) {
    throw new ApiError(body.error ?? body.message ?? 'Content detail failed', res.status);
  }
  return body;
}

export async function portalSeoReviewContent(
  token: string,
  contentId: string,
  payload: { approved: boolean; notes?: string },
): Promise<Record<string, unknown>> {
  const res = await fetch(`${API_BASE}/api/v1/portal/seo/content/${encodeURIComponent(contentId)}/review`, {
    method: 'POST',
    headers: {
      Authorization: `Bearer ${token}`,
      'Content-Type': 'application/json',
    },
    body: JSON.stringify(payload),
  });
  const body = await parseJson<Record<string, unknown> & { error?: string; message?: string }>(res);
  if (!res.ok) {
    throw new ApiError(body.error ?? body.message ?? 'Review failed', res.status);
  }
  return body;
}

export interface PortalEmailDashboard {
  ok: boolean;
  email_enabled: boolean;
  client_id: string;
  pending_approvals: number;
  campaigns_sent_28d: number;
  open_rate_pct: number;
  revenue_attrib: number;
  recent_campaigns: Array<{
    id: string;
    name: string;
    status: string;
    audience_count: number | null;
    updated_at: string;
  }>;
}

export interface PortalEmailApprovalRow {
  campaign_id: string;
  name: string;
  audience_count: number | null;
  template_name: string;
  requested_at: string;
  status: string;
}

export interface PortalEmailApprovalPreview {
  ok: boolean;
  campaign_id: string;
  name: string;
  subject_template: string;
  html_body: string;
  audience_count: number | null;
  scheduled_at: string | null;
  template_name: string;
  status: string;
}

export interface PortalEmailCampaignStats {
  ok: boolean;
  campaign_id: string;
  campaign_name: string;
  status: string;
  audience_count: number | null;
  sent: number;
  opens: number;
  clicks: number;
  open_rate_pct: number;
  click_rate_pct: number;
  revenue_attrib: number;
}

export async function portalEmailDashboard(token: string): Promise<PortalEmailDashboard> {
  const res = await fetch(`${API_BASE}/api/v1/portal/email/dashboard`, {
    headers: { Authorization: `Bearer ${token}` },
    cache: 'no-store',
  });
  const body = await parseJson<PortalEmailDashboard & { error?: string; message?: string }>(res);
  if (!res.ok) {
    throw new ApiError(body.error ?? body.message ?? 'Email dashboard failed', res.status);
  }
  return body;
}

export async function portalEmailPendingApprovals(
  token: string,
): Promise<{ ok: boolean; items: PortalEmailApprovalRow[] }> {
  const res = await fetch(`${API_BASE}/api/v1/portal/email/approvals/pending`, {
    headers: { Authorization: `Bearer ${token}` },
    cache: 'no-store',
  });
  const body = await parseJson<
    { ok: boolean; items: PortalEmailApprovalRow[] } & { error?: string; message?: string }
  >(res);
  if (!res.ok) {
    throw new ApiError(body.error ?? body.message ?? 'Pending approvals failed', res.status);
  }
  return body;
}

export async function portalEmailApprovalPreview(
  token: string,
  campaignId: string,
): Promise<PortalEmailApprovalPreview> {
  const res = await fetch(
    `${API_BASE}/api/v1/portal/email/approvals/${encodeURIComponent(campaignId)}/preview`,
    {
      headers: { Authorization: `Bearer ${token}` },
      cache: 'no-store',
    },
  );
  const body = await parseJson<PortalEmailApprovalPreview & { error?: string; message?: string }>(res);
  if (!res.ok) {
    throw new ApiError(body.error ?? body.message ?? 'Approval preview failed', res.status);
  }
  return body;
}

export async function portalEmailApproveCampaign(
  token: string,
  campaignId: string,
): Promise<{ ok: boolean; campaign: { id: string; status: string; name: string } }> {
  const res = await fetch(`${API_BASE}/api/v1/portal/email/approvals/${encodeURIComponent(campaignId)}/approve`, {
    method: 'POST',
    headers: { Authorization: `Bearer ${token}` },
  });
  const body = await parseJson<
    { ok: boolean; campaign: { id: string; status: string; name: string } } & {
      error?: string;
      message?: string;
    }
  >(res);
  if (!res.ok) {
    throw new ApiError(body.error ?? body.message ?? 'Approve failed', res.status);
  }
  return body;
}

export async function portalEmailRejectCampaign(
  token: string,
  campaignId: string,
  note?: string,
): Promise<{ ok: boolean; campaign: { id: string; status: string; name: string } }> {
  const res = await fetch(`${API_BASE}/api/v1/portal/email/approvals/${encodeURIComponent(campaignId)}/reject`, {
    method: 'POST',
    headers: {
      Authorization: `Bearer ${token}`,
      'Content-Type': 'application/json',
    },
    body: JSON.stringify({ note: note?.trim() || undefined }),
  });
  const body = await parseJson<
    { ok: boolean; campaign: { id: string; status: string; name: string } } & {
      error?: string;
      message?: string;
    }
  >(res);
  if (!res.ok) {
    throw new ApiError(body.error ?? body.message ?? 'Reject failed', res.status);
  }
  return body;
}

export async function portalEmailCampaignStats(
  token: string,
  campaignId: string,
): Promise<PortalEmailCampaignStats> {
  const res = await fetch(`${API_BASE}/api/v1/portal/email/campaigns/${encodeURIComponent(campaignId)}/stats`, {
    headers: { Authorization: `Bearer ${token}` },
    cache: 'no-store',
  });
  const body = await parseJson<PortalEmailCampaignStats & { error?: string; message?: string }>(res);
  if (!res.ok) {
    throw new ApiError(body.error ?? body.message ?? 'Campaign stats failed', res.status);
  }
  return body;
}
