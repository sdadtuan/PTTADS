'use client';

import Link from 'next/link';
import { useCallback, useEffect, useState } from 'react';
import { useRouter } from 'next/navigation';
import { OpsNav } from '@/components/OpsNav';
import { fetchAgencyClients, fetchAgencyStats, staffMe, staffRefresh } from '@/lib/api';
import type { AgencyClient } from '@/lib/api';
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

export default function AgencyPage() {
  const router = useRouter();
  const [user, setUser] = useState<StoredStaffUser | null>(null);
  const [token, setToken] = useState('');
  const [clients, setClients] = useState<AgencyClient[]>([]);
  const [stats, setStats] = useState<{ pg_ready: boolean; clients: Record<string, number>; jobs: Record<string, number> } | null>(null);
  const [q, setQ] = useState('');
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
      if (!hasCap(me, 'crm_agency', 'view')) {
        setError('Không có quyền Agency');
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
      setToken(access);
      setLoading(true);
      setError('');
      try {
        const [st, list] = await Promise.all([
          fetchAgencyStats(access),
          fetchAgencyClients(access, { q: q.trim() || undefined }),
        ]);
        setStats(st);
        setClients(list.clients);
      } catch (err) {
        setError(err instanceof Error ? err.message : 'Tải agency thất bại');
      } finally {
        setLoading(false);
      }
    })();
  }, [ensureAuth, q]);

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

  const clientTotal = Object.values(stats?.clients ?? {}).reduce((a, b) => a + b, 0);
  const pendingJobs = stats?.jobs?.pending ?? 0;

  return (
    <main style={{ maxWidth: 1200, margin: '0 auto', padding: '1.5rem' }}>
      <OpsNav user={user} onLogout={logout} />
      <div className="card" style={{ marginBottom: '1rem' }}>
        <p className="muted" style={{ marginTop: 0 }}>
          Phase 2 — Agency ops trên ops-web · PG primary · Nest API
        </p>
        <div style={{ display: 'flex', gap: '1.5rem', flexWrap: 'wrap' }}>
          <div>
            <strong>{stats?.pg_ready ? clientTotal : '—'}</strong>
            <span className="muted"> clients</span>
          </div>
          <div>
            <strong>{pendingJobs}</strong>
            <span className="muted"> jobs pending</span>
          </div>
        </div>
      </div>

      <div className="card">
        <form
          onSubmit={(e) => {
            e.preventDefault();
            if (token) void fetchAgencyClients(token, { q: q.trim() || undefined }).then((r) => setClients(r.clients));
          }}
          style={{ display: 'flex', gap: '0.75rem', marginBottom: '1rem', flexWrap: 'wrap' }}
        >
          <Link href="/agency/clients/new" className="btn btn-sm">
            + Client
          </Link>
          <Link href="/agency/jobs" className="btn btn-secondary btn-sm">
            Jobs
          </Link>
          <input
            type="search"
            placeholder="Tìm code, tên client…"
            value={q}
            onChange={(e) => setQ(e.target.value)}
            style={{
              flex: '1 1 220px',
              background: 'var(--bg)',
              border: '1px solid var(--border)',
              borderRadius: 8,
              padding: '0.55rem 0.75rem',
              color: 'var(--text)',
            }}
          />
          <button type="submit" className="btn btn-sm" disabled={loading}>
            Lọc
          </button>
        </form>

        {error ? <p className="error">{error}</p> : null}

        <div style={{ overflowX: 'auto' }}>
          <table className="perf-table">
            <thead>
              <tr>
                <th>Code</th>
                <th>Tên</th>
                <th>Trạng thái</th>
                <th>Kênh</th>
                <th>AM</th>
              </tr>
            </thead>
            <tbody>
              {clients.map((c) => (
                <tr key={c.id}>
                  <td>
                    <Link href={`/agency/clients/${c.id}`} className="nav-link">
                      {c.code}
                    </Link>
                  </td>
                  <td>{c.name}</td>
                  <td>{c.status}</td>
                  <td>{c.channels || '—'}</td>
                  <td>{c.owner_am_id || '—'}</td>
                </tr>
              ))}
              {!loading && clients.length === 0 ? (
                <tr>
                  <td colSpan={5} className="muted">
                    Không có client
                  </td>
                </tr>
              ) : null}
            </tbody>
          </table>
        </div>
      </div>
    </main>
  );
}
