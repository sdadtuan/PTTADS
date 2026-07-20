'use client';

import Link from 'next/link';
import { useCallback, useEffect, useState } from 'react';
import { useRouter } from 'next/navigation';
import { OpsNav } from '@/components/OpsNav';
import { fetchLeads, staffMe, staffRefresh } from '@/lib/api';
import type { LeadRow } from '@/lib/api';
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

const PAGE_SIZE = 50;

export default function CrmLeadsPage() {
  const router = useRouter();
  const [user, setUser] = useState<StoredStaffUser | null>(null);
  const [token, setToken] = useState('');
  const [rows, setRows] = useState<LeadRow[]>([]);
  const [total, setTotal] = useState(0);
  const [offset, setOffset] = useState(0);
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
      if (!hasCap(me, 'crm_leads', 'view')) {
        setError('Không có quyền xem CRM leads');
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

  const loadLeads = useCallback(
    async (accessToken: string, nextOffset: number, search: string) => {
      setLoading(true);
      setError('');
      try {
        const data = await fetchLeads(accessToken, {
          q: search || undefined,
          limit: PAGE_SIZE,
          offset: nextOffset,
        });
        setRows(data.leads);
        setTotal(data.total);
        setOffset(data.offset);
      } catch (err) {
        setError(err instanceof Error ? err.message : 'Tải leads thất bại');
      } finally {
        setLoading(false);
      }
    },
    [],
  );

  useEffect(() => {
    void (async () => {
      const access = await ensureAuth();
      if (!access) return;
      setToken(access);
      await loadLeads(access, 0, query);
    })();
  }, [ensureAuth, loadLeads, query]);

  function logout() {
    clearSession();
    router.push('/login');
  }

  function onSearch(e: React.FormEvent) {
    e.preventDefault();
    setQuery(q.trim());
    setOffset(0);
  }

  async function goPage(nextOffset: number) {
    if (!token || nextOffset < 0 || nextOffset >= total) return;
    await loadLeads(token, nextOffset, query);
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
      <div className="card">
        <form onSubmit={onSearch} style={{ display: 'flex', gap: '0.75rem', flexWrap: 'wrap', marginBottom: '1rem' }}>
          <input
            type="search"
            placeholder="Tìm tên, SĐT, email…"
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
          {total.toLocaleString('vi-VN')} leads · trang {Math.floor(offset / PAGE_SIZE) + 1} /{' '}
          {Math.max(1, Math.ceil(total / PAGE_SIZE))}
        </p>

        {error ? <p className="error">{error}</p> : null}

        <div style={{ overflowX: 'auto' }}>
          <table className="perf-table">
            <thead>
              <tr>
                <th>ID</th>
                <th>Tên</th>
                <th>SĐT</th>
                <th>Trạng thái</th>
                <th>Nguồn</th>
                <th>Kênh</th>
                <th>Ngày</th>
              </tr>
            </thead>
            <tbody>
              {rows.map((lead) => (
                <tr key={lead.id}>
                  <td>
                    <Link href={`/crm/leads/${lead.id}`} className="nav-link">
                      {lead.id}
                    </Link>
                  </td>
                  <td>{lead.full_name || '—'}</td>
                  <td>{lead.phone || '—'}</td>
                  <td>{lead.status}</td>
                  <td>{lead.source}</td>
                  <td>{lead.channel || '—'}</td>
                  <td>{lead.created_at?.slice(0, 10) ?? '—'}</td>
                </tr>
              ))}
              {!loading && rows.length === 0 ? (
                <tr>
                  <td colSpan={7} className="muted">
                    Không có lead
                  </td>
                </tr>
              ) : null}
            </tbody>
          </table>
        </div>

        <div style={{ display: 'flex', gap: '0.5rem', marginTop: '1rem' }}>
          <button
            type="button"
            className="btn btn-secondary btn-sm"
            disabled={loading || offset <= 0}
            onClick={() => void goPage(Math.max(0, offset - PAGE_SIZE))}
          >
            ← Trước
          </button>
          <button
            type="button"
            className="btn btn-secondary btn-sm"
            disabled={loading || offset + PAGE_SIZE >= total}
            onClick={() => void goPage(offset + PAGE_SIZE)}
          >
            Sau →
          </button>
        </div>
      </div>
    </main>
  );
}
