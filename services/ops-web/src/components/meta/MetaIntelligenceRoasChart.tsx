import type { MetaRoasSeriesPoint } from '@/lib/meta/types';

interface Props {
  series: MetaRoasSeriesPoint[];
  disabled?: boolean;
}

export function MetaIntelligenceRoasChart({ series, disabled }: Props) {
  const points = series.filter((p) => !p.roas_stub && p.roas != null);
  const maxRoas = points.reduce((max, p) => Math.max(max, p.roas ?? 0), 0);

  return (
    <div className="meta-intelligence-roas-chart">
      <h3 style={{ margin: '0 0 0.75rem', fontSize: '0.95rem' }}>ROAS theo ngày</h3>
      {disabled ? (
        <p className="muted">Biểu đồ ROAS ẩn khi feature flag tắt.</p>
      ) : !points.length ? (
        <p className="muted">Chưa có ROAS thật (conversion value) trong cửa sổ đã chọn.</p>
      ) : (
        <div className="meta-roas-chart-bars" role="img" aria-label="ROAS daily series chart">
          {points.map((point) => {
            const heightPct = maxRoas > 0 ? Math.round(((point.roas ?? 0) / maxRoas) * 100) : 0;
            return (
              <div key={point.performance_date} className="meta-roas-chart-bar-wrap">
                <div
                  className="meta-roas-chart-bar"
                  style={{ height: `${Math.max(heightPct, 4)}%` }}
                  title={`${point.performance_date}: ROAS ${point.roas?.toFixed(2)}`}
                />
                <span className="meta-roas-chart-label">{point.performance_date.slice(5)}</span>
                <span className="meta-roas-chart-value">{point.roas?.toFixed(2)}</span>
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
}
