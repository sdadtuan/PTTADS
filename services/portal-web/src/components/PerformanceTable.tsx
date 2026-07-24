import type { PerformanceRow } from '@/lib/api';
import { fmtDate, fmtDeltaPct, fmtDeltaVnd, fmtNumber, fmtVnd } from '@/lib/format';

interface PerformanceTableProps {
  rows: PerformanceRow[];
  groupBy: 'day' | 'campaign';
  hideChannel?: boolean;
}

function isOverTarget(row: PerformanceRow): boolean {
  return row.cpl != null && row.target_cpl_vnd != null && row.cpl > row.target_cpl_vnd;
}

export function PerformanceTable({ rows, groupBy, hideChannel = false }: PerformanceTableProps) {
  if (rows.length === 0) {
    return <p className="muted">Không có dữ liệu performance trong khoảng thời gian đã chọn.</p>;
  }

  return (
    <div style={{ overflowX: 'auto' }}>
      <table className="perf-table">
        <thead>
          <tr>
            {groupBy === 'day' && <th>Ngày</th>}
            {!hideChannel && <th>Kênh</th>}
            <th>Chiến dịch</th>
            <th>Map</th>
            <th className="num">Spend</th>
            <th className="num">Leads CRM</th>
            <th className="num">CPL</th>
            <th className="num">Target CPL</th>
            <th className="num">CPL Δ</th>
            <th className="num">ROAS</th>
          </tr>
        </thead>
        <tbody>
          {rows.map((row, idx) => {
            const key = `${row.performance_date ?? 'agg'}-${row.external_campaign_id ?? idx}`;
            const overTarget = isOverTarget(row);
            const deltaOver = row.cpl_delta_vnd != null && row.cpl_delta_vnd > 0;
            return (
              <tr key={key}>
                {groupBy === 'day' && <td>{fmtDate(row.performance_date)}</td>}
                {!hideChannel && (
                  <td>
                    <span className="channel-badge">{row.channel === 'google' ? 'Google' : 'Meta'}</span>
                  </td>
                )}
                <td>
                  <div>{row.external_campaign_name ?? row.external_campaign_id ?? '—'}</div>
                  {row.external_campaign_id && (
                    <div className="muted" style={{ fontSize: '0.75rem' }}>
                      {row.external_campaign_id}
                    </div>
                  )}
                </td>
                <td>
                  {row.hub_mapped ? (
                    <span className="map-badge map-badge--ok" title="Đã map Hub campaign">
                      Mapped
                    </span>
                  ) : (
                    <span className="map-badge map-badge--warn" title="Chưa map Hub — CPL có thể thiếu chính xác">
                      Chưa map
                    </span>
                  )}
                </td>
                <td className="num">{fmtVnd(row.spend)}</td>
                <td className="num">{fmtNumber(row.leads_crm)}</td>
                <td className={`num${overTarget ? ' over-target' : ''}`}>{fmtVnd(row.cpl)}</td>
                <td className="num">{fmtVnd(row.target_cpl_vnd)}</td>
                <td className={`num${deltaOver || overTarget ? ' over-target' : ''}`}>
                  {row.cpl_delta_vnd != null ? (
                    <>
                      {fmtDeltaVnd(row.cpl_delta_vnd)}
                      {row.cpl_delta_pct != null ? (
                        <span className="muted" style={{ display: 'block', fontSize: '0.75rem' }}>
                          ({fmtDeltaPct(row.cpl_delta_pct)})
                        </span>
                      ) : null}
                    </>
                  ) : (
                    '—'
                  )}
                </td>
                <td className="num">
                  {row.roas_stub ? (
                    <span className="muted" title="Chưa có conversion value">
                      —
                    </span>
                  ) : (
                    (row.roas?.toFixed(2) ?? '—')
                  )}
                </td>
              </tr>
            );
          })}
        </tbody>
      </table>
    </div>
  );
}
