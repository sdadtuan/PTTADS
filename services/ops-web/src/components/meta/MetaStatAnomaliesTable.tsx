import type { MetaAnomaliesListResponse } from '@/lib/meta/types';
import { fmtVnd } from '@/lib/meta/format';
import { metaAnomalyStatEnabled } from '@/lib/meta/flags';
import { MetaBadge } from './MetaBadge';

interface Props {
  data: MetaAnomaliesListResponse | null;
}

export function MetaStatAnomaliesTable({ data }: Props) {
  const rows = data?.anomalies ?? [];
  const disabled = data?.disabled || !metaAnomalyStatEnabled();

  return (
    <section className="meta-intelligence-section">
      <h2 style={{ margin: '0 0 0.75rem', fontSize: '1.05rem' }}>Stat anomalies (z-score)</h2>
      {disabled ? (
        <p className="meta-intelligence-disabled-banner">
          Z-score anomaly đang tắt — bật <code>NEXT_PUBLIC_PTT_META_ANOMALY_STAT_ENABLED</code>.
        </p>
      ) : null}
      {!rows.length ? (
        <p className="muted">Không có stat anomaly trong cửa sổ đã chọn.</p>
      ) : (
        <div className="table-wrap">
          <table className="data-table">
            <thead>
              <tr>
                <th>Loại</th>
                <th>Client</th>
                <th>Campaign</th>
                <th>z-score</th>
                <th>Metric</th>
                <th>Ngày</th>
              </tr>
            </thead>
            <tbody>
              {rows.map((row) => (
                <tr key={row.id}>
                  <td>
                    <MetaBadge variant="error">{row.alert_type}</MetaBadge>
                  </td>
                  <td>{row.client_code ?? row.client_id.slice(0, 8)}</td>
                  <td>{row.external_campaign_id ?? '—'}</td>
                  <td>{row.z_score?.toFixed(2) ?? '—'}</td>
                  <td>{fmtVnd(row.metric_value)}</td>
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
