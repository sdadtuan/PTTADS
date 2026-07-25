'use client';

export interface SeoGscTrendPoint {
  date: string;
  clicks: number;
  impressions: number;
}

export function SeoSparkline({
  data,
  width = 200,
  height = 48,
  className = 'seo-sparkline',
  label,
}: {
  data: number[];
  width?: number;
  height?: number;
  className?: string;
  label?: string;
}) {
  if (!data.length) {
    return <span className="muted">—</span>;
  }
  const pad = 4;
  const max = Math.max(...data, 1);
  const min = Math.min(...data, 0);
  const range = max - min || 1;
  const points = data
    .map((value, index) => {
      const x = pad + (index / Math.max(data.length - 1, 1)) * (width - pad * 2);
      const y = height - pad - ((value - min) / range) * (height - pad * 2);
      return `${x},${y}`;
    })
    .join(' ');

  return (
    <svg
      width={width}
      height={height}
      className={className}
      viewBox={`0 0 ${width} ${height}`}
      role={label ? 'img' : 'presentation'}
      aria-label={label}
    >
      <polyline fill="none" stroke="currentColor" strokeWidth="2" strokeLinejoin="round" points={points} />
    </svg>
  );
}

export function SeoGscTrendChart({
  points,
  days,
}: {
  points: SeoGscTrendPoint[];
  days: number;
}) {
  if (!points.length) {
    return (
      <p className="muted" style={{ margin: 0 }}>
        Chưa có dữ liệu GSC ({days} ngày) — kết nối OAuth và chạy sync.
      </p>
    );
  }
  const clicks = points.map((p) => p.clicks);
  const impressions = points.map((p) => p.impressions);
  const totalClicks = clicks.reduce((s, v) => s + v, 0);
  const totalImpressions = impressions.reduce((s, v) => s + v, 0);
  return (
    <div style={{ display: 'grid', gap: '1rem', gridTemplateColumns: 'repeat(auto-fit, minmax(200px, 1fr))' }}>
      <div>
        <p className="muted" style={{ margin: '0 0 0.35rem' }}>
          GSC clicks ({days}d) · {totalClicks.toLocaleString()}
        </p>
        <SeoSparkline data={clicks} width={240} height={52} label={`GSC clicks ${days} days`} />
      </div>
      <div>
        <p className="muted" style={{ margin: '0 0 0.35rem' }}>
          Impressions · {totalImpressions.toLocaleString()}
        </p>
        <SeoSparkline data={impressions} width={240} height={52} label={`GSC impressions ${days} days`} />
      </div>
    </div>
  );
}
