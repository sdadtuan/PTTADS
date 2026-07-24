import type {
  FacebookHubCampaignsResponse,
  FacebookHubQuery,
  MetaAlertAckResponse,
  MetaAlertsListResponse,
  MetaHubMapSuggestBody,
  MetaHubMapSuggestResponse,
  MetaSyncStatusResponse,
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
