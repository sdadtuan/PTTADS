import type { MetaDailyInsightsResponse } from '@/lib/meta/types';
import { fmtVnd } from '@/lib/meta/format';

interface Props {
  data: MetaDailyInsightsResponse | null;
}

export function MetaAdsetInsightsTable({ data }: Props) {
  const rows = data?.rows ?? [];
  const level = data?.level ?? 'adset';

  return (
    <section className="meta-intelligence-section">
      <h2 style={{ margin: '0 0 0.75rem', fontSize: '1.05rem' }}>
        Insights daily ({level})
      </h2>
      {data?.disabled ? (
        <p className="meta-intelligence-disabled-banner">
          Adset insights chưa bật — set <code>PTT_META_INSIGHTS_LEVEL=adset</code> và apply DDL v6.
          {data.hint ? ` ${data.hint}` : ''}
        </p>
      ) : null}
      {!rows.length ? (
        <p className="muted">Không có rows {level} trong cửa sổ đã chọn.</p>
      ) : (
        <div className="table-wrap">
          <table className="data-table">
            <thead>
              <tr>
                <th>Ngày</th>
                <th>Campaign</th>
                {level === 'adset' ? <th>Ad set</th> : null}
                <th>Spend</th>
                <th>Leads</th>
                <th>Conv. value</th>
              </tr>
            </thead>
            <tbody>
              {rows.slice(0, 50).map((row) => (
                <tr key={`${row.performance_date}:${row.external_campaign_id}:${row.external_adset_id ?? ''}`}>
                  <td>{row.performance_date}</td>
                  <td>{row.external_campaign_name ?? row.external_campaign_id ?? '—'}</td>
                  {level === 'adset' ? (
                    <td>{row.external_adset_name ?? row.external_adset_id ?? '—'}</td>
                  ) : null}
                  <td>{fmtVnd(row.spend)}</td>
                  <td>{row.leads_crm}</td>
                  <td>{fmtVnd(row.conversion_value)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </section>
  );
}
