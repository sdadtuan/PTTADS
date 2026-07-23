import { createCipheriv, createDecipheriv, createHash, randomBytes } from 'crypto';

const NONCE_LEN = 12;
const KEY_LEN = 32;

export class TokenVaultError extends Error {
  constructor(message: string) {
    super(message);
    this.name = 'TokenVaultError';
  }
}

export function vaultConfigured(): boolean {
  return Boolean((process.env.PTT_TOKEN_VAULT_KEY ?? '').trim());
}

export function deriveVaultKey(): Buffer {
  const raw = (process.env.PTT_TOKEN_VAULT_KEY ?? '').trim();
  if (!raw) {
    throw new TokenVaultError('PTT_TOKEN_VAULT_KEY chưa cấu hình');
  }
  try {
    const padded = raw + '='.repeat((4 - (raw.length % 4)) % 4);
    const key = Buffer.from(padded, 'base64url');
    if (key.length === KEY_LEN) {
      return key;
    }
  } catch {
    // fall through to sha256
  }
  return createHash('sha256').update(raw, 'utf8').digest();
}

/** AES-256-GCM blob compatible with ptt_meta/token_crypto.py (nonce || ciphertext+tag). */
export function encryptAccessToken(plaintext: string): Buffer {
  const text = String(plaintext ?? '').trim();
  if (!text) {
    throw new TokenVaultError('Token rỗng');
  }
  const key = deriveVaultKey();
  const nonce = randomBytes(NONCE_LEN);
  const cipher = createCipheriv('aes-256-gcm', key, nonce);
  const enc = Buffer.concat([cipher.update(text, 'utf8'), cipher.final()]);
  const tag = cipher.getAuthTag();
  return Buffer.concat([nonce, enc, tag]);
}

/** Decrypt AES-256-GCM blob from encryptAccessToken / Python token_crypto.encrypt_token. */
export function decryptAccessToken(blob: Buffer | null | undefined): string | null {
  if (!blob || blob.length <= NONCE_LEN + 16) {
    return null;
  }
  try {
    const key = deriveVaultKey();
    const nonce = blob.subarray(0, NONCE_LEN);
    const encTag = blob.subarray(NONCE_LEN);
    const tag = encTag.subarray(encTag.length - 16);
    const enc = encTag.subarray(0, encTag.length - 16);
    const decipher = createDecipheriv('aes-256-gcm', key, nonce);
    decipher.setAuthTag(tag);
    return Buffer.concat([decipher.update(enc), decipher.final()]).toString('utf8');
  } catch {
    return null;
  }
}

export type TokenStatus = 'unknown' | 'valid' | 'expiring' | 'expired' | 'revoked';

export function computeTokenStatus(input: {
  hasToken: boolean;
  tokenStatus?: string | null;
  tokenExpiresAt?: Date | null;
  revoked?: boolean;
}): TokenStatus {
  if (input.revoked || (input.tokenStatus ?? '').toLowerCase() === 'revoked') {
    return 'revoked';
  }
  if (!input.hasToken) {
    return 'unknown';
  }
  const exp = input.tokenExpiresAt;
  if (exp) {
    const now = Date.now();
    if (exp.getTime() < now) {
      return 'expired';
    }
    if (exp.getTime() < now + 7 * 24 * 60 * 60 * 1000) {
      return 'expiring';
    }
  }
  return 'valid';
}
