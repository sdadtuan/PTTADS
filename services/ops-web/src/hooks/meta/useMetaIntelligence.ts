'use client';

import { useCallback, useEffect, useState } from 'react';
import {
  fetchMetaAnomalies,
  fetchMetaBudgetRecommendations,
  fetchMetaDailyInsights,
  fetchMetaRoas,
} from '@/lib/meta/api';
import type {
  MetaAnomaliesListResponse,
  MetaBudgetRecommendationsResponse,
  MetaDailyInsightsResponse,
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
  const [adsetInsights, setAdsetInsights] = useState<MetaDailyInsightsResponse | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');

  const reload = useCallback(async () => {
    if (!token) return;
    setLoading(true);
    setError('');
    try {
      const params = { client_id: clientId || undefined, days };
      const [anomalyRes, roasRes, recRes, insightsRes] = await Promise.all([
        fetchMetaAnomalies(token, params),
        fetchMetaRoas(token, params),
        fetchMetaBudgetRecommendations(token, params),
        fetchMetaDailyInsights(token, { ...params, level: 'adset', limit: 100 }),
      ]);
      setAnomalies(anomalyRes);
      setRoas(roasRes);
      setRecommendations(recRes);
      setAdsetInsights(insightsRes);
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
    adsetInsights,
    loading,
    error,
    reload,
    attribution: roas?.attribution ?? anomalies?.attribution ?? recommendations?.attribution,
  };
}
