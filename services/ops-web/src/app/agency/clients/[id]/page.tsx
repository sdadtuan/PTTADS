'use client';

import Link from 'next/link';
import { useCallback, useEffect, useState } from 'react';
import { useParams, useRouter } from 'next/navigation';
import { OpsNav } from '@/components/OpsNav';
import {
  fetchAgencyClient,
  fetchClientPerformance,
  staffMe,
  staffRefresh,
} from '@/lib/api';
import type { AgencyClient, PerformanceRow } from '@/lib/api';
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

function fmtVnd(n: number | null | undefined): string {
  if (n == null) return '—';
  return Math.round(n).toLocaleString('vi-VN') + ' ₫';
}

export default function AgencyClientDetailPage() {
  const router = useRouter();
  const params = useParams();
  const clientId = String(params.id ?? '');

  const [user, setUser] = useState<StoredStaffUser | null>(null);
  const [client, setClient] = useState<AgencyClient | null>(null);
  const [perfRows, setPerfRows] = useState<PerformanceRow[]>([]);
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
    if (!clientId) return;
    void (async () => {
      const access = await ensureAuth();
      if (!access) return;
      setLoading(true);
      setError('');
      try {
        const [detail, perf] = await Promise.all([
          fetchAgencyClient(access, clientId),
          fetchClientPerformance(access, clientId, { group_by: 'campaign' }),
        ]);
        setClient(detail);
        setPerfRows(perf.rows ?? []);
      } catch (err) {
        setError(err instanceof Error ? err.message : 'Tải client thất bại');
      } finally {
        setLoading(false);
      }
    })();
  }, [ensureAuth, clientId]);

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
    <main style={{ maxWidth: 1100, margin: '0 auto', padding: '1.5rem' }}>
      <OpsNav user={user} onLogout={logout} />
      <p style={{ margin: '0 0 1rem' }}>
        <Link href="/agency" className="nav-link">
          ← Agency
        </Link>
      </p>

      <div className="card">
        {loading ? <p className="muted">Đang tải…</p> : null}
        {error ? <p className="error">{error}</p> : null}

        {client && !loading ? (
          <>
            <h2 style={{ marginTop: 0 }}>
              {client.code} · {client.name}
            </h2>
            <p className="muted">
              {client.status} · AM: {client.owner_am_id || '—'}
            </p>

            <h3 style={{ fontSize: '1rem', marginTop: '1.5rem' }}>Performance (Meta, 7 ngày)</h3>
            <div style={{ overflowX: 'auto' }}>
              <table className="perf-table">
                <thead>
                  <tr>
                    <th>Campaign</th>
                    <th>Spend</th>
                    <th>Leads</th>
                    <th>CPL</th>
                    <th>Target</th>
                    <th>Δ</th>
                  </tr>
                </thead>
                <tbody>
                  {perfRows.map((row, i) => (
                    <tr key={`${row.external_campaign_id ?? i}`}>
                      <td>{row.external_campaign_name || row.external_campaign_id || '—'}</td>
                      <td>{fmtVnd(row.spend)}</td>
                      <td>{row.leads_crm}</td>
                      <td>{fmtVnd(row.cpl)}</td>
                      <td>{fmtVnd(row.target_cpl_vnd)}</td>
                      <td>
                        {row.cpl_delta_pct != null
                          ? `${row.cpl_delta_pct > 0 ? '+' : ''}${row.cpl_delta_pct}%`
                          : '—'}
                      </td>
                    </tr>
                  ))}
                  {perfRows.length === 0 ? (
                    <tr>
                      <td colSpan={6} className="muted">
                        Chưa có daily_performance — chạy sync_meta_insights
                      </td>
                    </tr>
                  ) : null}
                </tbody>
              </table>
            </div>
          </>
        ) : null}
      </div>
    </main>
  );
}
