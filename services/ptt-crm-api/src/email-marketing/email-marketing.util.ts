import { randomBytes } from 'crypto';

export function iso(value: unknown): string | null {
  if (value == null) return null;
  if (value instanceof Date) return value.toISOString();
  return String(value);
}

export function normalizeEmail(email: string): string {
  return email.trim().toLowerCase();
}

export function isValidEmail(email: string): boolean {
  return /^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(normalizeEmail(email));
}

export function randomToken(bytes = 24): string {
  return randomBytes(bytes).toString('base64url');
}

export function clampLimit(limit: number | undefined, fallback = 50, max = 200): number {
  if (limit == null || !Number.isFinite(limit)) return fallback;
  return Math.max(1, Math.min(max, Math.floor(limit)));
}

export function clampOffset(offset: number | undefined): number {
  if (offset == null || !Number.isFinite(offset)) return 0;
  return Math.max(0, Math.floor(offset));
}
