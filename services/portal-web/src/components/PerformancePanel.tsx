'use client';

import { useCallback, useEffect, useState } from 'react';
import { PerformanceTable } from '@/components/PerformanceTable';
import {
  fetchPerformance,
  type PerformanceChannel,
  type PerformanceListResponse,
} from '@/lib/api';
import { dateRangeEndingYesterday, fmtDate, fmtNumber, fmtVnd } from '@/lib/format';

type WindowDays = 7 | 30;
type GroupBy = 'day' | 'campaign';

export interface PerformancePanelProps {
  token: string;
  channel?: PerformanceChannel;
  title: string;
  subtitle?: string;
  hideChannelColumn?: boolean;
}

export function PerformancePanel({
  token,
  channel,
  title,
  subtitle,
  hideChannelColumn = false,
}: PerformancePanelProps) {
  const [windowDays, setWindowDays] = useState<WindowDays>(7);
  const [groupBy, setGroupBy] = useState<GroupBy>('day');
  const [performance, setPerformance] = useState<PerformanceListResponse | null>(null);
  const [loadingPerf, setLoadingPerf] = useState(true);
  const [error, setError] = useState('');

  const loadPerformance = useCallback(
    async (authToken: string, days: WindowDays, group: GroupBy) => {
      setLoadingPerf(true);
      setError('');
      const range = dateRangeEndingYesterday(days);
      try {
        const data = await fetchPerformance(authToken, {
          from: range.from,
          to: range.to,
          group_by: group,
          channel,
        });
        setPerformance(data);
      } catch (err) {
        setPerformance(null);
        setError(err instanceof Error ? err.message : 'Không tải được performance');
      } finally {
        setLoadingPerf(false);
      }
    },
    [channel],
  );

  useEffect(() => {
    if (!token) {
      return;
    }
    void loadPerformance(token, windowDays, groupBy);
  }, [token, windowDays, groupBy, loadPerformance]);

  const summary = performance?.summary;

  return (
    <section className="card" style={{ marginBottom: '1rem' }}>
      <div
        style={{
          display: 'flex',
          justifyContent: 'space-between',
          alignItems: 'center',
          gap: '1rem',
          flexWrap: 'wrap',
          marginBottom: '1rem',
        }}
      >
        <div>
          <h2 style={{ margin: 0, fontSize: '1.1rem' }}>{title}</h2>
          {performance && (
            <p className="muted" style={{ margin: '0.35rem 0 0' }}>
              {subtitle ? `${subtitle} · ` : ''}
              {fmtDate(performance.date_from)} → {fmtDate(performance.date_to)} ·{' '}
              {summary?.campaigns_tracked ?? 0} chiến dịch
            </p>
          )}
        </div>
        <div style={{ display: 'flex', gap: '0.5rem', flexWrap: 'wrap' }}>
          <button
            type="button"
            className={`btn${windowDays === 7 ? '' : ' btn-secondary'}`}
            onClick={() => setWindowDays(7)}
          >
            T-7
          </button>
          <button
            type="button"
            className={`btn${windowDays === 30 ? '' : ' btn-secondary'}`}
            onClick={() => setWindowDays(30)}
          >
            T-30
          </button>
          <button
            type="button"
            className={`btn${groupBy === 'day' ? '' : ' btn-secondary'}`}
            onClick={() => setGroupBy('day')}
          >
            Theo ngày
          </button>
          <button
            type="button"
            className={`btn${groupBy === 'campaign' ? '' : ' btn-secondary'}`}
            onClick={() => setGroupBy('campaign')}
          >
            Theo chiến dịch
          </button>
        </div>
      </div>

      {summary && (
        <div className="summary-grid">
          <div className="summary-card">
            <span className="muted">Tổng spend</span>
            <strong>{fmtVnd(summary.total_spend)}</strong>
          </div>
          <div className="summary-card">
            <span className="muted">Leads CRM</span>
            <strong>{fmtNumber(summary.total_leads_crm)}</strong>
          </div>
          <div className="summary-card">
            <span className="muted">CPL trung bình</span>
            <strong>{fmtVnd(summary.avg_cpl)}</strong>
          </div>
          <div className="summary-card">
            <span className="muted">Vượt target CPL</span>
            <strong>{fmtNumber(summary.over_target_rows)} hàng</strong>
          </div>
        </div>
      )}

      {error && <p className="error">{error}</p>}
      {loadingPerf ? (
        <p className="muted">Đang tải performance…</p>
      ) : performance ? (
        <PerformanceTable
          rows={performance.rows}
          groupBy={performance.group_by}
          hideChannel={hideChannelColumn}
        />
      ) : null}
    </section>
  );
}
