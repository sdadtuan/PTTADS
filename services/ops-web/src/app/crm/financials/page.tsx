'use client';

import { useCallback, useEffect, useState } from 'react';
import { useRouter } from 'next/navigation';
import { OpsNav } from '@/components/OpsNav';
import {
  fetchFinanceArAging,
  fetchFinanceFinancials,
  staffMe,
  staffRefresh,
} from '@/lib/api';
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

export default function CrmFinancialsPage() {
  const router = useRouter();
  const now = new Date();
  const [user, setUser] = useState<StoredStaffUser | null>(null);
  const [year, setYear] = useState(now.getFullYear());
  const [month, setMonth] = useState(now.getMonth() + 1);
  const [financials, setFinancials] = useState<Record<string, unknown> | null>(null);
  const [arAging, setArAging] = useState<Record<string, unknown> | null>(null);
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
      if (!hasCap(me, 'crm_business_dashboard', 'view')) {
        setError('Không có quyền Financials');
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

  const loadData = useCallback(
    async (access: string) => {
      setLoading(true);
      setError('');
      try {
        const [fin, ar] = await Promise.all([
          fetchFinanceFinancials(access, { year, month }),
          fetchFinanceArAging(access),
        ]);
        setFinancials(fin);
        setArAging(ar.buckets ? ar : (fin.ar_aging as Record<string, unknown>) ?? ar);
      } catch (err) {
        setError(err instanceof Error ? err.message : 'Tải financials thất bại');
      } finally {
        setLoading(false);
      }
    },
    [year, month],
  );

  useEffect(() => {
    void (async () => {
      const access = await ensureAuth();
      if (!access) return;
      await loadData(access);
    })();
  }, [ensureAuth, loadData]);

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

  const rows = (financials?.rows ?? []) as Array<Record<string, unknown>>;

  return (
    <main style={{ maxWidth: 960, margin: '0 auto', padding: '1.5rem' }}>
      <OpsNav user={user} onLogout={logout} />
      <div className="card">
        <h2 style={{ marginTop: 0, fontSize: '1.15rem' }}>Financials — lifecycle margin</h2>
        <div style={{ display: 'flex', gap: '0.5rem', flexWrap: 'wrap', marginBottom: '1rem' }}>
          <input
            type="number"
            value={year}
            onChange={(e) => setYear(Number(e.target.value))}
            style={{
              width: 90,
              background: 'var(--bg)',
              border: '1px solid var(--border)',
              borderRadius: 8,
              padding: '0.55rem 0.75rem',
              color: 'var(--text)',
            }}
          />
          <input
            type="number"
            min={1}
            max={12}
            value={month}
            onChange={(e) => setMonth(Number(e.target.value))}
            style={{
              width: 70,
              background: 'var(--bg)',
              border: '1px solid var(--border)',
              borderRadius: 8,
              padding: '0.55rem 0.75rem',
              color: 'var(--text)',
            }}
          />
        </div>

        {loading ? <p className="muted">Đang tải…</p> : null}
        {error ? <p className="error">{error}</p> : null}

        <h3 style={{ fontSize: '1rem' }}>Lifecycle ({rows.length})</h3>
        <div style={{ overflowX: 'auto', marginBottom: '1rem' }}>
          <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: '0.85rem' }}>
            <thead>
              <tr>
                <th style={{ textAlign: 'left', padding: '0.35rem' }}>ID</th>
                <th style={{ textAlign: 'left', padding: '0.35rem' }}>Dịch vụ</th>
                <th style={{ textAlign: 'left', padding: '0.35rem' }}>KH</th>
                <th style={{ textAlign: 'right', padding: '0.35rem' }}>Margin</th>
              </tr>
            </thead>
            <tbody>
              {rows.length === 0 ? (
                <tr>
                  <td colSpan={4} className="muted" style={{ padding: '0.35rem' }}>
                    Chưa có lifecycle active
                  </td>
                </tr>
              ) : (
                rows.map((row, i) => (
                  <tr key={String(row.lifecycle_id ?? i)}>
                    <td style={{ padding: '0.35rem' }}>{String(row.lifecycle_id ?? '—')}</td>
                    <td style={{ padding: '0.35rem' }}>{String(row.service_label ?? row.service_slug ?? '—')}</td>
                    <td style={{ padding: '0.35rem' }}>{String(row.customer_name ?? '—')}</td>
                    <td style={{ padding: '0.35rem', textAlign: 'right' }}>
                      {row.margin_pct != null
                        ? `${Number(row.margin_pct).toFixed(1)}%`
                        : row.margin_vnd != null
                          ? `${Number(row.margin_vnd).toLocaleString('vi-VN')} VND`
                          : '—'}
                    </td>
                  </tr>
                ))
              )}
            </tbody>
          </table>
        </div>

        <h3 style={{ fontSize: '1rem' }}>AR aging</h3>
        <pre
          style={{
            background: 'var(--bg)',
            border: '1px solid var(--border)',
            borderRadius: 8,
            padding: '0.75rem',
            overflow: 'auto',
            fontSize: '0.85rem',
          }}
        >
          {JSON.stringify(arAging ?? {}, null, 2)}
        </pre>
      </div>
    </main>
  );
}
