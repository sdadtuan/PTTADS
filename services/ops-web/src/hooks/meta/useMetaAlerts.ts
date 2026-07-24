'use client';

import { useCallback, useEffect, useState } from 'react';
import { fetchMetaAlerts, patchMetaAlertAck } from '@/lib/meta/api';
import type { MetaAlertRow } from '@/lib/meta/types';
import { getAccessToken } from '@/lib/auth';

export function useMetaAlerts(clientId?: string, enabled = true) {
  const [alerts, setAlerts] = useState<MetaAlertRow[]>([]);
  const [openCount, setOpenCount] = useState(0);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  const [ackBusyId, setAckBusyId] = useState<string | null>(null);

  const reload = useCallback(async () => {
    const access = getAccessToken();
    if (!access || !enabled) return;
    setLoading(true);
    setError('');
    try {
      const out = await fetchMetaAlerts(access, {
        client_id: clientId || undefined,
        include_ack: false,
        limit: 200,
      });
      setAlerts(out.alerts ?? []);
      setOpenCount(out.open_count ?? out.alerts?.length ?? 0);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Tải alerts thất bại');
      setAlerts([]);
      setOpenCount(0);
    } finally {
      setLoading(false);
    }
  }, [clientId, enabled]);

  useEffect(() => {
    void reload();
  }, [reload]);

  const acknowledge = useCallback(
    async (alertId: string) => {
      const access = getAccessToken();
      if (!access) return;
      setAckBusyId(alertId);
      setError('');
      try {
        await patchMetaAlertAck(access, alertId);
        setAlerts((prev) => prev.filter((a) => a.id !== alertId));
        setOpenCount((prev) => Math.max(0, prev - 1));
      } catch (err) {
        setError(err instanceof Error ? err.message : 'Ack alert thất bại');
      } finally {
        setAckBusyId(null);
      }
    },
    [],
  );

  return { alerts, openCount, loading, error, ackBusyId, reload, acknowledge };
}
