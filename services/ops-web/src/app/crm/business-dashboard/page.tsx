'use client';

import { useCallback, useEffect, useState } from 'react';
import { useRouter } from 'next/navigation';
import { OpsNav } from '@/components/OpsNav';
import {
  fetchFinanceBusinessDashboard,
  fetchFinanceKpiAlerts,
  fetchFinanceKpiTrends,
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

export default function CrmBusinessDashboardPage() {
  const router = useRouter();
  const now = new Date();
  const [user, setUser] = useState<StoredStaffUser | null>(null);
  const [year, setYear] = useState(now.getFullYear());
  const [month, setMonth] = useState(now.getMonth() + 1);
  const [trendMonths, setTrendMonths] = useState(6);
  const [dashboard, setDashboard] = useState<Record<string, unknown> | null>(null);
  const [alerts, setAlerts] = useState<Array<Record<string, unknown>>>([]);
  const [trends, setTrends] = useState<Array<Record<string, unknown>>>([]);
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
        setError('Không có quyền Business Dashboard');
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
        const [dash, alertOut, trendOut] = await Promise.all([
          fetchFinanceBusinessDashboard(access, { year, month, trend_months: trendMonths }),
          fetchFinanceKpiAlerts(access, { year, month }),
          fetchFinanceKpiTrends(access, { year, month, trend_months: trendMonths }),
        ]);
        setDashboard(dash);
        const alertList = (alertOut.alerts ?? dash.kpi_alerts ?? []) as Array<Record<string, unknown>>;
        setAlerts(alertList);
        const trendList = (trendOut.trends ?? dash.trends ?? []) as Array<Record<string, unknown>>;
        setTrends(trendList);
      } catch (err) {
        setError(err instanceof Error ? err.message : 'Tải dashboard thất bại');
      } finally {
        setLoading(false);
      }
    },
    [year, month, trendMonths],
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

  const execMetrics = (dashboard?.exec_metrics ?? {}) as Record<string, unknown>;
  const arAging = (dashboard?.ar_aging ?? {}) as Record<string, unknown>;
  const retention = (dashboard?.retention_metrics ?? {}) as Record<string, unknown>;

  return (
    <main style={{ maxWidth: 960, margin: '0 auto', padding: '1.5rem' }}>
      <OpsNav user={user} onLogout={logout} />
      <div className="card">
        <h2 style={{ marginTop: 0, fontSize: '1.15rem' }}>Business Dashboard</h2>
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
          <input
            type="number"
            min={3}
            max={12}
            value={trendMonths}
            onChange={(e) => setTrendMonths(Number(e.target.value))}
            title="Trend months"
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

        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(180px, 1fr))', gap: '0.75rem', marginBottom: '1rem' }}>
          <div className="card" style={{ padding: '0.75rem' }}>
            <p className="muted" style={{ margin: 0, fontSize: '0.8rem' }}>Exec metrics</p>
            <pre style={{ margin: '0.35rem 0 0', fontSize: '0.75rem', overflow: 'auto' }}>
              {JSON.stringify(execMetrics, null, 2)}
            </pre>
          </div>
          <div className="card" style={{ padding: '0.75rem' }}>
            <p className="muted" style={{ margin: 0, fontSize: '0.8rem' }}>AR aging</p>
            <pre style={{ margin: '0.35rem 0 0', fontSize: '0.75rem', overflow: 'auto' }}>
              {JSON.stringify(arAging, null, 2)}
            </pre>
          </div>
          <div className="card" style={{ padding: '0.75rem' }}>
            <p className="muted" style={{ margin: 0, fontSize: '0.8rem' }}>Retention</p>
            <pre style={{ margin: '0.35rem 0 0', fontSize: '0.75rem', overflow: 'auto' }}>
              {JSON.stringify(retention, null, 2)}
            </pre>
          </div>
        </div>

        <h3 style={{ fontSize: '1rem' }}>Cảnh báo KPI ({alerts.length})</h3>
        <ul style={{ margin: '0.5rem 0 1rem', paddingLeft: '1.1rem' }}>
          {alerts.length === 0 ? (
            <li className="muted">Không có cảnh báo</li>
          ) : (
            alerts.map((a, i) => (
              <li key={String(a.id ?? a.alert_id ?? i)}>
                {String(a.severity ?? '—')} · {String(a.title ?? a.message ?? a.label ?? '—')}
              </li>
            ))
          )}
        </ul>

        <h3 style={{ fontSize: '1rem' }}>Xu hướng ({trends.length})</h3>
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
          {JSON.stringify(trends, null, 2)}
        </pre>
      </div>
    </main>
  );
}
