'use client';

import Link from 'next/link';
import { useCallback, useEffect, useState } from 'react';
import { useRouter } from 'next/navigation';
import { OpsNav } from '@/components/OpsNav';
import { fetchSeoClients, staffMe, staffRefresh, type SeoHubClientRow } from '@/lib/api';
import {
  clearSession,
  getAccessToken,
  getRefreshToken,
  getStoredUser,
  updateAccessToken,
  updateStoredUser,
  type StoredStaffUser,
} from '@/lib/auth';
import { canViewSeoHub } from '@/lib/seo/caps';

export default function SeoClientsPage() {
  const router = useRouter();
  const [user, setUser] = useState<StoredStaffUser | null>(null);
  const [clients, setClients] = useState<SeoHubClientRow[]>([]);
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(true);

  const ensureAuth = useCallback(async (): Promise<string | null> => {
    let access = getAccessToken();
    if (!access) {
      router.replace('/login');
      return null;
    }
    const cached = getStoredUser();
    if (cached) setUser(cached);
    try {
      const me = await staffMe(access);
      setUser(me);
      updateStoredUser(me);
      if (!canViewSeoHub(me)) {
        setError('Không có quyền SEO/AEO');
        return null;
      }
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
      access = out.access_token;
      const me = await staffMe(access);
      setUser(me);
      updateStoredUser(me);
      return access;
    }
  }, [router]);

  useEffect(() => {
    void (async () => {
      const access = await ensureAuth();
      if (!access) return;
      setLoading(true);
      try {
        const data = await fetchSeoClients(access);
        setClients(data.clients);
      } catch (err) {
        setError(err instanceof Error ? err.message : 'Tải clients thất bại');
      } finally {
        setLoading(false);
      }
    })();
  }, [ensureAuth]);

  function logout() {
    clearSession();
    router.push('/login');
  }

  if (!user) {
    return (
      <main style={{ padding: '2rem' }}>
        <p className="muted">Đang tải…</p>
      </main>
    );
  }

  return (
    <main style={{ maxWidth: 1200, margin: '0 auto', padding: '1.5rem' }}>
      <OpsNav user={user} onLogout={logout} />
      <div className="card" style={{ marginBottom: '1rem' }}>
        <p className="muted" style={{ marginTop: 0 }}>
          SEO clients · workspace B1
        </p>
        <Link href="/seo/hub" className="btn btn-secondary btn-sm">
          ← SEO Hub
        </Link>
      </div>

      {error ? <p className="error">{error}</p> : null}

      <div className="card">
        <div style={{ overflowX: 'auto' }}>
          <table className="perf-table">
            <thead>
              <tr>
                <th>ID</th>
                <th>Tên</th>
                <th>Domains</th>
                <th>Tier</th>
                <th>Settings</th>
                <th>Health</th>
                <th></th>
              </tr>
            </thead>
            <tbody>
              {clients.map((c) => (
                <tr key={c.customer_id} id={`c${c.customer_id}`}>
                  <td>{c.customer_id}</td>
                  <td>
                    <Link href={`/seo/clients/${c.customer_id}`} className="nav-link">
                      {c.customer_name}
                    </Link>
                  </td>
                  <td>{c.domains.join(', ') || '—'}</td>
                  <td>{c.contract_tier}</td>
                  <td>{c.settings_ok ? 'OK' : 'Missing'}</td>
                  <td>
                    <span className={c.health_tier === 'bad' ? 'error' : 'muted'}>
                      {c.health_score} · {c.health_tier}
                    </span>
                  </td>
                  <td>
                    <Link href={`/seo/clients/${c.customer_id}?tab=settings`} className="btn btn-secondary btn-sm">
                      Settings
                    </Link>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
          {!loading && clients.length === 0 ? (
            <p className="muted">Chưa có dữ liệu — chạy seed SEO pilot hoặc import từ Flask PG cutover.</p>
          ) : null}
        </div>
      </div>
    </main>
  );
}
