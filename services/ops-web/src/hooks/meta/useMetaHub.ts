'use client';

import { useCallback, useEffect, useMemo, useState } from 'react';
import { useRouter, useSearchParams } from 'next/navigation';
import {
  downloadFacebookHubExport,
  fetchAgencyClients,
  fetchFacebookAdsMigrationStatus,
  fetchFacebookHub,
  type AgencyClient,
  type FacebookAdsMigrationStatus,
  type FacebookHubResponse,
} from '@/lib/api';
import { getAccessToken } from '@/lib/auth';
import { fetchMetaTrackingHealth } from '@/lib/meta/api';
import { metaTrackingEnabled } from '@/lib/meta/flags';
import { yesterdayIso } from '@/lib/meta/format';
import type { FacebookHubExportScope, TrackingHealthAccountRow } from '@/lib/meta/types';
import { useMetaHubAuth } from '@/hooks/meta/useMetaHubAuth';

export function useMetaHub() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const { user, authError, setAuthError, ensureAuth, logout } = useMetaHubAuth();

  const [hub, setHub] = useState<FacebookHubResponse | null>(null);
  const [migration, setMigration] = useState<FacebookAdsMigrationStatus | null>(null);
  const [clientOptions, setClientOptions] = useState<AgencyClient[]>([]);
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(true);
  const [exportBusy, setExportBusy] = useState(false);
  const [trackingAccounts, setTrackingAccounts] = useState<TrackingHealthAccountRow[]>([]);

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
        const [data, tracking] = await Promise.all([
          fetchFacebookHub(access, hubQuery),
          metaTrackingEnabled()
            ? fetchMetaTrackingHealth(access).catch(() => null)
            : Promise.resolve(null),
        ]);
        setHub(data);
        setTrackingAccounts(tracking?.accounts ?? []);
        syncUrl();
      } catch (err) {
        setError(err instanceof Error ? err.message : 'Tải Meta hub thất bại');
      } finally {
        setLoading(false);
      }
    },
    [hubQuery, syncUrl],
  );

  const trackingByClient = useMemo(() => {
    const map = new Map<string, TrackingHealthAccountRow>();
    for (const row of trackingAccounts) {
      if (!map.has(row.client_id)) map.set(row.client_id, row);
    }
    return map;
  }, [trackingAccounts]);

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

  const displayError = error || authError;

  return {
    user,
    hub,
    migration,
    clientOptions,
    error: displayError,
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
    trackingByClient,
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
