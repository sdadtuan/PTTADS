import type { MetaForecastResponse } from '@/lib/meta/types';
import { fmtVnd } from '@/lib/meta/format';
import { metaForecastEnabled } from '@/lib/meta/flags';

interface Props {
  data: MetaForecastResponse | null;
  metric: 'cpl' | 'spend';
}

export function MetaForecastPanel({ data, metric }: Props) {
  const disabled = data?.disabled || !metaForecastEnabled();
  const projection = data?.projection ?? [];
  const historical = data?.historical ?? [];

  return (
    <section className="meta-intelligence-section">
      <h2 style={{ margin: '0 0 0.75rem', fontSize: '1.05rem' }}>
        Forecast ({metric.toUpperCase()})
      </h2>
      {disabled ? (
        <p className="meta-intelligence-disabled-banner">
          Forecast đang tắt — bật <code>NEXT_PUBLIC_PTT_META_FORECAST_ENABLED</code>.
        </p>
      ) : null}
      {data ? (
        <div className="meta-forecast-summary">
          <p className="muted" style={{ marginTop: 0 }}>
            Slope {data.slope.toFixed(4)} · Intercept {fmtVnd(data.intercept)} · Dự báo{' '}
            {projection.length} ngày
          </p>
          <div className="table-wrap">
            <table className="data-table">
              <thead>
                <tr>
                  <th>Ngày</th>
                  <th>Thực tế</th>
                  <th>Dự báo</th>
                </tr>
              </thead>
              <tbody>
                {historical.slice(-5).map((row) => (
                  <tr key={`h-${row.performance_date}`}>
                    <td>{row.performance_date}</td>
                    <td>{fmtVnd(row.value)}</td>
                    <td>—</td>
                  </tr>
                ))}
                {projection.map((row) => (
                  <tr key={`p-${row.performance_date}`}>
                    <td>{row.performance_date}</td>
                    <td>—</td>
                    <td>{fmtVnd(row.projected_value)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      ) : (
        <p className="muted">Chưa có dữ liệu forecast.</p>
      )}
    </section>
  );
}
