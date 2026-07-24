'use client';

import { useCallback, useEffect, useState } from 'react';
import { fetchMetaCapiEvents, postMetaCapiRetry } from '@/lib/meta/api';
import type { CapiEventRow } from '@/lib/meta/types';

export function useMetaCapiEvents(
  token: string | null,
  params: { client_id?: string; status?: string; limit?: number } = {},
) {
  const [events, setEvents] = useState<CapiEventRow[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [retryingId, setRetryingId] = useState<string | null>(null);

  const reload = useCallback(async () => {
    if (!token) {
      setEvents([]);
      setLoading(false);
      return;
    }
    setLoading(true);
    setError('');
    try {
      const out = await fetchMetaCapiEvents(token, {
        client_id: params.client_id,
        status: params.status,
        limit: params.limit ?? 50,
      });
      setEvents(out.events ?? []);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Tải CAPI events thất bại');
      setEvents([]);
    } finally {
      setLoading(false);
    }
  }, [token, params.client_id, params.status, params.limit]);

  useEffect(() => {
    void reload();
  }, [reload]);

  const retry = useCallback(
    async (logId: string) => {
      if (!token) return;
      setRetryingId(logId);
      setError('');
      try {
        await postMetaCapiRetry(token, logId);
        await reload();
      } catch (err) {
        setError(err instanceof Error ? err.message : 'Retry thất bại');
      } finally {
        setRetryingId(null);
      }
    },
    [token, reload],
  );

  return { events, loading, error, reload, retry, retryingId };
}
