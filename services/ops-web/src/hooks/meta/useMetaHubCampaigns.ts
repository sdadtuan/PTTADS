'use client';

import { useCallback, useEffect, useState } from 'react';
import { fetchFacebookHubCampaigns } from '@/lib/meta/api';
import type { FacebookHubCampaignsResponse, FacebookHubQuery } from '@/lib/meta/types';
import { getAccessToken } from '@/lib/auth';

export function useMetaHubCampaigns(query: FacebookHubQuery, enabled: boolean) {
  const [data, setData] = useState<FacebookHubCampaignsResponse | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');

  const reload = useCallback(async () => {
    const access = getAccessToken();
    if (!access || !enabled) return;
    setLoading(true);
    setError('');
    try {
      const out = await fetchFacebookHubCampaigns(access, query);
      setData(out);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Tải campaigns thất bại');
      setData(null);
    } finally {
      setLoading(false);
    }
  }, [enabled, query]);

  useEffect(() => {
    void reload();
  }, [reload]);

  return { data, campaigns: data?.campaigns ?? [], loading, error, reload };
}
