'use client';

import Link from 'next/link';
import { useEffect, useState } from 'react';
import { portalEmailDashboard, type PortalEmailDashboard } from '@/lib/api';

interface EmailWidgetsPanelProps {
  token: string;
}

export function EmailWidgetsPanel({ token }: EmailWidgetsPanelProps) {
  const [data, setData] = useState<PortalEmailDashboard | null>(null);
  const [error, setError] = useState('');

  useEffect(() => {
    portalEmailDashboard(token)
      .then(setData)
      .catch((err) => setError(err instanceof Error ? err.message : 'Lỗi tải email dashboard'));
  }, [token]);

  if (error) return <p className="error">{error}</p>;
  if (!data) return <p className="muted">Đang tải email metrics…</p>;

  return (
    <>
      <div className="seo-widgets-grid" style={{ marginBottom: '1rem' }}>
        <div className="seo-widget-card">
          <p className="seo-widget-label">Pending approval</p>
          <strong className="seo-widget-value">{data.pending_approvals}</strong>
        </div>
        <div className="seo-widget-card">
          <p className="seo-widget-label">Sent (28d)</p>
          <strong className="seo-widget-value">{data.campaigns_sent_28d.toLocaleString()}</strong>
        </div>
        <div className="seo-widget-card seo-widget-card--ok">
          <p className="seo-widget-label">Open rate</p>
          <strong className="seo-widget-value">{data.open_rate_pct}%</strong>
        </div>
        <div className="seo-widget-card seo-widget-card--featured">
          <p className="seo-widget-label">Revenue attrib.</p>
          <strong className="seo-widget-value">{data.revenue_attrib}</strong>
        </div>
      </div>
      <div className="card">
        <h2 style={{ marginTop: 0, fontSize: '1.1rem' }}>Recent campaigns</h2>
        {data.recent_campaigns.length === 0 ? (
          <p className="muted">Chưa có campaign.</p>
        ) : (
          <ul style={{ margin: 0, paddingLeft: '1.2rem' }}>
            {data.recent_campaigns.map((c) => (
              <li key={c.id} style={{ marginBottom: '0.35rem' }}>
                <Link href={`/email/campaigns/${c.id}`}>{c.name}</Link>
                {' · '}
                <span className="badge">{c.status}</span>
                {c.audience_count != null ? ` (${c.audience_count})` : ''}
              </li>
            ))}
          </ul>
        )}
      </div>
    </>
  );
}
