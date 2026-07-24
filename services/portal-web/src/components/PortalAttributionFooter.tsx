import { fmtDateTime, fmtPct } from '@/lib/format';
import type { PerformanceListResponse } from '@/lib/api';

interface PortalAttributionFooterProps {
  performance: PerformanceListResponse | null;
}

export function PortalAttributionFooter({ performance }: PortalAttributionFooterProps) {
  if (!performance?.attribution_model) {
    return null;
  }

  const unmapped = performance.unmapped_spend_pct;
  const freshness = performance.data_freshness;

  return (
    <p className="muted portal-attribution-footer" style={{ margin: '1rem 0 0', fontSize: '0.85rem' }}>
      Attribution: <strong>{performance.attribution_model}</strong>
      {unmapped != null ? (
        <>
          {' · '}
          Chi tiêu chưa map: <strong>{fmtPct(unmapped)}</strong>
        </>
      ) : null}
      {performance.spend_source ? (
        <>
          {' · '}
          Spend: {performance.spend_source}
        </>
      ) : null}
      {freshness?.through_date ? (
        <>
          {' · '}
          Through {freshness.through_date}
        </>
      ) : null}
      {freshness?.synced_at ? (
        <>
          {' · '}
          synced {fmtDateTime(freshness.synced_at)}
        </>
      ) : null}
    </p>
  );
}
