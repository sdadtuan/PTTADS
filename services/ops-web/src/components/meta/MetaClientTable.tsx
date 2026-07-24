import Link from 'next/link';
import { fmtVnd } from '@/lib/meta/format';
import type { FacebookHubClient } from '@/lib/meta/types';

interface MetaClientTableProps {
  rows: FacebookHubClient[];
  loading: boolean;
}

export function MetaClientTable({ rows, loading }: MetaClientTableProps) {
  return (
    <div className="card" id="clients-table">
      <h2 style={{ marginTop: 0, fontSize: '1.1rem' }}>Clients overview</h2>
      <div style={{ overflowX: 'auto' }}>
        <table className="perf-table">
          <thead>
            <tr>
              <th>Client</th>
              <th>Status</th>
              <th>Spend</th>
              <th>Leads</th>
              <th>CPL</th>
              <th>Campaigns</th>
              <th>Chưa map</th>
              <th>Vượt target</th>
              <th>Token</th>
            </tr>
          </thead>
          <tbody>
            {rows.map((c) => (
              <tr key={c.id}>
                <td>
                  <Link href={`/agency/clients/${c.id}`} className="nav-link">
                    {c.code || c.name}
                  </Link>
                </td>
                <td>{c.status ?? '—'}</td>
                <td>{fmtVnd(c.spend)}</td>
                <td>{c.leads_crm}</td>
                <td>{fmtVnd(c.cpl)}</td>
                <td>{c.campaigns}</td>
                <td>{c.unmapped_campaigns ?? 0}</td>
                <td>{c.over_target_rows}</td>
                <td>{c.token_status ?? (c.meta_has_token ? 'ok' : '—')}</td>
              </tr>
            ))}
            {!loading && rows.length === 0 ? (
              <tr>
                <td colSpan={9} className="muted">
                  Không có dữ liệu Meta cho bộ lọc đã chọn
                </td>
              </tr>
            ) : null}
          </tbody>
        </table>
      </div>
    </div>
  );
}
