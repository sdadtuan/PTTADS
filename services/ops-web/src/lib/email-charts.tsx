'use client';

/** Lightweight SVG sparkline for email engagement (Wave 3 E-12). */

export interface EmailSparklineProps {
  data: number[];
  width?: number;
  height?: number;
  className?: string;
  label?: string;
}

export function EmailSparkline({
  data,
  width = 160,
  height = 40,
  className = 'email-sparkline',
  label,
}: EmailSparklineProps) {
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

export function EmailEngagementChart({
  points,
  days,
}: {
  points: Array<{ date: string; opens: number; clicks: number }>;
  days: number;
}) {
  if (points.length === 0) {
    return (
      <details className="email-chart-fallback">
        <summary className="muted">Chưa có dữ liệu engagement ({days} ngày)</summary>
      </details>
    );
  }
  const opens = points.map((p) => p.opens);
  const clicks = points.map((p) => p.clicks);
  return (
    <div className="email-sparkline-grid">
      <div>
        <p className="muted" style={{ margin: '0 0 0.25rem' }}>
          Opens
        </p>
        <EmailSparkline data={opens} label={`Opens ${days} ngày`} />
      </div>
      <div>
        <p className="muted" style={{ margin: '0 0 0.25rem' }}>
          Clicks
        </p>
        <EmailSparkline data={clicks} label={`Clicks ${days} ngày`} />
      </div>
    </div>
  );
}
