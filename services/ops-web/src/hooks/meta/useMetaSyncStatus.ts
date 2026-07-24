'use client';

import { useCallback, useEffect, useState } from 'react';
import { fetchMetaSyncStatus } from '@/lib/meta/api';
import type { MetaSyncStatusResponse } from '@/lib/meta/types';
import { getAccessToken } from '@/lib/auth';

export function useMetaSyncStatus(clientId?: string) {
  const [data, setData] = useState<MetaSyncStatusResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');

  const reload = useCallback(async () => {
    const access = getAccessToken();
    if (!access) {
      setLoading(false);
      return;
    }
    setLoading(true);
    setError('');
    try {
      const out = await fetchMetaSyncStatus(access, clientId || undefined);
      setData(out);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Tải sync status thất bại');
      setData(null);
    } finally {
      setLoading(false);
    }
  }, [clientId]);

  useEffect(() => {
    void reload();
  }, [reload]);

  return { data, loading, error, reload };
}
