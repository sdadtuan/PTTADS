'use client';

import Link from 'next/link';
import { useCallback, useEffect, useState } from 'react';
import { PortalPageShell } from '@/components/PortalPageShell';
import {
  fetchPortalNotifications,
  markAllPortalNotificationsRead,
  markPortalNotificationRead,
  type PortalNotificationRow,
} from '@/lib/api';

function formatWhen(iso: string): string {
  try {
    return new Date(iso).toLocaleString('vi-VN', {
      day: '2-digit',
      month: '2-digit',
      year: 'numeric',
      hour: '2-digit',
      minute: '2-digit',
    });
  } catch {
    return iso;
  }
}

function categoryLabel(category: string): string {
  switch (category) {
    case 'creative_pending':
      return 'Creative';
    case 'email_pending':
      return 'Email';
    case 'seo_pending':
      return 'SEO';
    case 'campaign_milestone':
      return 'Milestone';
    default:
      return 'Hệ thống';
  }
}

export default function NotificationsPage() {
  return (
    <PortalPageShell>
      {({ token }) => <NotificationsContent token={token} />}
    </PortalPageShell>
  );
}

function NotificationsContent({ token }: { token: string }) {
  const [rows, setRows] = useState<PortalNotificationRow[]>([]);
  const [unread, setUnread] = useState(0);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [unreadOnly, setUnreadOnly] = useState(false);
  const [tableReady, setTableReady] = useState(true);

  const load = useCallback(async () => {
    setLoading(true);
    setError('');
    try {
      const data = await fetchPortalNotifications(token, { unreadOnly, limit: 50 });
      setRows(data.rows);
      setUnread(data.unread);
      setTableReady(data.table_ready);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Không tải được thông báo');
    } finally {
      setLoading(false);
    }
  }, [token, unreadOnly]);

  useEffect(() => {
    void load();
  }, [load]);

  async function handleMarkRead(row: PortalNotificationRow) {
    if (row.read) return;
    await markPortalNotificationRead(token, row.id);
    await load();
  }

  async function handleMarkAllRead() {
    await markAllPortalNotificationsRead(token);
    await load();
  }

  return (
    <>
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
          <h2 style={{ margin: 0, fontSize: '1.15rem' }}>Trung tâm thông báo</h2>
          <p className="muted" style={{ margin: '0.35rem 0 0' }}>
            {unread > 0 ? `${unread} chưa đọc` : 'Tất cả đã đọc'}
          </p>
        </div>
        <div style={{ display: 'flex', gap: '0.5rem', flexWrap: 'wrap' }}>
          <button
            type="button"
            className={`btn${unreadOnly ? '' : ' btn-secondary'}`}
            onClick={() => setUnreadOnly(false)}
          >
            Tất cả
          </button>
          <button
            type="button"
            className={`btn${unreadOnly ? ' btn-secondary' : ''}`}
            onClick={() => setUnreadOnly(true)}
          >
            Chưa đọc
          </button>
          {unread > 0 ? (
            <button type="button" className="btn btn-secondary" onClick={() => void handleMarkAllRead()}>
              Đánh dấu tất cả đã đọc
            </button>
          ) : null}
        </div>
      </div>

      {!tableReady ? (
        <p className="muted">
          Bảng thông báo chưa sẵn sàng trên môi trường này — liên hệ AM nếu bạn không thấy thông báo sau khi
          AM gửi creative.
        </p>
      ) : null}

      {error ? <p className="error">{error}</p> : null}
      {loading ? (
        <p className="muted">Đang tải…</p>
      ) : rows.length === 0 ? (
        <p className="muted">Không có thông báo{unreadOnly ? ' chưa đọc' : ''}.</p>
      ) : (
        <ul style={{ listStyle: 'none', margin: 0, padding: 0, display: 'grid', gap: '0.75rem' }}>
          {rows.map((row) => (
            <li
              key={row.id}
              className="card"
              style={{
                padding: '1rem 1.15rem',
                opacity: row.read ? 0.85 : 1,
                borderLeft: row.read ? undefined : '3px solid var(--accent, #2563eb)',
              }}
            >
              <div style={{ display: 'flex', justifyContent: 'space-between', gap: '1rem', flexWrap: 'wrap' }}>
                <div>
                  <p className="badge" style={{ marginBottom: '0.35rem' }}>
                    {categoryLabel(row.category)}
                  </p>
                  <p style={{ margin: 0, fontWeight: row.read ? 500 : 600 }}>{row.title}</p>
                  {row.body ? (
                    <p className="muted" style={{ margin: '0.35rem 0 0' }}>
                      {row.body}
                    </p>
                  ) : null}
                  <p className="muted" style={{ margin: '0.5rem 0 0', fontSize: '0.85rem' }}>
                    {formatWhen(row.created_at)}
                  </p>
                </div>
                <div style={{ display: 'flex', gap: '0.5rem', alignItems: 'flex-start' }}>
                  {row.link_url ? (
                    <Link href={row.link_url} className="btn btn-secondary">
                      Mở
                    </Link>
                  ) : null}
                  {!row.read ? (
                    <button
                      type="button"
                      className="btn"
                      onClick={() => void handleMarkRead(row)}
                    >
                      Đã đọc
                    </button>
                  ) : null}
                </div>
              </div>
            </li>
          ))}
        </ul>
      )}
    </>
  );
}
