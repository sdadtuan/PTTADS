import type { MetaPixelsListResponse } from '@/lib/meta/types';
import { metaPixelsEnabled } from '@/lib/meta/flags';
import { MetaBadge } from './MetaBadge';

interface Props {
  data: MetaPixelsListResponse | null;
}

export function MetaPixelsTable({ data }: Props) {
  const rows = data?.pixels ?? [];
  const disabled = data?.disabled || !metaPixelsEnabled();

  return (
    <section className="meta-intelligence-section">
      <h2 style={{ margin: '0 0 0.75rem', fontSize: '1.05rem' }}>Multi-pixel</h2>
      {disabled ? (
        <p className="meta-intelligence-disabled-banner">
          Multi-pixel đang tắt — bật <code>NEXT_PUBLIC_PTT_META_PIXELS_ENABLED</code> và apply DDL v7.
        </p>
      ) : null}
      {data?.reason === 'meta_pixels_not_ready' ? (
        <p className="muted">{data.hint ?? './scripts/apply_pg_ddl_v7_meta_advanced.sh'}</p>
      ) : null}
      {!rows.length ? (
        <p className="muted">Chưa có pixel đăng ký — dùng API POST /meta/pixels.</p>
      ) : (
        <div className="table-wrap">
          <table className="data-table">
            <thead>
              <tr>
                <th>Pixel ID</th>
                <th>Label</th>
                <th>Primary</th>
                <th>CAPI</th>
                <th>Account</th>
              </tr>
            </thead>
            <tbody>
              {rows.map((row) => (
                <tr key={row.id}>
                  <td>{row.pixel_id}</td>
                  <td>{row.label || '—'}</td>
                  <td>{row.is_primary ? <MetaBadge variant="ok">primary</MetaBadge> : '—'}</td>
                  <td>{row.capi_enabled ? 'on' : 'off'}</td>
                  <td>{row.client_channel_account_id.slice(0, 8)}…</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </section>
  );
}
