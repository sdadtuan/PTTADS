'use client';

import Link from 'next/link';
import { useCallback, useEffect, useState } from 'react';
import { portalSeoWidgets, type PortalSeoWidgetMetric, type PortalSeoWidgetsResponse } from '@/lib/api';
import { fmtNumber } from '@/lib/format';

function fmtWidgetValue(value: unknown, unit?: string): string {
  if (value == null || value === '') {
    return '—';
  }
  if (typeof value === 'number') {
    const formatted = fmtNumber(value);
    return unit === '%' ? `${formatted}%` : formatted;
  }
  return String(value);
}

function Sparkline({ data }: { data: number[] }) {
  if (!data.length) {
    return null;
  }
  const width = 128;
  const height = 36;
  const pad = 3;
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
    <svg width={width} height={height} className="seo-sparkline" aria-hidden viewBox={`0 0 ${width} ${height}`}>
      <polyline fill="none" stroke="currentColor" strokeWidth="2" strokeLinejoin="round" points={points} />
    </svg>
  );
}

interface WidgetCardProps {
  metric: PortalSeoWidgetMetric;
  featured?: boolean;
  href?: string;
  tone?: 'default' | 'warn' | 'ok';
}

function WidgetCard({ metric, featured = false, href, tone = 'default' }: WidgetCardProps) {
  const body = (
    <div className={`seo-widget-card${featured ? ' seo-widget-card--featured' : ''} seo-widget-card--${tone}`}>
      <p className="seo-widget-label">{metric.label}</p>
      <strong className="seo-widget-value">{fmtWidgetValue(metric.value, metric.unit)}</strong>
      {metric.sparkline && metric.sparkline.length > 0 ? <Sparkline data={metric.sparkline} /> : null}
    </div>
  );

  if (href) {
    return (
      <Link href={href} className="seo-widget-link">
        {body}
      </Link>
    );
  }
  return body;
}

export interface SeoWidgetsPanelProps {
  token: string;
}

export function SeoWidgetsPanel({ token }: SeoWidgetsPanelProps) {
  const [data, setData] = useState<PortalSeoWidgetsResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');

  const load = useCallback(async (authToken: string) => {
    setLoading(true);
    setError('');
    try {
      const widgets = await portalSeoWidgets(authToken);
      setData(widgets);
    } catch (err) {
      setData(null);
      setError(err instanceof Error ? err.message : 'Không tải được SEO widgets');
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    if (!token) {
      return;
    }
    void load(token);
  }, [token, load]);

  const widgets = data?.widgets ?? {};
  const critical = Number(widgets.critical_issues?.value ?? 0);
  const pending = Number(widgets.content_in_review?.value ?? 0);
  const alerts = Number(widgets.open_alerts?.value ?? 0);

  return (
    <section className="card" data-testid="seo-widgets-panel">
      <div className="seo-widgets-head">
        <div>
          <h2 style={{ margin: 0 }}>SEO/AEO KPI</h2>
          <p className="muted" style={{ margin: '0.35rem 0 0' }}>
            Cập nhật từ Search Console, AEO và pipeline nội dung
          </p>
        </div>
        <button type="button" className="btn btn-secondary btn-sm" disabled={loading} onClick={() => void load(token)}>
          {loading ? 'Đang tải…' : 'Làm mới'}
        </button>
      </div>

      {error ? <p className="error">{error}</p> : null}

      {loading && !data ? <p className="muted">Đang tải widgets…</p> : null}

      {!loading && data ? (
        <div className="seo-widgets-grid">
          {widgets.gsc_clicks ? (
            <WidgetCard metric={widgets.gsc_clicks} featured tone="ok" href="/seo/reports?tab=seo" />
          ) : null}
          {widgets.gsc_impressions ? (
            <WidgetCard metric={widgets.gsc_impressions} href="/seo/reports?tab=seo" />
          ) : null}
          {widgets.aeo_coverage ? (
            <WidgetCard metric={widgets.aeo_coverage} tone="ok" href="/seo/reports?tab=aeo" />
          ) : null}
          {widgets.critical_issues ? (
            <WidgetCard
              metric={widgets.critical_issues}
              href={critical > 0 ? '/seo/reports?tab=technical' : '/seo/reports?tab=technical'}
              tone={critical > 0 ? 'warn' : 'default'}
            />
          ) : null}
          {widgets.open_alerts ? (
            <WidgetCard
              metric={widgets.open_alerts}
              href={alerts > 0 ? '/seo/reports?tab=executive' : '/seo/reports?tab=executive'}
              tone={alerts > 0 ? 'warn' : 'default'}
            />
          ) : null}
          {widgets.content_in_review ? (
            <WidgetCard
              metric={widgets.content_in_review}
              href={pending > 0 ? '/seo/content' : undefined}
              tone={pending > 0 ? 'warn' : 'default'}
            />
          ) : null}
        </div>
      ) : null}

      <p style={{ marginTop: '1rem', marginBottom: 0 }}>
        <Link href="/seo/reports" className="nav-link">
          Xem báo cáo chi tiết →
        </Link>
        {' · '}
        <Link href="/seo/content" className="nav-link">
          Duyệt nội dung →
        </Link>
      </p>
    </section>
  );
}
