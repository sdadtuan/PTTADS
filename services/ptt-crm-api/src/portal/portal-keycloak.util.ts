import { createPublicKey, verify } from 'crypto';

export interface KeycloakJwtClaims {
  sub: string;
  email?: string;
  preferred_username?: string;
  client_id?: string;
  realm_access?: { roles?: string[] };
  resource_access?: Record<string, { roles?: string[] }>;
  exp?: number;
  iss?: string;
  aud?: string | string[];
}

export interface PortalKeycloakConfig {
  issuer: string;
  audience: string;
  clientIdClaim: string;
}

type JwkKey = {
  kid: string;
  kty: string;
  n?: string;
  e?: string;
  x5c?: string[];
};

let jwksCache: { fetchedAt: number; keys: JwkKey[] } | null = null;
const JWKS_TTL_MS = 5 * 60 * 1000;

function decodePart(part: string): Buffer {
  const padded = part.replace(/-/g, '+').replace(/_/g, '/');
  const pad = padded.length % 4 === 0 ? '' : '='.repeat(4 - (padded.length % 4));
  return Buffer.from(padded + pad, 'base64');
}

function parseJwt(token: string): { header: Record<string, unknown>; payload: KeycloakJwtClaims; sig: Buffer } | null {
  const parts = token.split('.');
  if (parts.length !== 3) {
    return null;
  }
  try {
    const header = JSON.parse(decodePart(parts[0]).toString('utf8')) as Record<string, unknown>;
    const payload = JSON.parse(decodePart(parts[1]).toString('utf8')) as KeycloakJwtClaims;
    const sig = decodePart(parts[2]);
    return { header, payload, sig };
  } catch {
    return null;
  }
}

async function fetchJwks(issuer: string): Promise<JwkKey[]> {
  const now = Date.now();
  if (jwksCache && now - jwksCache.fetchedAt < JWKS_TTL_MS) {
    return jwksCache.keys;
  }
  const url = `${issuer.replace(/\/$/, '')}/protocol/openid-connect/certs`;
  const resp = await fetch(url);
  if (!resp.ok) {
    throw new Error(`JWKS fetch failed: ${resp.status}`);
  }
  const data = (await resp.json()) as { keys?: JwkKey[] };
  const keys = data.keys ?? [];
  jwksCache = { fetchedAt: now, keys };
  return keys;
}

function publicKeyFromJwk(jwk: JwkKey): ReturnType<typeof createPublicKey> | null {
  if (jwk.x5c?.[0]) {
    const pem = `-----BEGIN CERTIFICATE-----\n${jwk.x5c[0]}\n-----END CERTIFICATE-----`;
    return createPublicKey(pem);
  }
  if (jwk.kty === 'RSA' && jwk.n && jwk.e) {
    return createPublicKey({ key: jwk as unknown as Record<string, string>, format: 'jwk' });
  }
  return null;
}

function audMatches(aud: string | string[] | undefined, expected: string): boolean {
  if (!aud) {
    return false;
  }
  if (Array.isArray(aud)) {
    return aud.includes(expected);
  }
  return aud === expected;
}

export async function verifyKeycloakAccessToken(
  token: string,
  config: PortalKeycloakConfig,
): Promise<KeycloakJwtClaims | null> {
  const parsed = parseJwt(token);
  if (!parsed) {
    return null;
  }
  const { header, payload, sig } = parsed;
  if (payload.iss && payload.iss !== config.issuer) {
    return null;
  }
  if (payload.exp && payload.exp * 1000 < Date.now()) {
    return null;
  }
  if (!audMatches(payload.aud, config.audience)) {
    return null;
  }

  const kid = String(header.kid ?? '');
  const keys = await fetchJwks(config.issuer);
  const jwk = keys.find((k) => k.kid === kid) ?? keys[0];
  if (!jwk) {
    return null;
  }
  const pub = publicKeyFromJwk(jwk);
  if (!pub) {
    return null;
  }

  const signingInput = token.split('.').slice(0, 2).join('.');
  const algo = String(header.alg ?? 'RS256');
  if (algo !== 'RS256') {
    return null;
  }
  const ok = verify('RSA-SHA256', Buffer.from(signingInput), pub, sig);
  return ok ? payload : null;
}

export function mapKeycloakToPortalPayload(
  claims: KeycloakJwtClaims,
  config: PortalKeycloakConfig,
): { sub: string; email: string; client_id: string; role: 'viewer' | 'approver'; iat: number; exp: number } | null {
  const email = (claims.email ?? claims.preferred_username ?? '').trim().toLowerCase();
  const extra = claims as unknown as Record<string, unknown>;
  const clientId = String(extra[config.clientIdClaim] ?? claims.client_id ?? '').trim();
  if (!email || !clientId) {
    return null;
  }
  const roles = [
    ...(claims.realm_access?.roles ?? []),
    ...(claims.resource_access?.['ptt-portal']?.roles ?? []),
  ].map((r) => r.toLowerCase());
  const role: 'viewer' | 'approver' = roles.includes('approver') ? 'approver' : 'viewer';
  const now = Math.floor(Date.now() / 1000);
  return {
    sub: claims.sub,
    email,
    client_id: clientId,
    role,
    iat: claims.exp ? claims.exp - 3600 : now,
    exp: claims.exp ?? now + 28800,
  };
}
