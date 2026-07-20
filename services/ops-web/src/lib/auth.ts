const TOKEN_KEY = 'ptt_ops_access_token';
const REFRESH_KEY = 'ptt_ops_refresh_token';
const USER_KEY = 'ptt_ops_user';

export interface StaffSectionCap {
  section: string;
  action: string;
}

export interface StoredStaffUser {
  id: string;
  email: string;
  display_name: string;
  position_id: number;
  caps?: StaffSectionCap[];
}

export function saveSession(
  accessToken: string,
  refreshToken: string,
  user: StoredStaffUser,
): void {
  if (typeof window === 'undefined') return;
  sessionStorage.setItem(TOKEN_KEY, accessToken);
  sessionStorage.setItem(REFRESH_KEY, refreshToken);
  sessionStorage.setItem(USER_KEY, JSON.stringify(user));
}

export function clearSession(): void {
  if (typeof window === 'undefined') return;
  sessionStorage.removeItem(TOKEN_KEY);
  sessionStorage.removeItem(REFRESH_KEY);
  sessionStorage.removeItem(USER_KEY);
}

export function getAccessToken(): string | null {
  if (typeof window === 'undefined') return null;
  return sessionStorage.getItem(TOKEN_KEY);
}

export function getRefreshToken(): string | null {
  if (typeof window === 'undefined') return null;
  return sessionStorage.getItem(REFRESH_KEY);
}

export function getStoredUser(): StoredStaffUser | null {
  if (typeof window === 'undefined') return null;
  const raw = sessionStorage.getItem(USER_KEY);
  if (!raw) return null;
  try {
    return JSON.parse(raw) as StoredStaffUser;
  } catch {
    return null;
  }
}

export function hasCap(user: StoredStaffUser | null, section: string, action = 'view'): boolean {
  if (!user?.caps?.length) return true;
  return user.caps.some((c) => c.section === section && c.action === action);
}

export function updateStoredUser(user: StoredStaffUser): void {
  if (typeof window === 'undefined') return;
  sessionStorage.setItem(USER_KEY, JSON.stringify(user));
}

export function updateAccessToken(token: string): void {
  if (typeof window === 'undefined') return;
  sessionStorage.setItem(TOKEN_KEY, token);
}
