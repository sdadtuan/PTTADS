'use client';

import { useCallback, useEffect, useState } from 'react';
import { useRouter } from 'next/navigation';
import { OpsNav } from '@/components/OpsNav';
import {
  exportStaffKpi,
  fetchKpiAlerts,
  fetchKpiChart,
  fetchKpiMetrics,
  staffMe,
  staffRefresh,
  type KpiMetricRow,
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

export default function CrmKpiPage() {
  const router = useRouter();
  const now = new Date();
  const [user, setUser] = useState<StoredStaffUser | null>(null);
  const [metrics, setMetrics] = useState<KpiMetricRow[]>([]);
  const [alerts, setAlerts] = useState<Array<Record<string, unknown>>>([]);
  const [chartMetricId, setChartMetricId] = useState('');
  const [chartData, setChartData] = useState<Record<string, unknown> | null>(null);
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
      if (!hasCap(me, 'crm_kpi_records', 'view')) {
        setError('Không có quyền KPI');
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
        const [metricRows, alertRows] = await Promise.all([
          fetchKpiMetrics(access),
          fetchKpiAlerts(access, { year: now.getFullYear(), month: now.getMonth() + 1 }),
        ]);
        setMetrics(metricRows);
        setAlerts(alertRows);
        if (metricRows[0]) setChartMetricId(String(metricRows[0].id));
      } catch (err) {
        setError(err instanceof Error ? err.message : 'Tải KPI thất bại');
      } finally {
        setLoading(false);
      }
    })();
  }, [ensureAuth, now]);

  async function loadChart() {
    const access = getAccessToken();
    if (!access || !chartMetricId) return;
    setError('');
    try {
      setChartData(
        await fetchKpiChart(access, {
          metric_id: Number(chartMetricId),
          year: now.getFullYear(),
          month: now.getMonth() + 1,
        }),
      );
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Tải biểu đồ thất bại');
    }
  }

  async function onExport() {
    const access = getAccessToken();
    if (!access) return;
    setError('');
    try {
      const bundle = await exportStaffKpi(access, {
        year: now.getFullYear(),
        month: now.getMonth() + 1,
      });
      const blob = new Blob([JSON.stringify(bundle, null, 2)], { type: 'application/json' });
      const url = URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = `kpi-export-${now.getFullYear()}-${now.getMonth() + 1}.json`;
      a.click();
      URL.revokeObjectURL(url);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Export thất bại');
    }
  }

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
    <main style={{ maxWidth: 960, margin: '0 auto', padding: '1.5rem' }}>
      <OpsNav user={user} onLogout={logout} />
      <div className="card">
        <h2 style={{ marginTop: 0, fontSize: '1.15rem' }}>Chỉ tiêu KPI</h2>
        {loading ? <p className="muted">Đang tải…</p> : null}
        {error ? <p className="error">{error}</p> : null}
        <div style={{ display: 'flex', gap: '0.5rem', marginBottom: '1rem', flexWrap: 'wrap' }}>
          <button type="button" className="btn btn-sm btn-secondary" onClick={() => void onExport()}>
            Export JSON
          </button>
        </div>
        <h3 style={{ fontSize: '1rem' }}>Cảnh báo</h3>
        {alerts.length === 0 ? <p className="muted">Không có cảnh báo.</p> : null}
        <ul style={{ margin: '0 0 1rem', paddingLeft: '1.1rem' }}>
          {alerts.map((a, i) => (
            <li key={String(a.id ?? i)}>
              {String(a.message ?? a.label ?? a.metric_name ?? 'Alert')} · {String(a.severity ?? '—')}
            </li>
          ))}
        </ul>
        <h3 style={{ fontSize: '1rem' }}>Chỉ tiêu</h3>
        {metrics.length === 0 && !loading ? <p className="muted">Chưa có chỉ tiêu.</p> : null}
        <ul style={{ margin: '0 0 1rem', paddingLeft: '1.1rem' }}>
          {metrics.map((m) => (
            <li key={m.id}>
              {m.code ? `[${m.code}] ` : ''}
              {m.name} {m.unit ? `(${m.unit})` : ''}
            </li>
          ))}
        </ul>
        <h3 style={{ fontSize: '1rem' }}>Biểu đồ</h3>
        <div style={{ display: 'flex', gap: '0.5rem', marginBottom: '0.75rem', flexWrap: 'wrap' }}>
          <select
            value={chartMetricId}
            onChange={(e) => setChartMetricId(e.target.value)}
            style={{
              background: 'var(--bg)',
              border: '1px solid var(--border)',
              borderRadius: 8,
              padding: '0.55rem 0.75rem',
              color: 'var(--text)',
            }}
          >
            {metrics.map((m) => (
              <option key={m.id} value={String(m.id)}>
                {m.name}
              </option>
            ))}
          </select>
          <button type="button" className="btn btn-sm" onClick={() => void loadChart()}>
            Vẽ
          </button>
        </div>
        {chartData ? (
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
            {JSON.stringify(chartData, null, 2)}
          </pre>
        ) : (
          <p className="muted">Chọn chỉ tiêu và bấm Vẽ.</p>
        )}
      </div>
    </main>
  );
}
