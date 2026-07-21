'use client';

import Link from 'next/link';
import { useCallback, useEffect, useState } from 'react';
import { useRouter } from 'next/navigation';
import { OpsNav } from '@/components/OpsNav';
import {
  fetchAgencyNotifications,
  markAgencyNotificationRead,
  markAllAgencyNotificationsRead,
  staffMe,
  staffRefresh,
} from '@/lib/api';
import type { NotificationRow } from '@/lib/api';
import {
  clearSession,
  getAccessToken,
  getRefreshToken,
  getStoredUser,
  hasCap,
  updateAccessToken,
  updateStoredUser,
  type StoredStaffUser,
} from '@/lib/auth';

const RECIPIENT = 'ops';

export default function AgencyNotificationsPage() {
  const router = useRouter();
  const [user, setUser] = useState<StoredStaffUser | null>(null);
  const [items, setItems] = useState<NotificationRow[]>([]);
  const [unread, setUnread] = useState(0);
  const [filter, setFilter] = useState('');
  const [error, setError] = useState('');
  const [busy, setBusy] = useState(false);

  const ensureAuth = useCallback(async (): Promise<string | null> => {
    let access = getAccessToken();
    if (!access) {
      router.replace('/login');
      return null;
    }
    try {
      const me = await staffMe(access);
      setUser(me);
      updateStoredUser(me);
      if (!hasCap(me, 'crm_agency', 'view')) return null;
      return access;
    } catch {
      const refresh = getRefreshToken();
      if (!refresh) {
        clearSession();
        router.replace('/login');
        return null;
      }
      const out = await staffRefresh(refresh);
      updateAccessToken(out.access_token);
      return out.access_token;
    }
  }, [router]);

  const reload = useCallback(async (access: string) => {
    const data = await fetchAgencyNotifications(access);
    setItems(data.notifications);
    setUnread(data.unread);
  }, []);

  useEffect(() => {
    void (async () => {
      const access = await ensureAuth();
      if (!access) return;
      try {
        await reload(access);
      } catch (err) {
        setError(err instanceof Error ? err.message : 'Tải thông báo thất bại');
      }
    })();
  }, [ensureAuth, reload]);

  const filtered = filter
    ? items.filter((n) => n.category === filter)
    : items;

  async function markRead(id: string) {
    const access = getAccessToken();
    if (!access) return;
    setBusy(true);
    try {
      await markAgencyNotificationRead(access, id, RECIPIENT);
      await reload(access);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Đánh dấu đã đọc thất bại');
    } finally {
      setBusy(false);
    }
  }

  async function markAll() {
    const access = getAccessToken();
    if (!access) return;
    setBusy(true);
    try {
      await markAllAgencyNotificationsRead(access, RECIPIENT);
      await reload(access);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Đánh dấu tất cả thất bại');
    } finally {
      setBusy(false);
    }
  }

  if (!user) {
    return (
      <main style={{ padding: '2rem' }}>
        <p className="muted">Đang tải…</p>
      </main>
    );
  }

  return (
    <main style={{ maxWidth: 900, margin: '0 auto', padding: '1.5rem' }}>
      <OpsNav user={user} onLogout={() => { clearSession(); router.push('/login'); }} />
      <p style={{ margin: '0 0 1rem' }}>
        <Link href="/agency" className="nav-link">
          ← Agency
        </Link>
      </p>

      <div className="card">
        <div style={{ display: 'flex', flexWrap: 'wrap', gap: '0.75rem', alignItems: 'center', marginBottom: '1rem' }}>
          <h2 style={{ margin: 0, flex: '1 1 auto' }}>Thông báo {unread > 0 ? `(${unread} chưa đọc)` : ''}</h2>
          <button type="button" className="btn btn-secondary btn-sm" disabled={busy || unread === 0} onClick={() => void markAll()}>
            Đánh dấu tất cả đã đọc
          </button>
        </div>

        <div className="agency-tabs" style={{ marginBottom: '1rem' }}>
          {['', 'sla', 'ingest', 'system'].map((cat) => (
            <button
              key={cat || 'all'}
              type="button"
              className={`agency-tab${filter === cat ? ' is-active' : ''}`}
              onClick={() => setFilter(cat)}
            >
              {cat === '' ? 'Tất cả' : cat.toUpperCase()}
            </button>
          ))}
        </div>

        {error ? <p className="error">{error}</p> : null}

        <ul className="notification-list">
          {filtered.map((n) => (
            <li key={n.id} className={`notif-item${n.read ? '' : ' notif-item--unread'}`}>
              <div>
                <strong>{n.title}</strong>
                {n.body ? <p className="muted" style={{ margin: '0.25rem 0 0' }}>{n.body}</p> : null}
                <p className="muted" style={{ margin: '0.25rem 0 0', fontSize: '0.85rem' }}>
                  {n.category} · {n.created_at?.slice(0, 16) ?? '—'}
                </p>
              </div>
              {!n.read ? (
                <button type="button" className="btn btn-secondary btn-sm" disabled={busy} onClick={() => void markRead(n.id)}>
                  Đã đọc
                </button>
              ) : null}
            </li>
          ))}
          {filtered.length === 0 ? (
            <li className="agency-empty muted">Không có thông báo</li>
          ) : null}
        </ul>
      </div>
    </main>
  );
}
