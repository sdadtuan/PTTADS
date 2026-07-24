import type {
  CapiEventsListResponse,
  CapiFlushResponse,
  CapiRetryResponse,
  ConversionRuleRow,
  ConversionRulesListResponse,
  CreateConversionRuleBody,
  FacebookHubCampaignsResponse,
  FacebookHubQuery,
  MetaAlertAckResponse,
  MetaAlertsListResponse,
  MetaHubMapSuggestBody,
  MetaHubMapSuggestResponse,
  MetaSyncStatusResponse,
  PatchConversionRuleBody,
  TestPixelResponse,
  TrackingHealthResponse,
} from './types';

const API_BASE = (process.env.NEXT_PUBLIC_PTT_API_URL ?? 'http://127.0.0.1:3000').replace(/\/$/, '');

class MetaApiError extends Error {
  constructor(
    message: string,
    readonly status: number,
  ) {
    super(message);
    this.name = 'MetaApiError';
  }
}

async function parseJson<T>(res: Response): Promise<T> {
  const text = await res.text();
  if (!text) return {} as T;
  try {
    return JSON.parse(text) as T;
  } catch {
    throw new MetaApiError('Invalid JSON response', res.status);
  }
}

function hubQueryString(params: FacebookHubQuery = {}): string {
  const qs = new URLSearchParams();
  if (params.days != null) qs.set('days', String(params.days));
  if (params.date_to) qs.set('date_to', params.date_to);
  if (params.date_from) qs.set('date_from', params.date_from);
  if (params.status) qs.set('status', params.status);
  if (params.client_id) qs.set('client_id', params.client_id);
  if (params.q) qs.set('q', params.q);
  return qs.toString() ? `?${qs.toString()}` : '';
}

async function metaFetch<T>(token: string, path: string): Promise<T> {
  const res = await fetch(`${API_BASE}${path}`, {
    headers: { Authorization: `Bearer ${token}` },
  });
  const body = await parseJson<T & { error?: string; message?: string }>(res);
  if (!res.ok) {
    throw new MetaApiError(body.error ?? body.message ?? `Request failed (${res.status})`, res.status);
  }
  return body;
}

async function metaMutate<T>(token: string, path: string, init: RequestInit): Promise<T> {
  const res = await fetch(`${API_BASE}${path}`, {
    ...init,
    headers: {
      Authorization: `Bearer ${token}`,
      'Content-Type': 'application/json',
      ...(init.headers ?? {}),
    },
  });
  const body = await parseJson<T & { error?: string; message?: string }>(res);
  if (!res.ok) {
    throw new MetaApiError(body.error ?? body.message ?? `Request failed (${res.status})`, res.status);
  }
  return body;
}

export async function fetchFacebookHubCampaigns(
  token: string,
  params: FacebookHubQuery = {},
): Promise<FacebookHubCampaignsResponse> {
  return metaFetch(token, `/api/v1/facebook-ads/hub/campaigns${hubQueryString(params)}`);
}

export async function fetchMetaSyncStatus(
  token: string,
  clientId?: string,
): Promise<MetaSyncStatusResponse> {
  const qs = clientId ? `?client_id=${encodeURIComponent(clientId)}` : '';
  return metaFetch(token, `/api/v1/meta/sync/status${qs}`);
}

export async function fetchMetaAlerts(
  token: string,
  params: { client_id?: string; include_ack?: boolean; limit?: number } = {},
): Promise<MetaAlertsListResponse> {
  const qs = new URLSearchParams();
  if (params.client_id) qs.set('client_id', params.client_id);
  if (params.include_ack) qs.set('include_ack', '1');
  if (params.limit != null) qs.set('limit', String(params.limit));
  const suffix = qs.toString() ? `?${qs.toString()}` : '';
  return metaFetch(token, `/api/v1/meta/alerts${suffix}`);
}

export async function patchMetaAlertAck(token: string, alertId: string): Promise<MetaAlertAckResponse> {
  return metaMutate(token, `/api/v1/meta/alerts/${encodeURIComponent(alertId)}/ack`, {
    method: 'PATCH',
    body: '{}',
  });
}

export async function postMetaHubMapSuggest(
  token: string,
  body: MetaHubMapSuggestBody,
): Promise<MetaHubMapSuggestResponse> {
  return metaMutate(token, '/api/v1/meta/hub-campaign-map/suggest', {
    method: 'POST',
    body: JSON.stringify(body),
  });
}

export async function fetchMetaTrackingHealth(
  token: string,
  params: { client_id?: string; window_days?: number } = {},
): Promise<TrackingHealthResponse> {
  const qs = new URLSearchParams();
  if (params.client_id) qs.set('client_id', params.client_id);
  if (params.window_days != null) qs.set('window_days', String(params.window_days));
  const suffix = qs.toString() ? `?${qs.toString()}` : '';
  return metaFetch(token, `/api/v1/meta/tracking/health${suffix}`);
}

export async function fetchMetaCapiEvents(
  token: string,
  params: {
    client_id?: string;
    status?: string;
    event_name?: string;
    limit?: number;
    offset?: number;
  } = {},
): Promise<CapiEventsListResponse> {
  const qs = new URLSearchParams();
  if (params.client_id) qs.set('client_id', params.client_id);
  if (params.status) qs.set('status', params.status);
  if (params.event_name) qs.set('event_name', params.event_name);
  if (params.limit != null) qs.set('limit', String(params.limit));
  if (params.offset != null) qs.set('offset', String(params.offset));
  const suffix = qs.toString() ? `?${qs.toString()}` : '';
  return metaFetch(token, `/api/v1/meta/capi/events${suffix}`);
}

export async function postMetaCapiRetry(token: string, logId: string): Promise<CapiRetryResponse> {
  return metaMutate(token, `/api/v1/meta/capi/events/${encodeURIComponent(logId)}/retry`, {
    method: 'POST',
    body: '{}',
  });
}

export async function postMetaCapiFlush(
  token: string,
  params: { client_id?: string; limit?: number } = {},
): Promise<CapiFlushResponse> {
  return metaMutate(token, '/api/v1/meta/capi/flush', {
    method: 'POST',
    body: JSON.stringify(params),
  });
}

export async function postMetaTestPixel(
  token: string,
  clientId: string,
  accountId: string,
): Promise<TestPixelResponse> {
  return metaMutate(
    token,
    `/api/v1/clients/${encodeURIComponent(clientId)}/channel-accounts/${encodeURIComponent(accountId)}/test-pixel`,
    { method: 'POST', body: '{}' },
  );
}

export async function fetchMetaConversionRules(
  token: string,
  clientId?: string,
): Promise<ConversionRulesListResponse> {
  const qs = clientId ? `?client_id=${encodeURIComponent(clientId)}` : '';
  return metaFetch(token, `/api/v1/meta/conversion-rules${qs}`);
}

export async function createMetaConversionRule(
  token: string,
  body: CreateConversionRuleBody,
): Promise<{ ok: boolean; rule: ConversionRuleRow }> {
  return metaMutate(token, '/api/v1/meta/conversion-rules', {
    method: 'POST',
    body: JSON.stringify(body),
  });
}

export async function patchMetaConversionRule(
  token: string,
  ruleId: string,
  body: PatchConversionRuleBody,
): Promise<{ ok: boolean; rule: ConversionRuleRow }> {
  return metaMutate(token, `/api/v1/meta/conversion-rules/${encodeURIComponent(ruleId)}`, {
    method: 'PATCH',
    body: JSON.stringify(body),
  });
}

export async function fetchMetaAnomalies(
  token: string,
  params: { client_id?: string; limit?: number; days?: number } = {},
): Promise<import('./types').MetaAnomaliesListResponse> {
  const qs = new URLSearchParams();
  if (params.client_id) qs.set('client_id', params.client_id);
  if (params.limit != null) qs.set('limit', String(params.limit));
  if (params.days != null) qs.set('days', String(params.days));
  const suffix = qs.toString() ? `?${qs.toString()}` : '';
  return metaFetch(token, `/api/v1/meta/anomalies${suffix}`);
}

export async function fetchMetaRoas(
  token: string,
  params: { client_id?: string; from?: string; to?: string; days?: number } = {},
): Promise<import('./types').MetaRoasResponse> {
  const qs = new URLSearchParams();
  if (params.client_id) qs.set('client_id', params.client_id);
  if (params.from) qs.set('from', params.from);
  if (params.to) qs.set('to', params.to);
  if (params.days != null) qs.set('days', String(params.days));
  const suffix = qs.toString() ? `?${qs.toString()}` : '';
  return metaFetch(token, `/api/v1/meta/roas${suffix}`);
}

export async function fetchMetaBudgetRecommendations(
  token: string,
  params: { client_id?: string; days?: number } = {},
): Promise<import('./types').MetaBudgetRecommendationsResponse> {
  const qs = new URLSearchParams();
  if (params.client_id) qs.set('client_id', params.client_id);
  if (params.days != null) qs.set('days', String(params.days));
  const suffix = qs.toString() ? `?${qs.toString()}` : '';
  return metaFetch(token, `/api/v1/meta/budget-recommendations${suffix}`);
}

export async function fetchMetaDailyInsights(
  token: string,
  params: {
    client_id?: string;
    level?: 'campaign' | 'adset' | 'ad';
    from?: string;
    to?: string;
    days?: number;
    limit?: number;
  } = {},
): Promise<import('./types').MetaDailyInsightsResponse> {
  const qs = new URLSearchParams();
  if (params.client_id) qs.set('client_id', params.client_id);
  if (params.level) qs.set('level', params.level);
  if (params.from) qs.set('from', params.from);
  if (params.to) qs.set('to', params.to);
  if (params.days != null) qs.set('days', String(params.days));
  if (params.limit != null) qs.set('limit', String(params.limit));
  const suffix = qs.toString() ? `?${qs.toString()}` : '';
  return metaFetch(token, `/api/v1/meta/insights/daily${suffix}`);
}

export async function fetchMetaStatAnomalies(
  token: string,
  params: { client_id?: string; limit?: number; days?: number } = {},
): Promise<import('./types').MetaAnomaliesListResponse> {
  const qs = new URLSearchParams({ mode: 'stat' });
  if (params.client_id) qs.set('client_id', params.client_id);
  if (params.limit != null) qs.set('limit', String(params.limit));
  if (params.days != null) qs.set('days', String(params.days));
  return metaFetch(token, `/api/v1/meta/anomalies?${qs.toString()}`);
}

export async function fetchMetaForecast(
  token: string,
  params: { client_id?: string; metric?: 'cpl' | 'spend'; days?: number } = {},
): Promise<import('./types').MetaForecastResponse> {
  const qs = new URLSearchParams();
  if (params.client_id) qs.set('client_id', params.client_id);
  if (params.metric) qs.set('metric', params.metric);
  if (params.days != null) qs.set('days', String(params.days));
  const suffix = qs.toString() ? `?${qs.toString()}` : '';
  return metaFetch(token, `/api/v1/meta/forecast${suffix}`);
}

export async function fetchMetaPixels(
  token: string,
  params: { client_id?: string; client_channel_account_id?: string } = {},
): Promise<import('./types').MetaPixelsListResponse> {
  const qs = new URLSearchParams();
  if (params.client_id) qs.set('client_id', params.client_id);
  if (params.client_channel_account_id) qs.set('client_channel_account_id', params.client_channel_account_id);
  const suffix = qs.toString() ? `?${qs.toString()}` : '';
  return metaFetch(token, `/api/v1/meta/pixels${suffix}`);
}

export async function createMetaPixel(
  token: string,
  body: {
    client_channel_account_id: string;
    pixel_id: string;
    label?: string;
    is_primary?: boolean;
    capi_enabled?: boolean;
  },
): Promise<import('./types').MetaPixelMutationResponse> {
  return metaMutate(token, '/api/v1/meta/pixels', {
    method: 'POST',
    body: JSON.stringify(body),
  });
}

export async function patchMetaPixel(
  token: string,
  pixelId: string,
  body: { label?: string; is_primary?: boolean; capi_enabled?: boolean },
): Promise<import('./types').MetaPixelMutationResponse> {
  return metaMutate(token, `/api/v1/meta/pixels/${encodeURIComponent(pixelId)}`, {
    method: 'PATCH',
    body: JSON.stringify(body),
  });
}

export { MetaApiError };
