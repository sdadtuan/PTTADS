import type { TrackingHealthGlobal } from '@/lib/meta/types';
import { fmtMs, fmtPct } from '@/lib/meta/format';

interface Props {
  global: TrackingHealthGlobal;
  windowDays: number;
  disabled?: boolean;
}

export function MetaTrackingKpiGrid({ global, windowDays, disabled }: Props) {
  const cards = [
    { label: 'Sent', value: String(global.sent), hint: `${windowDays}d` },
    { label: 'Failed', value: String(global.failed), hint: fmtPct(global.fail_rate_pct) },
    { label: 'Skipped', value: String(global.skipped), hint: 'events' },
    { label: 'Pending', value: String(global.pending), hint: 'queue' },
    { label: 'Match hint', value: fmtPct(global.match_hint_pct), hint: 'attribution' },
    { label: 'Avg latency', value: fmtMs(global.avg_latency_ms), hint: 'sent events' },
  ];

  return (
    <div className="meta-tracking-kpi-grid">
      {disabled ? (
        <p className="meta-tracking-disabled-banner">
          Meta Tracking đang tắt — bật <code>PTT_META_TRACKING_ENABLED</code> trên API.
        </p>
      ) : null}
      {cards.map((card) => (
        <div key={card.label} className="meta-tracking-kpi-card">
          <p className="muted meta-tracking-kpi-label">{card.label}</p>
          <strong className="meta-tracking-kpi-value">{card.value}</strong>
          <span className="muted meta-tracking-kpi-hint">{card.hint}</span>
        </div>
      ))}
    </div>
  );
}
