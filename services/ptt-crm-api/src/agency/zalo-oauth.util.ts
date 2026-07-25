import { randomBytes } from 'crypto';

const OAUTH_AUTH = 'https://oauth.zaloapp.com/v4/permission';
const OAUTH_TOKEN = 'https://oauth.zaloapp.com/v4/access_token';

function clientConfig(): { appId: string; appSecret: string; redirectUri: string } {
  const appId = (process.env.PTT_ZALO_APP_ID ?? '').trim();
  const appSecret = (process.env.PTT_ZALO_APP_SECRET ?? '').trim();
  const redirectUri = (process.env.PTT_ZALO_OAUTH_REDIRECT_URI ?? '').trim();
  if (!appId || !appSecret || !redirectUri) {
    throw new Error('missing_zalo_oauth_env');
  }
  return { appId, appSecret, redirectUri };
}

export function buildZaloOAuthState(agencyClientId: string, accountId?: string): string {
  const payload = {
    client_id: agencyClientId,
    account_id: accountId ?? '',
    nonce: randomBytes(12).toString('base64url'),
  };
  return encodeURIComponent(JSON.stringify(payload));
}

export function parseZaloOAuthState(state: string): { client_id: string; account_id: string } {
  const raw = decodeURIComponent(String(state ?? ''));
  const data = JSON.parse(raw) as Record<string, unknown>;
  return {
    client_id: String(data.client_id ?? ''),
    account_id: String(data.account_id ?? ''),
  };
}

export function zaloOAuthAuthorizationUrl(agencyClientId: string, accountId?: string): string {
  const { appId, redirectUri } = clientConfig();
  const params = new URLSearchParams({
    app_id: appId,
    redirect_uri: redirectUri,
    state: buildZaloOAuthState(agencyClientId, accountId),
  });
  return `${OAUTH_AUTH}?${params.toString()}`;
}

export async function exchangeZaloAuthorizationCode(code: string): Promise<{
  access_token: string;
  refresh_token?: string;
  expires_in?: number;
}> {
  const { appId, appSecret } = clientConfig();
  const body = new URLSearchParams({
    code: code.trim(),
    app_id: appId,
    grant_type: 'authorization_code',
  });
  const res = await fetch(OAUTH_TOKEN, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/x-www-form-urlencoded',
      secret_key: appSecret,
    },
    body: body.toString(),
  });
  const data = (await res.json()) as Record<string, unknown>;
  if (!res.ok) {
    throw new Error(String(data.message ?? data.error ?? `OAuth HTTP ${res.status}`));
  }
  const access = String(data.access_token ?? '').trim();
  if (!access) {
    throw new Error('missing_access_token');
  }
  return {
    access_token: access,
    refresh_token: data.refresh_token != null ? String(data.refresh_token) : undefined,
    expires_in: data.expires_in != null ? Number(data.expires_in) : undefined,
  };
}

export function zaloOAuthConfigured(): boolean {
  try {
    clientConfig();
    return true;
  } catch {
    return false;
  }
}
