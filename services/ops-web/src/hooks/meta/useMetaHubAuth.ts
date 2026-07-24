'use client';

import { useCallback, useState } from 'react';
import { useRouter } from 'next/navigation';
import { staffMe, staffRefresh } from '@/lib/api';
import {
  clearSession,
  getAccessToken,
  getRefreshToken,
  getStoredUser,
  updateAccessToken,
  updateStoredUser,
  type StoredStaffUser,
} from '@/lib/auth';
import { canViewMetaHub } from '@/lib/meta/caps';

export function useMetaHubAuth() {
  const router = useRouter();
  const [user, setUser] = useState<StoredStaffUser | null>(null);
  const [authError, setAuthError] = useState('');

  const ensureAuth = useCallback(async (): Promise<string | null> => {
    let access = getAccessToken();
    if (!access) {
      router.replace('/login');
      return null;
    }
    const cached = getStoredUser();
    if (cached) setUser(cached);
    try {
      const me = await staffMe(access);
      setUser(me);
      updateStoredUser(me);
      if (!canViewMetaHub(me)) {
        setAuthError('Không có quyền Meta hub');
        return null;
      }
      setAuthError('');
      return access;
    } catch {
      const refresh = getRefreshToken();
      if (!refresh) {
        clearSession();
        router.replace('/login');
        return null;
      }
      const out = await staffRefresh(refresh);
      updateAccessToken(out.access_token);
      access = out.access_token;
      setAuthError('');
      return access;
    }
  }, [router]);

  const logout = useCallback(() => {
    clearSession();
    router.push('/login');
  }, [router]);

  return { user, authError, setAuthError, ensureAuth, logout };
}
