'use client';

import { useCallback, useEffect, useState } from 'react';
import { fetchMetaTrackingHealth } from '@/lib/meta/api';
import type { TrackingHealthResponse } from '@/lib/meta/types';

export function useMetaTracking(token: string | null, clientId?: string, windowDays = 7) {
  const [data, setData] = useState<TrackingHealthResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');

  const reload = useCallback(async () => {
    if (!token) {
      setData(null);
      setLoading(false);
      return;
    }
    setLoading(true);
    setError('');
    try {
      const out = await fetchMetaTrackingHealth(token, {
        client_id: clientId || undefined,
        window_days: windowDays,
      });
      setData(out);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Tải tracking health thất bại');
      setData(null);
    } finally {
      setLoading(false);
    }
  }, [token, clientId, windowDays]);

  useEffect(() => {
    void reload();
  }, [reload]);

  return { data, loading, error, reload };
}
