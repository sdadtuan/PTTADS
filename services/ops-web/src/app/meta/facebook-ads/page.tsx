'use client';

import Link from 'next/link';
import { useCallback, useEffect, useState } from 'react';
import { useRouter } from 'next/navigation';
import { OpsNav } from '@/components/OpsNav';
import { fetchFacebookHub, staffMe, staffRefresh } from '@/lib/api';
import type { FacebookHubClient } from '@/lib/api';
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

export default function MetaFacebookAdsPage() {
  const router = useRouter();
  const [user, setUser] = useState<StoredStaffUser | null>(null);
  const [rows, setRows] = useState<FacebookHubClient[]>([]);
  const [summary, setSummary] = useState<Record<string, unknown>>({});
  const [alerts, setAlerts] = useState<string[]>([]);
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
      const ok =
        hasCap(me, 'crm_facebook_ads', 'view') || hasCap(me, 'crm_agency', 'view');
      if (!ok) {
        setError('Không có quyền Meta hub');
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
      return access;
    }
  }, [router]);

  useEffect(() => {
    void (async () => {
      const access = await ensureAuth();
      if (!access) return;
      setLoading(true);
      try {
        const hub = await fetchFacebookHub(access, 7);
        setRows(hub.clients);
        setSummary(hub.summary);
        setAlerts(hub.alerts ?? []);
      } catch (err) {
        setError(err instanceof Error ? err.message : 'Tải Meta hub thất bại');
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
      <div className="card">
        <p className="muted" style={{ marginTop: 0 }}>
          Meta closed-loop · spend + CPL · {String(summary.total_spend ?? 0)} ₫ spend ·{' '}
          {String(summary.total_leads ?? 0)} leads
        </p>
        {alerts.length > 0 ? (
          <ul style={{ color: 'var(--warn)', paddingLeft: '1.2rem' }}>
            {alerts.map((a) => (
              <li key={a}>{a}</li>
            ))}
          </ul>
        ) : null}
        {error ? <p className="error">{error}</p> : null}

        <div style={{ overflowX: 'auto' }}>
          <table className="perf-table">
            <thead>
              <tr>
                <th>Client</th>
                <th>Spend</th>
                <th>Leads</th>
                <th>CPL</th>
                <th>Campaigns</th>
                <th>Vượt target</th>
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
                  <td>{fmtVnd(c.spend)}</td>
                  <td>{c.leads_crm}</td>
                  <td>{fmtVnd(c.cpl)}</td>
                  <td>{c.campaigns}</td>
                  <td>{c.over_target_rows}</td>
                </tr>
              ))}
              {!loading && rows.length === 0 ? (
                <tr>
                  <td colSpan={6} className="muted">
                    Chưa có dữ liệu Meta
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
