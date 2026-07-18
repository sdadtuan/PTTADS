import { randomBytes, scryptSync, timingSafeEqual } from 'crypto';

const SCRYPT_PREFIX = 'scrypt:';

export function hashPortalPassword(plain: string): string {
  const salt = randomBytes(16);
  const hash = scryptSync(plain, salt, 64);
  return `${SCRYPT_PREFIX}${salt.toString('base64')}:${hash.toString('base64')}`;
}

export function verifyPortalPassword(plain: string, stored: string): boolean {
  if (stored.startsWith('plain:')) {
    if (
      process.env.NODE_ENV === 'production' &&
      !['1', 'true', 'yes', 'on'].includes(
        (process.env.PTT_PORTAL_ALLOW_PLAIN_PASSWORD ?? '0').trim().toLowerCase(),
      )
    ) {
      return false;
    }
    return stored.slice(6) === plain;
  }
  if (stored.startsWith(SCRYPT_PREFIX)) {
    const body = stored.slice(SCRYPT_PREFIX.length);
    const sep = body.indexOf(':');
    if (sep <= 0) {
      return false;
    }
    const salt = Buffer.from(body.slice(0, sep), 'base64');
    const expected = Buffer.from(body.slice(sep + 1), 'base64');
    const actual = scryptSync(plain, salt, 64);
    if (expected.length !== actual.length) {
      return false;
    }
    return timingSafeEqual(expected, actual);
  }
  if (stored.length === 64 && /^[a-f0-9]+$/i.test(stored)) {
    return false;
  }
  return stored === plain;
}
