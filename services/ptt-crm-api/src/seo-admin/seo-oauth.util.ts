import { randomBytes } from 'crypto';
import { encryptAccessToken, vaultConfigured } from '../agency/token-vault.util';

const OAUTH_AUTH = 'https://accounts.google.com/o/oauth2/v2/auth';
const OAUTH_TOKEN = 'https://oauth2.googleapis.com/token';
const GSC_SCOPE = 'https://www.googleapis.com/auth/webmasters.readonly';
const GA4_SCOPE = 'https://www.googleapis.com/auth/analytics.readonly';

export type SeoOAuthProvider = 'gsc' | 'ga4';

function gscClientConfig(): { clientId: string; clientSecret: string; redirectUri: string } {
  const clientId = (
    process.env.PTT_GSC_OAUTH_CLIENT_ID ??
    process.env.PTT_GOOGLE_ADS_CLIENT_ID ??
    ''
  ).trim();
  const clientSecret = (
    process.env.PTT_GSC_OAUTH_CLIENT_SECRET ??
    process.env.PTT_GOOGLE_ADS_CLIENT_SECRET ??
    ''
  ).trim();
  const redirectUri = (
    process.env.PTT_GSC_OAUTH_REDIRECT_URI ??
    process.env.PTT_GOOGLE_OAUTH_REDIRECT_URI ??
    ''
  ).trim();
  if (!clientId || !clientSecret || !redirectUri) {
    throw new Error('missing_gsc_oauth_env');
  }
  return { clientId, clientSecret, redirectUri };
}

function ga4ClientConfig(): { clientId: string; clientSecret: string; redirectUri: string } {
  let redirectUri = (process.env.PTT_GA4_OAUTH_REDIRECT_URI ?? '').trim();
  if (!redirectUri) {
    const gscUri = (process.env.PTT_GSC_OAUTH_REDIRECT_URI ?? '').trim();
    if (gscUri.includes('/gsc/oauth/callback')) {
      redirectUri = gscUri.replace('/gsc/oauth/callback', '/ga4/oauth/callback');
    } else {
      redirectUri = (process.env.PTT_GOOGLE_OAUTH_REDIRECT_URI ?? '').trim();
    }
  }
  const clientId = (
    process.env.PTT_GA4_OAUTH_CLIENT_ID ??
    process.env.PTT_GSC_OAUTH_CLIENT_ID ??
    process.env.PTT_GOOGLE_ADS_CLIENT_ID ??
    ''
  ).trim();
  const clientSecret = (
    process.env.PTT_GA4_OAUTH_CLIENT_SECRET ??
    process.env.PTT_GSC_OAUTH_CLIENT_SECRET ??
    process.env.PTT_GOOGLE_ADS_CLIENT_SECRET ??
    ''
  ).trim();
  if (!clientId || !clientSecret || !redirectUri) {
    throw new Error('missing_ga4_oauth_env');
  }
  return { clientId, clientSecret, redirectUri };
}

function clientConfig(provider: SeoOAuthProvider): { clientId: string; clientSecret: string; redirectUri: string } {
  return provider === 'gsc' ? gscClientConfig() : ga4ClientConfig();
}

export function seoOAuthConfigured(provider: SeoOAuthProvider): boolean {
  try {
    clientConfig(provider);
    return true;
  } catch {
    return false;
  }
}

export function buildSeoOAuthState(input: {
  customerId: number;
  provider: SeoOAuthProvider;
  siteUrl?: string;
  propertyId?: string;
}): string {
  const payload: Record<string, unknown> = {
    customer_id: input.customerId,
    provider: input.provider,
    nonce: randomBytes(12).toString('base64url'),
  };
  if (input.siteUrl) payload.site_url = input.siteUrl;
  if (input.propertyId) payload.property_id = input.propertyId;
  return encodeURIComponent(JSON.stringify(payload));
}

export function parseSeoOAuthState(state: string): {
  customer_id: number;
  provider: SeoOAuthProvider;
  site_url: string;
  property_id: string;
} {
  const raw = decodeURIComponent(String(state ?? ''));
  const data = JSON.parse(raw) as Record<string, unknown>;
  const provider = String(data.provider ?? 'gsc') === 'ga4' ? 'ga4' : 'gsc';
  return {
    customer_id: Number.parseInt(String(data.customer_id ?? '0'), 10),
    provider,
    site_url: String(data.site_url ?? ''),
    property_id: String(data.property_id ?? ''),
  };
}

export function seoOAuthAuthorizationUrl(input: {
  customerId: number;
  provider: SeoOAuthProvider;
  siteUrl?: string;
  propertyId?: string;
}): string {
  const { clientId, redirectUri } = clientConfig(input.provider);
  const scope = input.provider === 'gsc' ? GSC_SCOPE : GA4_SCOPE;
  const params = new URLSearchParams({
    client_id: clientId,
    redirect_uri: redirectUri,
    response_type: 'code',
    scope,
    access_type: 'offline',
    prompt: 'consent',
    state: buildSeoOAuthState(input),
  });
  return `${OAUTH_AUTH}?${params.toString()}`;
}

export async function exchangeSeoAuthorizationCode(
  code: string,
  provider: SeoOAuthProvider,
): Promise<{ refresh_token: string; token_type?: string }> {
  const { clientId, clientSecret, redirectUri } = clientConfig(provider);
  const body = new URLSearchParams({
    code: code.trim(),
    client_id: clientId,
    client_secret: clientSecret,
    redirect_uri: redirectUri,
    grant_type: 'authorization_code',
  });
  const res = await fetch(OAUTH_TOKEN, {
    method: 'POST',
    headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
    body: body.toString(),
  });
  const data = (await res.json()) as Record<string, unknown>;
  if (!res.ok) {
    throw new Error(String(data.error_description ?? data.error ?? `OAuth HTTP ${res.status}`));
  }
  const refresh = String(data.refresh_token ?? '').trim();
  if (!refresh) {
    throw new Error('missing_refresh_token');
  }
  return {
    refresh_token: refresh,
    token_type: data.token_type != null ? String(data.token_type) : undefined,
  };
}

export function encryptSeoRefreshToken(refreshToken: string): string {
  if (vaultConfigured()) {
    return encryptAccessToken(refreshToken).toString('base64');
  }
  return `plain:${refreshToken}`;
}

export function opsWebBaseUrl(): string {
  return (process.env.PTT_OPS_WEB_URL ?? 'http://127.0.0.1:3001').replace(/\/$/, '');
}
