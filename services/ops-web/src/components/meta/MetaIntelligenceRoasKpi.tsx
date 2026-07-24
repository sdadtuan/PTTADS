import type { MetaRoasResponse } from '@/lib/meta/types';
import { fmtPct, fmtVnd } from '@/lib/meta/format';
import { metaRoasEnabled } from '@/lib/meta/flags';

interface Props {
  roas: MetaRoasResponse | null;
  days: number;
}

export function MetaIntelligenceRoasKpi({ roas, days }: Props) {
  const disabled = roas?.disabled || !metaRoasEnabled();
  const summary = roas?.summary;

  const cards = [
    {
      label: 'ROAS trung bình',
      value: summary?.roas_stub ? '— (stub)' : summary?.avg_roas != null ? summary.avg_roas.toFixed(2) : '—',
      hint: `${days}d`,
    },
    {
      label: 'Spend',
      value: fmtVnd(summary?.total_spend ?? 0),
      hint: 'VND',
    },
    {
      label: 'Conversion value',
      value: fmtVnd(summary?.total_conversion_value ?? 0),
      hint: 'CRM deals',
    },
    {
      label: 'Ngày có dữ liệu',
      value: String(roas?.series.length ?? 0),
      hint: roas ? `${roas.date_from} → ${roas.date_to}` : '',
    },
  ];

  return (
    <section className="meta-intelligence-section">
      <h2 style={{ margin: '0 0 0.75rem', fontSize: '1.05rem' }}>ROAS KPI</h2>
      {disabled ? (
        <p className="meta-intelligence-disabled-banner">
          ROAS Intelligence đang tắt — bật <code>NEXT_PUBLIC_PTT_META_ROAS_ENABLED</code>.
        </p>
      ) : null}
      <div className="meta-tracking-kpi-grid">
        {cards.map((card) => (
          <div key={card.label} className="meta-tracking-kpi-card">
            <p className="muted meta-tracking-kpi-label">{card.label}</p>
            <strong className="meta-tracking-kpi-value">{card.value}</strong>
            <span className="muted meta-tracking-kpi-hint">{card.hint}</span>
          </div>
        ))}
      </div>
      {summary && !summary.roas_stub && summary.avg_roas != null ? (
        <p className="muted" style={{ marginTop: '0.75rem', fontSize: '0.85rem' }}>
          ROAS = conversion_value / spend · ratio {summary.avg_roas.toFixed(2)}
        </p>
      ) : null}
    </section>
  );
}
