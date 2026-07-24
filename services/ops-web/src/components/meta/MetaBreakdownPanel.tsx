'use client';

import { useEffect, useState } from 'react';
import { fetchMetaInsightsBreakdown } from '@/lib/meta/api';
import { fmtVnd } from '@/lib/meta/format';
import { metaBreakdownEnabled } from '@/lib/meta/flags';
import type { MetaInsightsBreakdownResponse } from '@/lib/meta/types';

interface Props {
  token: string;
  clientId: string;
  campaignId: string;
  dateFrom?: string;
  dateTo?: string;
}

export function MetaBreakdownPanel({ token, clientId, campaignId, dateFrom, dateTo }: Props) {
  const [data, setData] = useState<MetaInsightsBreakdownResponse | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');

  useEffect(() => {
    if (!metaBreakdownEnabled() || !campaignId) return;
    setLoading(true);
    setError('');
    void fetchMetaInsightsBreakdown(token, {
      client_id: clientId,
      campaign_id: campaignId,
      type: 'publisher_platform',
      from: dateFrom,
      to: dateTo,
    })
      .then(setData)
      .catch((err) => setError(err instanceof Error ? err.message : 'Không tải breakdown'))
      .finally(() => setLoading(false));
  }, [token, clientId, campaignId, dateFrom, dateTo]);

  if (!metaBreakdownEnabled()) {
    return (
      <p className="muted meta-breakdown-disabled">
        Breakdown đang tắt — bật <code>NEXT_PUBLIC_PTT_META_INSIGHTS_BREAKDOWN</code>.
      </p>
    );
  }

  if (loading) return <p className="muted">Đang tải breakdown…</p>;
  if (error) return <p className="error-text">{error}</p>;
  if (!data?.rows.length) return <p className="muted">Không có breakdown publisher_platform.</p>;

  return (
    <div className="meta-breakdown-panel">
      <p className="muted" style={{ marginTop: 0 }}>
        publisher_platform · spend delta{' '}
        {data.spend_delta_pct != null ? `${data.spend_delta_pct.toFixed(1)}%` : '—'} vs campaign total
      </p>
      <div className="table-wrap">
        <table className="data-table">
          <thead>
            <tr>
              <th>Platform</th>
              <th>Ngày</th>
              <th>Spend</th>
              <th>Clicks</th>
              <th>Leads (platform)</th>
            </tr>
          </thead>
          <tbody>
            {data.rows.map((row) => (
              <tr key={`${row.performance_date}:${row.breakdown_value}`}>
                <td>{row.breakdown_value}</td>
                <td>{row.performance_date}</td>
                <td>{fmtVnd(row.spend)}</td>
                <td>{row.clicks}</td>
                <td>{row.leads_platform}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}
