'use client';

import { useCallback, useEffect, useState } from 'react';
import {
  fetchMetaAnomalies,
  fetchMetaBudgetRecommendations,
  fetchMetaRoas,
} from '@/lib/meta/api';
import type {
  MetaAnomaliesListResponse,
  MetaBudgetRecommendationsResponse,
  MetaRoasResponse,
} from '@/lib/meta/types';

interface UseMetaIntelligenceOptions {
  token: string | null;
  clientId?: string;
  days?: number;
}

export function useMetaIntelligence({ token, clientId, days = 7 }: UseMetaIntelligenceOptions) {
  const [anomalies, setAnomalies] = useState<MetaAnomaliesListResponse | null>(null);
  const [roas, setRoas] = useState<MetaRoasResponse | null>(null);
  const [recommendations, setRecommendations] = useState<MetaBudgetRecommendationsResponse | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');

  const reload = useCallback(async () => {
    if (!token) return;
    setLoading(true);
    setError('');
    try {
      const params = { client_id: clientId || undefined, days };
      const [anomalyRes, roasRes, recRes] = await Promise.all([
        fetchMetaAnomalies(token, params),
        fetchMetaRoas(token, params),
        fetchMetaBudgetRecommendations(token, params),
      ]);
      setAnomalies(anomalyRes);
      setRoas(roasRes);
      setRecommendations(recRes);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Không tải được Meta Intelligence');
    } finally {
      setLoading(false);
    }
  }, [token, clientId, days]);

  useEffect(() => {
    void reload();
  }, [reload]);

  return {
    anomalies,
    roas,
    recommendations,
    loading,
    error,
    reload,
    attribution: roas?.attribution ?? anomalies?.attribution ?? recommendations?.attribution,
  };
}
