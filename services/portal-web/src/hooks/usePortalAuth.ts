'use client';

import { useCallback, useEffect, useState } from 'react';
import { useRouter } from 'next/navigation';
import { portalMe, portalRefresh, isTenantArchivedError } from '@/lib/api';
import {
  accessTokenExpiringSoon,
  clearSession,
  getRefreshToken,
  getStoredUser,
  getToken,
  saveSession,
  type StoredUser,
} from '@/lib/auth';

export function usePortalAuth() {
  const router = useRouter();
  const [user, setUser] = useState<StoredUser | null>(null);
  const [token, setToken] = useState('');
  const [loading, setLoading] = useState(true);
  const [sessionWarning, setSessionWarning] = useState('');

  const logout = useCallback(() => {
    clearSession();
    router.push('/login');
  }, [router]);

  const refreshIfNeeded = useCallback(async (currentToken: string) => {
    if (!accessTokenExpiringSoon()) {
      return currentToken;
    }
    const refresh = getRefreshToken();
    if (!refresh) {
      return currentToken;
    }
    const out = await portalRefresh(refresh);
    saveSession(out.access_token, out.user, {
      refreshToken: out.refresh_token,
      expiresInSec: out.expires_in,
    });
    setToken(out.access_token);
    setUser(out.user);
    setSessionWarning('');
    return out.access_token;
  }, []);

  useEffect(() => {
    let cancelled = false;
    async function boot() {
      const authToken = getToken();
      const cached = getStoredUser();
      if (!authToken) {
        router.replace('/login');
        return;
      }
      if (cached) {
        setUser(cached);
      }
      setToken(authToken);
      try {
        let activeToken = authToken;
        if (accessTokenExpiringSoon()) {
          activeToken = await refreshIfNeeded(authToken);
        } else if (accessTokenExpiringSoon(60 * 60 * 1000)) {
          setSessionWarning('Phiên đăng nhập sắp hết hạn — hệ thống sẽ tự làm mới.');
        }
        const me = await portalMe(activeToken);
        if (cancelled) return;
        setUser(me);
        saveSession(activeToken, me, {
          refreshToken: getRefreshToken() ?? undefined,
          expiresInSec: undefined,
        });
      } catch (err) {
        if (cancelled) return;
        if (isTenantArchivedError(err)) {
          clearSession();
          router.replace('/archived');
          return;
        }
        clearSession();
        router.replace('/login');
      } finally {
        if (!cancelled) {
          setLoading(false);
        }
      }
    }
    void boot();
    return () => {
      cancelled = true;
    };
  }, [router, refreshIfNeeded]);

  return { user, token, loading, sessionWarning, logout };
}
