import { randomBytes } from 'crypto';

const OAUTH_AUTH = 'https://accounts.google.com/o/oauth2/v2/auth';
const OAUTH_TOKEN = 'https://oauth2.googleapis.com/token';
const SCOPES = 'https://www.googleapis.com/auth/adwords';

function clientConfig(): { clientId: string; clientSecret: string; redirectUri: string } {
  const clientId = (process.env.PTT_GOOGLE_ADS_CLIENT_ID ?? '').trim();
  const clientSecret = (process.env.PTT_GOOGLE_ADS_CLIENT_SECRET ?? '').trim();
  const redirectUri = (process.env.PTT_GOOGLE_OAUTH_REDIRECT_URI ?? '').trim();
  if (!clientId || !clientSecret || !redirectUri) {
    throw new Error('missing_google_oauth_env');
  }
  return { clientId, clientSecret, redirectUri };
}

export function buildGoogleOAuthState(agencyClientId: string, accountId?: string): string {
  const payload = {
    client_id: agencyClientId,
    account_id: accountId ?? '',
    nonce: randomBytes(12).toString('base64url'),
  };
  return encodeURIComponent(JSON.stringify(payload));
}

export function parseGoogleOAuthState(state: string): { client_id: string; account_id: string } {
  const raw = decodeURIComponent(String(state ?? ''));
  const data = JSON.parse(raw) as Record<string, unknown>;
  return {
    client_id: String(data.client_id ?? ''),
    account_id: String(data.account_id ?? ''),
  };
}

export function googleOAuthAuthorizationUrl(agencyClientId: string, accountId?: string): string {
  const { clientId, redirectUri } = clientConfig();
  const params = new URLSearchParams({
    client_id: clientId,
    redirect_uri: redirectUri,
    response_type: 'code',
    scope: SCOPES,
    access_type: 'offline',
    prompt: 'consent',
    state: buildGoogleOAuthState(agencyClientId, accountId),
  });
  return `${OAUTH_AUTH}?${params.toString()}`;
}

export async function exchangeGoogleAuthorizationCode(code: string): Promise<{
  refresh_token: string;
  access_token?: string;
  expires_in?: number;
}> {
  const { clientId, clientSecret, redirectUri } = clientConfig();
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
    access_token: data.access_token != null ? String(data.access_token) : undefined,
    expires_in: data.expires_in != null ? Number(data.expires_in) : undefined,
  };
}

export function googleOAuthConfigured(): boolean {
  try {
    clientConfig();
    return true;
  } catch {
    return false;
  }
}
