export const SESSION_COOKIE = 'ptt_portal_session';

const TOKEN_KEY = 'ptt_portal_token';
const REFRESH_KEY = 'ptt_portal_refresh';
const USER_KEY = 'ptt_portal_user';
const EXPIRES_KEY = 'ptt_portal_expires_at';

export interface StoredUser {
  id: string;
  email: string;
  client_id: string;
  role: string;
}

function setSessionCookie(): void {
  if (typeof document === 'undefined') return;
  document.cookie = `${SESSION_COOKIE}=1; path=/; SameSite=Lax`;
}

function clearSessionCookie(): void {
  if (typeof document === 'undefined') return;
  document.cookie = `${SESSION_COOKIE}=; path=/; Max-Age=0; SameSite=Lax`;
}

export function saveSession(
  token: string,
  user: StoredUser,
  opts?: { refreshToken?: string; expiresInSec?: number },
): void {
  if (typeof window === 'undefined') return;
  sessionStorage.setItem(TOKEN_KEY, token);
  sessionStorage.setItem(USER_KEY, JSON.stringify(user));
  if (opts?.refreshToken) {
    sessionStorage.setItem(REFRESH_KEY, opts.refreshToken);
  }
  if (opts?.expiresInSec) {
    sessionStorage.setItem(EXPIRES_KEY, String(Date.now() + opts.expiresInSec * 1000));
  }
  setSessionCookie();
}

export function clearSession(): void {
  if (typeof window === 'undefined') return;
  sessionStorage.removeItem(TOKEN_KEY);
  sessionStorage.removeItem(REFRESH_KEY);
  sessionStorage.removeItem(USER_KEY);
  sessionStorage.removeItem(EXPIRES_KEY);
  clearSessionCookie();
}

export function getToken(): string | null {
  if (typeof window === 'undefined') return null;
  return sessionStorage.getItem(TOKEN_KEY);
}

export function getRefreshToken(): string | null {
  if (typeof window === 'undefined') return null;
  return sessionStorage.getItem(REFRESH_KEY);
}

export function getStoredUser(): StoredUser | null {
  if (typeof window === 'undefined') return null;
  const raw = sessionStorage.getItem(USER_KEY);
  if (!raw) return null;
  try {
    return JSON.parse(raw) as StoredUser;
  } catch {
    return null;
  }
}

export function getAccessExpiresAt(): number | null {
  if (typeof window === 'undefined') return null;
  const raw = sessionStorage.getItem(EXPIRES_KEY);
  if (!raw) return null;
  const value = Number(raw);
  return Number.isFinite(value) ? value : null;
}

export function accessTokenExpiringSoon(withinMs = 15 * 60 * 1000): boolean {
  const expiresAt = getAccessExpiresAt();
  if (!expiresAt) return false;
  return expiresAt - Date.now() <= withinMs;
}
