'use client';

import Link from 'next/link';
import { useCallback, useEffect, useState } from 'react';
import { useRouter } from 'next/navigation';
import { OpsNav } from '@/components/OpsNav';
import { fetchCustomers, staffMe, staffRefresh, type CustomerRow } from '@/lib/api';
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

export default function CrmCustomersPage() {
  const router = useRouter();
  const [user, setUser] = useState<StoredStaffUser | null>(null);
  const [rows, setRows] = useState<CustomerRow[]>([]);
  const [q, setQ] = useState('');
  const [query, setQuery] = useState('');
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(false);

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
      if (!hasCap(me, 'crm_board_customers', 'view')) {
        setError('Không có quyền xem khách hàng');
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
      setError('');
      try {
        const data = await fetchCustomers(access, { q: query || undefined, limit: 200 });
        setRows(data);
      } catch (err) {
        setError(err instanceof Error ? err.message : 'Tải khách hàng thất bại');
      } finally {
        setLoading(false);
      }
    })();
  }, [ensureAuth, query]);

  function logout() {
    clearSession();
    router.push('/login');
  }

  return (
    <main style={{ maxWidth: 1200, margin: '0 auto', padding: '1.5rem' }}>
      <OpsNav user={user} onLogout={logout} />
      <div className="card">
        <form
          onSubmit={(e) => {
            e.preventDefault();
            setQuery(q.trim());
          }}
          style={{ display: 'flex', gap: '0.75rem', flexWrap: 'wrap', marginBottom: '1rem' }}
        >
          <input
            type="search"
            placeholder="Tìm tên, SĐT, email, công ty…"
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
          <button className="btn btn-sm" type="submit" disabled={loading}>
            Lọc
          </button>
        </form>

        <p className="muted" style={{ marginTop: 0 }}>
          {rows.length.toLocaleString('vi-VN')} khách hàng
        </p>
        {error ? <p className="error">{error}</p> : null}

        <div style={{ overflowX: 'auto' }}>
          <table className="perf-table">
            <thead>
              <tr>
                <th>ID</th>
                <th>Tên</th>
                <th>SĐT</th>
                <th>Email</th>
                <th>Công ty</th>
                <th>Nguồn</th>
              </tr>
            </thead>
            <tbody>
              {rows.map((c) => (
                <tr key={c.id}>
                  <td>
                    <Link href={`/crm/customers/${c.id}`} className="nav-link">
                      {c.id}
                    </Link>
                  </td>
                  <td>{c.name || '—'}</td>
                  <td>{c.phone || '—'}</td>
                  <td>{c.email || '—'}</td>
                  <td>{c.company || '—'}</td>
                  <td>{c.lead_source_label || c.lead_source || '—'}</td>
                </tr>
              ))}
              {!loading && rows.length === 0 ? (
                <tr>
                  <td colSpan={6} className="muted">
                    Không có khách hàng
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
