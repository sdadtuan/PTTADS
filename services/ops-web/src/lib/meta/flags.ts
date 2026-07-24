/** Feature flags for Meta Enterprise B8/B9 UI. */

export function metaAlertsEnabled(): boolean {
  const raw = (process.env.NEXT_PUBLIC_PTT_META_ALERTS_ENABLED ?? '0').trim().toLowerCase();
  return ['1', 'true', 'yes', 'on'].includes(raw);
}

export function metaTrackingEnabled(): boolean {
  return ['1', 'true', 'yes', 'on'].includes(
    (process.env.NEXT_PUBLIC_PTT_META_TRACKING_ENABLED ?? '0').trim().toLowerCase(),
  );
}

export function metaAnomalyEnabled(): boolean {
  return ['1', 'true', 'yes', 'on'].includes(
    (process.env.NEXT_PUBLIC_PTT_META_ANOMALY_ENABLED ?? '0').trim().toLowerCase(),
  );
}

export function metaRoasEnabled(): boolean {
  return ['1', 'true', 'yes', 'on'].includes(
    (process.env.NEXT_PUBLIC_PTT_META_ROAS_ENABLED ?? '0').trim().toLowerCase(),
  );
}

export function metaIntelligenceEnabled(): boolean {
  return metaAnomalyEnabled() || metaRoasEnabled();
}

export function metaBreakdownEnabled(): boolean {
  return ['1', 'true', 'yes', 'on'].includes(
    (process.env.NEXT_PUBLIC_PTT_META_INSIGHTS_BREAKDOWN ?? '0').trim().toLowerCase(),
  );
}
