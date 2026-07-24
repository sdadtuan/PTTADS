import { fmtDateTime, fmtPct } from '@/lib/meta/format';
import type { HubAttributionMeta } from '@/lib/meta/types';

interface MetaAttributionFooterProps {
  attribution?: HubAttributionMeta | null;
}

export function MetaAttributionFooter({ attribution }: MetaAttributionFooterProps) {
  if (!attribution) return null;

  return (
    <p className="muted meta-attribution-footer" style={{ margin: '0 0 1rem', fontSize: '0.85rem' }}>
      Attribution: <strong>{attribution.attribution_model}</strong>
      {' · '}
      Chi tiêu chưa map: <strong>{fmtPct(attribution.unmapped_spend_pct)}</strong>
      {' · '}
      Spend source: {attribution.spend_source}
      {' · '}
      Through {attribution.data_freshness.through_date}
      {attribution.data_freshness.synced_at
        ? ` · synced ${fmtDateTime(attribution.data_freshness.synced_at)}`
        : ''}
    </p>
  );
}
