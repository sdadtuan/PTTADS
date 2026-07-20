import * as crypto from 'crypto';

export type StaffTokenType = 'access' | 'refresh';

export interface StaffJwtPayload {
  sub: string;
  email: string;
  display_name: string;
  position_id: number;
  token_type: StaffTokenType;
  iat: number;
  exp: number;
}

function base64url(input: Buffer | string): string {
  const buf = typeof input === 'string' ? Buffer.from(input, 'utf8') : input;
  return buf.toString('base64url');
}

export function signStaffJwt(
  claims: Omit<StaffJwtPayload, 'iat' | 'exp'>,
  secret: string,
  ttlSec: number,
): string {
  const header = { alg: 'HS256', typ: 'JWT' };
  const now = Math.floor(Date.now() / 1000);
  const payload: StaffJwtPayload = {
    ...claims,
    iat: now,
    exp: now + Math.max(60, ttlSec),
  };
  const encodedHeader = base64url(JSON.stringify(header));
  const encodedPayload = base64url(JSON.stringify(payload));
  const data = `${encodedHeader}.${encodedPayload}`;
  const signature = crypto.createHmac('sha256', secret).update(data).digest('base64url');
  return `${data}.${signature}`;
}

export function verifyStaffJwt(token: string, secret: string): StaffJwtPayload | null {
  const parts = token.split('.');
  if (parts.length !== 3) {
    return null;
  }
  const [encodedHeader, encodedPayload, signature] = parts;
  const data = `${encodedHeader}.${encodedPayload}`;
  const expected = crypto.createHmac('sha256', secret).update(data).digest('base64url');
  if (signature.length !== expected.length) {
    return null;
  }
  if (!crypto.timingSafeEqual(Buffer.from(signature), Buffer.from(expected))) {
    return null;
  }
  try {
    const payload = JSON.parse(
      Buffer.from(encodedPayload, 'base64url').toString('utf8'),
    ) as StaffJwtPayload;
    const now = Math.floor(Date.now() / 1000);
    if (!payload.sub || !payload.email || !payload.exp || payload.exp < now) {
      return null;
    }
    if (payload.token_type !== 'access' && payload.token_type !== 'refresh') {
      return null;
    }
    return payload;
  } catch {
    return null;
  }
}
