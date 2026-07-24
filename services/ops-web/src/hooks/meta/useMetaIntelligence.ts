'use client';

import { useCallback, useEffect, useState } from 'react';
import {
  fetchMetaAnomalies,
  fetchMetaBudgetRecommendations,
  fetchMetaDailyInsights,
  fetchMetaForecast,
  fetchMetaPixels,
  fetchMetaRoas,
  fetchMetaStatAnomalies,
} from '@/lib/meta/api';
import type {
  MetaAnomaliesListResponse,
  MetaBudgetRecommendationsResponse,
  MetaDailyInsightsResponse,
  MetaForecastResponse,
  MetaPixelsListResponse,
  MetaRoasResponse,
} from '@/lib/meta/types';

interface UseMetaIntelligenceOptions {
  token: string | null;
  clientId?: string;
  days?: number;
  forecastMetric?: 'cpl' | 'spend';
}

export function useMetaIntelligence({
  token,
  clientId,
  days = 7,
  forecastMetric = 'cpl',
}: UseMetaIntelligenceOptions) {
  const [anomalies, setAnomalies] = useState<MetaAnomaliesListResponse | null>(null);
  const [statAnomalies, setStatAnomalies] = useState<MetaAnomaliesListResponse | null>(null);
  const [forecast, setForecast] = useState<MetaForecastResponse | null>(null);
  const [pixels, setPixels] = useState<MetaPixelsListResponse | null>(null);
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
      const statDays = Math.max(days, 14);
      const [anomalyRes, statRes, forecastRes, pixelRes, roasRes, recRes, insightsRes] =
        await Promise.all([
          fetchMetaAnomalies(token, params),
          fetchMetaStatAnomalies(token, { ...params, days: statDays }),
          fetchMetaForecast(token, { ...params, metric: forecastMetric, days: statDays }),
          fetchMetaPixels(token, params),
          fetchMetaRoas(token, params),
          fetchMetaBudgetRecommendations(token, params),
          fetchMetaDailyInsights(token, { ...params, level: 'adset', limit: 100 }),
        ]);
      setAnomalies(anomalyRes);
      setStatAnomalies(statRes);
      setForecast(forecastRes);
      setPixels(pixelRes);
      setRoas(roasRes);
      setRecommendations(recRes);
      setAdsetInsights(insightsRes);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Không tải được Meta Intelligence');
    } finally {
      setLoading(false);
    }
  }, [token, clientId, days, forecastMetric]);

  useEffect(() => {
    void reload();
  }, [reload]);

  return {
    anomalies,
    statAnomalies,
    forecast,
    pixels,
    roas,
    recommendations,
    adsetInsights,
    loading,
    error,
    reload,
    attribution:
      roas?.attribution ??
      anomalies?.attribution ??
      forecast?.attribution ??
      recommendations?.attribution,
  };
}
