import type { MetaAnomaliesListResponse } from '@/lib/meta/types';
import { fmtPct, fmtVnd } from '@/lib/meta/format';
import { metaAnomalyEnabled } from '@/lib/meta/flags';
import { MetaBadge } from './MetaBadge';

interface Props {
  data: MetaAnomaliesListResponse | null;
}

export function MetaAnomaliesTable({ data }: Props) {
  const rows = data?.anomalies ?? [];
  const disabled = data?.disabled || !metaAnomalyEnabled();

  return (
    <section className="meta-intelligence-section">
      <h2 style={{ margin: '0 0 0.75rem', fontSize: '1.05rem' }}>Anomalies</h2>
      {disabled ? (
        <p className="meta-intelligence-disabled-banner">
          Anomaly detection đang tắt — bật <code>NEXT_PUBLIC_PTT_META_ANOMALY_ENABLED</code>.
        </p>
      ) : null}
      {!rows.length ? (
        <p className="muted">Không có anomaly trong cửa sổ đã chọn.</p>
      ) : (
        <div className="table-wrap">
          <table className="data-table">
            <thead>
              <tr>
                <th>Loại</th>
                <th>Client</th>
                <th>Campaign</th>
                <th>Spike</th>
                <th>Metric</th>
                <th>Ngày</th>
              </tr>
            </thead>
            <tbody>
              {rows.map((row) => (
                <tr key={row.id}>
                    <td>
                    <MetaBadge variant={row.alert_type === 'roas_low' ? 'warn' : 'error'}>
                      {row.alert_type}
                    </MetaBadge>
                  </td>
                  <td>{row.client_code ?? row.client_id.slice(0, 8)}</td>
                  <td>{row.external_campaign_id ?? '—'}</td>
                  <td>{row.spike_pct != null ? fmtPct(row.spike_pct) : '—'}</td>
                  <td>
                    {row.alert_type === 'roas_low'
                      ? row.metric_value?.toFixed(2) ?? '—'
                      : fmtVnd(row.metric_value)}
                  </td>
                  <td>{row.performance_date ?? '—'}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </section>
  );
}
