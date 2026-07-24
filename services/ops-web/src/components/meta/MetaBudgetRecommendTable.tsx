import Link from 'next/link';
import type { MetaBudgetRecommendationsResponse } from '@/lib/meta/types';
import { fmtPct, fmtVnd } from '@/lib/meta/format';
import { metaIntelligenceEnabled } from '@/lib/meta/flags';
import { MetaBadge } from './MetaBadge';

interface Props {
  data: MetaBudgetRecommendationsResponse | null;
}

function writeRequestHref(row: MetaBudgetRecommendationsResponse['recommendations'][number]): string {
  const qs = new URLSearchParams();
  qs.set('client_id', row.client_id);
  if (row.external_campaign_id) qs.set('external_campaign_id', row.external_campaign_id);
  qs.set('daily_budget_vnd', String(row.write_request.daily_budget_vnd));
  return `/crm/campaign-writes?${qs.toString()}`;
}

export function MetaBudgetRecommendTable({ data }: Props) {
  const rows = data?.recommendations ?? [];
  const disabled = data?.disabled || !metaIntelligenceEnabled();

  return (
    <section className="meta-intelligence-section">
      <h2 style={{ margin: '0 0 0.75rem', fontSize: '1.05rem' }}>Budget recommendations (read-only)</h2>
      {disabled ? (
        <p className="meta-intelligence-disabled-banner">
          Recommendations đang tắt — bật anomaly hoặc ROAS flags.
        </p>
      ) : null}
      {!rows.length ? (
        <p className="muted">Không có đề xuất ngân sách cho cửa sổ hiện tại.</p>
      ) : (
        <div className="table-wrap">
          <table className="data-table">
            <thead>
              <tr>
                <th>Client</th>
                <th>Campaign</th>
                <th>Loại</th>
                <th>Spend TB/ngày</th>
                <th>Đề xuất</th>
                <th>Lý do</th>
                <th />
              </tr>
            </thead>
            <tbody>
              {rows.map((row) => (
                <tr key={`${row.client_id}:${row.external_campaign_id}:${row.recommendation_type}`}>
                  <td>{row.client_code ?? row.client_name ?? row.client_id.slice(0, 8)}</td>
                  <td>{row.external_campaign_name ?? row.external_campaign_id ?? '—'}</td>
                  <td>
                    <MetaBadge
                      variant={row.recommendation_type === 'decrease_budget' ? 'warn' : 'ok'}
                    >
                      {row.recommendation_type}
                    </MetaBadge>
                  </td>
                  <td>{fmtVnd(row.current_daily_spend_vnd)}</td>
                  <td>
                    {fmtVnd(row.suggested_daily_budget_vnd)}{' '}
                    <span className="muted">({fmtPct(row.change_pct)})</span>
                  </td>
                  <td>{row.rationale}</td>
                  <td>
                    <Link href={writeRequestHref(row)} className="nav-link">
                      Tạo write request
                    </Link>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </section>
  );
}
