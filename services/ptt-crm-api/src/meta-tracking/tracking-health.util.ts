import { TrackingHealthGlobal } from './meta-tracking.types';

export function roundPct(value: number): number {
  return Math.round(value * 10) / 10;
}

export function computeTrackingHealthGlobal(params: {
  byStatus: Record<string, number>;
  avgLatencyMs: number | null;
}): TrackingHealthGlobal {
  const sent = params.byStatus.sent ?? 0;
  const failed = params.byStatus.failed ?? 0;
  const skipped = params.byStatus.skipped ?? 0;
  const pending = params.byStatus.pending ?? 0;
  const attempted = sent + failed;
  const failRate = attempted > 0 ? roundPct((failed / attempted) * 100) : 0;
  const matchHint = attempted > 0 ? roundPct((sent / attempted) * 100) : null;
  return {
    sent,
    failed,
    skipped,
    pending,
    fail_rate_pct: failRate,
    match_hint_pct: matchHint,
    avg_latency_ms:
      params.avgLatencyMs != null && Number.isFinite(params.avgLatencyMs)
        ? Math.round(params.avgLatencyMs)
        : null,
  };
}

export function emptyTrackingHealthGlobal(): TrackingHealthGlobal {
  return {
    sent: 0,
    failed: 0,
    skipped: 0,
    pending: 0,
    fail_rate_pct: 0,
    match_hint_pct: null,
    avg_latency_ms: null,
  };
}
