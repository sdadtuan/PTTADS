'use client';

import { useCallback, useEffect, useMemo, useState } from 'react';
import { useRouter, useSearchParams } from 'next/navigation';
import {
  downloadFacebookHubExport,
  fetchAgencyClients,
  fetchFacebookAdsMigrationStatus,
  fetchFacebookHub,
  staffMe,
  staffRefresh,
  type AgencyClient,
  type FacebookAdsMigrationStatus,
  type FacebookHubResponse,
} from '@/lib/api';
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
import { yesterdayIso } from '@/lib/meta/format';
import type { FacebookHubExportScope } from '@/lib/meta/types';

export function useMetaHub() {
  const router = useRouter();
  const searchParams = useSearchParams();

  const [user, setUser] = useState<StoredStaffUser | null>(null);
  const [hub, setHub] = useState<FacebookHubResponse | null>(null);
  const [migration, setMigration] = useState<FacebookAdsMigrationStatus | null>(null);
  const [clientOptions, setClientOptions] = useState<AgencyClient[]>([]);
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(true);
  const [exportBusy, setExportBusy] = useState(false);

  const [days, setDays] = useState(Number(searchParams.get('days') ?? 7) || 7);
  const [dateTo, setDateTo] = useState(searchParams.get('date_to') ?? yesterdayIso());
  const [dateFrom, setDateFrom] = useState(searchParams.get('date_from') ?? '');
  const [clientId, setClientId] = useState(searchParams.get('client_id') ?? '');
  const [status, setStatus] = useState(searchParams.get('status') ?? '');
  const [q, setQ] = useState(searchParams.get('q') ?? '');
  const [exportScope, setExportScope] = useState<FacebookHubExportScope>('clients');

  const hubQuery = useMemo(
    () => ({
      days: dateFrom ? undefined : days,
      date_to: dateTo || undefined,
      date_from: dateFrom || undefined,
      status: status || undefined,
      client_id: clientId || undefined,
      q: q || undefined,
    }),
    [clientId, dateFrom, dateTo, days, q, status],
  );

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
        setError('Không có quyền Meta hub');
        return null;
      }
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
      return access;
    }
  }, [router]);

  const syncUrl = useCallback(() => {
    const qs = new URLSearchParams();
    const tab = searchParams.get('tab');
    if (tab && tab !== 'clients') qs.set('tab', tab);
    if (days !== 7) qs.set('days', String(days));
    if (dateTo) qs.set('date_to', dateTo);
    if (dateFrom) qs.set('date_from', dateFrom);
    if (clientId) qs.set('client_id', clientId);
    if (status) qs.set('status', status);
    if (q) qs.set('q', q);
    const suffix = qs.toString();
    router.replace(suffix ? `/meta/facebook-ads?${suffix}` : '/meta/facebook-ads', {
      scroll: false,
    });
  }, [clientId, dateFrom, dateTo, days, q, router, searchParams, status]);

  const loadHub = useCallback(
    async (access: string) => {
      setLoading(true);
      setError('');
      try {
        const data = await fetchFacebookHub(access, hubQuery);
        setHub(data);
        syncUrl();
      } catch (err) {
        setError(err instanceof Error ? err.message : 'Tải Meta hub thất bại');
      } finally {
        setLoading(false);
      }
    },
    [hubQuery, syncUrl],
  );

  useEffect(() => {
    void (async () => {
      const access = await ensureAuth();
      if (!access) return;
      try {
        const list = await fetchAgencyClients(access, { status: 'active' });
        setClientOptions(list.clients ?? []);
      } catch {
        /* optional filter list */
      }
      try {
        const mig = await fetchFacebookAdsMigrationStatus(access);
        setMigration(mig);
      } catch {
        /* optional */
      }
      await loadHub(access);
    })();
  }, [ensureAuth, loadHub]);

  const handleRefresh = useCallback(() => {
    const access = getAccessToken();
    if (!access) return;
    void loadHub(access);
  }, [loadHub]);

  const handleExport = useCallback(async () => {
    const access = getAccessToken();
    if (!access) return;
    setExportBusy(true);
    setError('');
    try {
      const { blob, filename } = await downloadFacebookHubExport(access, {
        ...hubQuery,
        scope: exportScope,
      });
      const url = URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = filename;
      a.click();
      URL.revokeObjectURL(url);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Export CSV thất bại');
    } finally {
      setExportBusy(false);
    }
  }, [exportScope, hubQuery]);

  const logout = useCallback(() => {
    clearSession();
    router.push('/login');
  }, [router]);

  return {
    user,
    hub,
    migration,
    clientOptions,
    error,
    loading,
    exportBusy,
    days,
    dateTo,
    dateFrom,
    clientId,
    status,
    q,
    exportScope,
    hubQuery,
    setDays,
    setDateTo,
    setDateFrom,
    setClientId,
    setStatus,
    setQ,
    setExportScope,
    handleRefresh,
    handleExport,
    logout,
  };
}
