'use client';

import Link from 'next/link';
import { Suspense, useCallback, useEffect, useMemo, useState } from 'react';
import { useRouter, useSearchParams } from 'next/navigation';
import { OpsNav } from '@/components/OpsNav';
import {
  downloadSeoReportExport,
  fetchSeoAlerts,
  fetchSeoAttribution,
  fetchSeoClients,
  fetchSeoDashboard,
  fetchSeoReportSchedules,
  staffMe,
  staffRefresh,
  type SeoDashboardData,
  type SeoHubClientRow,
  type SeoReportScheduleRow,
} from '@/lib/api';
import {
  clearSession,
  getAccessToken,
  getRefreshToken,
  getStoredUser,
  updateAccessToken,
  updateStoredUser,
  type StoredStaffUser,
} from '@/lib/auth';
import { canViewSeoReports } from '@/lib/seo/caps';
import { SeoGscTrendChart } from '@/lib/seo/charts';

const DASHBOARD_TYPES = [
  { key: 'executive', label: 'Executive' },
  { key: 'seo', label: 'SEO' },
  { key: 'content', label: 'Content' },
  { key: 'technical', label: 'Technical' },
  { key: 'aeo', label: 'AEO' },
  { key: 'ops', label: 'Ops' },
] as const;

type DashboardType = (typeof DASHBOARD_TYPES)[number]['key'];

function BarChart({ items, title }: { items: Array<{ label: string; value: number }>; title: string }) {
  const max = Math.max(...items.map((i) => i.value), 1);
  return (
    <div className="card" style={{ marginBottom: '1rem' }}>
      <h2 style={{ marginTop: 0, fontSize: '1.1rem' }}>{title}</h2>
      <div style={{ display: 'grid', gap: '0.5rem' }}>
        {items.map((item) => (
          <div key={item.label} style={{ display: 'flex', alignItems: 'center', gap: '0.75rem' }}>
            <span style={{ minWidth: 100, fontSize: '0.85rem' }}>{item.label}</span>
            <div
              style={{
                flex: 1,
                height: 20,
                background: 'var(--border, #eee)',
                borderRadius: 4,
                overflow: 'hidden',
              }}
            >
              <div
                style={{
                  width: `${(item.value / max) * 100}%`,
                  height: '100%',
                  background: 'currentColor',
                  opacity: 0.6,
                }}
              />
            </div>
            <strong style={{ minWidth: 32, textAlign: 'right' }}>{item.value}</strong>
          </div>
        ))}
      </div>
    </div>
  );
}

export default function SeoReportsPage() {
  return (
    <Suspense
      fallback={
        <main style={{ padding: '2rem' }}>
          <p className="muted">Đang tải reporting center…</p>
        </main>
      }
    >
      <SeoReportsContent />
    </Suspense>
  );
}

function SeoReportsContent() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const [user, setUser] = useState<StoredStaffUser | null>(null);
  const [clients, setClients] = useState<SeoHubClientRow[]>([]);
  const [customerId, setCustomerId] = useState('');
  const [dashboardType, setDashboardType] = useState<DashboardType>('executive');
  const [dashboard, setDashboard] = useState<SeoDashboardData | null>(null);
  const [schedules, setSchedules] = useState<SeoReportScheduleRow[]>([]);
  const [alerts, setAlerts] = useState<Array<Record<string, unknown>>>([]);
  const [attribution, setAttribution] = useState<{
    summary: Record<string, unknown>;
    top_landing_pages: Array<Record<string, unknown>>;
  } | null>(null);
  const [loading, setLoading] = useState(true);
  const [exportBusy, setExportBusy] = useState(false);
  const [error, setError] = useState('');

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
      if (!canViewSeoReports(me)) {
        setError('Không có quyền SEO Reports');
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

  const selectedClient = useMemo(
    () => clients.find((c) => String(c.customer_id) === customerId),
    [clients, customerId],
  );

  const loadReports = useCallback(
    async (access: string, cid: number, type: DashboardType) => {
      setLoading(true);
      setError('');
      try {
        const [dashOut, schedOut, alertsOut, attrOut] = await Promise.all([
          fetchSeoDashboard(access, cid, type),
          fetchSeoReportSchedules(access, cid),
          fetchSeoAlerts(access, 'open'),
          fetchSeoAttribution(access, cid, 28),
        ]);
        setDashboard(dashOut.dashboard);
        setSchedules(schedOut.schedules);
        setAlerts(alertsOut.alerts);
        setAttribution({ summary: attrOut.summary, top_landing_pages: attrOut.top_landing_pages });
      } catch (err) {
        setError(err instanceof Error ? err.message : 'Không tải được báo cáo');
      } finally {
        setLoading(false);
      }
    },
    [],
  );

  useEffect(() => {
    const cid = searchParams.get('customer_id');
    if (cid) setCustomerId(cid);
    const dt = searchParams.get('type') as DashboardType | null;
    if (dt && DASHBOARD_TYPES.some((d) => d.key === dt)) setDashboardType(dt);
  }, [searchParams]);

  useEffect(() => {
    void (async () => {
      const access = await ensureAuth();
      if (!access) return;
      const out = await fetchSeoClients(access);
      setClients(out.clients);
      if (!customerId && out.clients[0]) {
        setCustomerId(String(out.clients[0].customer_id));
      }
    })();
  }, [ensureAuth, customerId]);

  useEffect(() => {
    const cid = Number.parseInt(customerId, 10);
    if (!customerId || Number.isNaN(cid)) return;
    void (async () => {
      const access = await ensureAuth();
      if (!access) return;
      await loadReports(access, cid, dashboardType);
    })();
  }, [customerId, dashboardType, ensureAuth, loadReports]);

  const logout = () => {
    clearSession();
    router.push('/login');
  };

  const kpiCards = useMemo(() => {
    if (!dashboard) return [];
    const cards: Array<{ label: string; value: string }> = [];
    const gsc = dashboard.gsc ?? {};
    if (gsc.clicks != null) cards.push({ label: 'GSC Clicks (28d)', value: String(gsc.clicks) });
    if (gsc.impressions != null) cards.push({ label: 'Impressions', value: String(gsc.impressions) });
    if (gsc.avg_ctr != null) cards.push({ label: 'Avg CTR', value: String(gsc.avg_ctr) });
    if (dashboard.critical_issues != null) {
      cards.push({ label: 'Critical issues', value: String(dashboard.critical_issues) });
    }
    const aeo = dashboard.aeo ?? {};
    if (aeo.coverage_pct != null) cards.push({ label: 'AEO coverage', value: `${aeo.coverage_pct}%` });
    if (dashboard.open_alerts != null) cards.push({ label: 'Open alerts', value: String(dashboard.open_alerts) });
    if (dashboard.content_by_status) {
      const total = Object.values(dashboard.content_by_status).reduce((s, v) => s + v, 0);
      cards.push({ label: 'Content items', value: String(total) });
    }
    if (dashboard.severity) {
      const total = Object.values(dashboard.severity).reduce((s, v) => s + v, 0);
      cards.push({ label: 'Open issues', value: String(total) });
    }
    return cards;
  }, [dashboard]);

  const gscTrendPoints = useMemo(() => {
    return (dashboard?.gsc_trend ?? []).map((p) => ({
      date: p.stat_date,
      clicks: p.clicks,
      impressions: p.impressions,
    }));
  }, [dashboard]);

  async function handleExportCsv() {
    if (!customerId) return;
    const access = await ensureAuth();
    if (!access) return;
    setExportBusy(true);
    try {
      const { blob, filename } = await downloadSeoReportExport(access, Number.parseInt(customerId, 10), {
        type: dashboardType,
        format: 'csv',
        customer_label: selectedClient?.customer_name,
      });
      const url = URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = filename;
      a.click();
      URL.revokeObjectURL(url);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Export CSV thất bại');
    } finally {
      setExportBusy(false);
    }
  }

  return (
    <div className="page">
      <OpsNav user={user} onLogout={logout} />
      <main className="main-content">
        <div className="page-header">
          <div>
            <h1>Reporting Center</h1>
            <p className="muted">S-12 · Dashboard, export, lịch báo cáo, alerts</p>
          </div>
          <div className="page-actions">
            <Link href="/seo/hub" className="btn btn-secondary btn-sm">
              Hub
            </Link>
            <Link href="/seo/technical" className="btn btn-secondary btn-sm">
              Technical
            </Link>
          </div>
        </div>

        <div className="card" style={{ marginBottom: '1rem' }}>
          <div className="form-row" style={{ alignItems: 'end', gap: '1rem', flexWrap: 'wrap' }}>
            <label>
              Client
              <select value={customerId} onChange={(e) => setCustomerId(e.target.value)}>
                <option value="">— Chọn client —</option>
                {clients.map((c) => (
                  <option key={c.customer_id} value={c.customer_id}>
                    {c.customer_name} (#{c.customer_id})
                  </option>
                ))}
              </select>
            </label>
            <label>
              Dashboard
              <select
                value={dashboardType}
                onChange={(e) => setDashboardType(e.target.value as DashboardType)}
              >
                {DASHBOARD_TYPES.map((d) => (
                  <option key={d.key} value={d.key}>
                    {d.label}
                  </option>
                ))}
              </select>
            </label>
            <button
              type="button"
              className="btn btn-sm"
              disabled={!customerId || exportBusy}
              onClick={() => void handleExportCsv()}
            >
              {exportBusy ? 'Đang export…' : 'Export CSV'}
            </button>
          </div>
        </div>

        {error && <p className="error">{error}</p>}

        {!customerId ? (
          <p className="muted">Chọn client để xem báo cáo.</p>
        ) : loading ? (
          <p className="muted">Đang tải…</p>
        ) : (
          <>
            {kpiCards.length > 0 && (
              <div
                className="card"
                style={{
                  display: 'grid',
                  gridTemplateColumns: 'repeat(auto-fill, minmax(140px, 1fr))',
                  gap: '1rem',
                  marginBottom: '1rem',
                }}
              >
                {kpiCards.map((kpi) => (
                  <div key={kpi.label}>
                    <p className="muted" style={{ margin: 0 }}>
                      {kpi.label}
                    </p>
                    <strong>{kpi.value}</strong>
                  </div>
                ))}
              </div>
            )}

            {gscTrendPoints.length > 0 && (
              <div className="card" style={{ marginBottom: '1rem' }}>
                <h2 style={{ marginTop: 0, fontSize: '1.1rem' }}>GSC trend</h2>
                <SeoGscTrendChart points={gscTrendPoints} days={dashboard?.days ?? 28} />
              </div>
            )}

            {dashboard?.content_chart && dashboard.content_chart.length > 0 && (
              <BarChart items={dashboard.content_chart} title="Content theo status" />
            )}

            {dashboard?.severity_chart && dashboard.severity_chart.length > 0 && (
              <BarChart items={dashboard.severity_chart} title="Issues theo severity" />
            )}

            {attribution && (
              <div className="card" style={{ marginBottom: '1rem' }}>
                <h2 style={{ marginTop: 0, fontSize: '1.1rem' }}>Organic attribution (28 ngày)</h2>
                <div
                  style={{
                    display: 'grid',
                    gridTemplateColumns: 'repeat(auto-fill, minmax(140px, 1fr))',
                    gap: '1rem',
                    marginBottom: '1rem',
                  }}
                >
                  {[
                    { label: 'Sessions', value: attribution.summary.sessions },
                    { label: 'Users', value: attribution.summary.users },
                    { label: 'Conversions', value: attribution.summary.conversions },
                    { label: 'Revenue', value: attribution.summary.revenue },
                    { label: 'Conv. rate', value: attribution.summary.conversion_rate },
                    { label: 'Rev/session', value: attribution.summary.revenue_per_session },
                  ].map((item) => (
                    <div key={item.label}>
                      <p className="muted" style={{ margin: 0 }}>
                        {item.label}
                      </p>
                      <strong>{String(item.value ?? '—')}</strong>
                    </div>
                  ))}
                </div>
                {attribution.top_landing_pages.length > 0 ? (
                  <div className="table-wrap">
                    <table>
                      <thead>
                        <tr>
                          <th>Landing page</th>
                          <th>Sessions</th>
                          <th>Conversions</th>
                          <th>Revenue</th>
                        </tr>
                      </thead>
                      <tbody>
                        {attribution.top_landing_pages.map((row, idx) => (
                          <tr key={String(row.landing_page ?? idx)}>
                            <td style={{ maxWidth: 320, wordBreak: 'break-all' }}>
                              {String(row.landing_page ?? '—')}
                            </td>
                            <td>{String(row.sessions ?? '—')}</td>
                            <td>{String(row.conversions ?? '—')}</td>
                            <td>{String(row.revenue ?? '—')}</td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                ) : (
                  <p className="muted">Chưa có GA4 organic landing pages — chạy sync GA4 trước.</p>
                )}
              </div>
            )}

            <div className="card" style={{ marginBottom: '1rem' }}>
              <h2 style={{ marginTop: 0, fontSize: '1.1rem' }}>Lịch báo cáo</h2>
              {schedules.length > 0 ? (
                <div className="table-wrap">
                  <table>
                    <thead>
                      <tr>
                        <th>Dashboard</th>
                        <th>Cadence</th>
                        <th>Recipients</th>
                        <th>Active</th>
                        <th>Next run</th>
                        <th>Last run</th>
                      </tr>
                    </thead>
                    <tbody>
                      {schedules.map((s) => (
                        <tr key={s.id}>
                          <td>{s.dashboard_type}</td>
                          <td>{s.cadence}</td>
                          <td>{s.recipient_emails.join(', ') || '—'}</td>
                          <td>{s.active ? '✓' : '—'}</td>
                          <td>{s.next_run_at ?? '—'}</td>
                          <td>{s.last_run_at ?? '—'}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              ) : (
                <p className="muted">Chưa có lịch báo cáo tự động.</p>
              )}
            </div>

            <div className="card">
              <h2 style={{ marginTop: 0, fontSize: '1.1rem' }}>Open alerts</h2>
              {alerts.length > 0 ? (
                <ul style={{ margin: 0, paddingLeft: '1.2rem' }}>
                  {alerts.map((alert) => (
                    <li key={String(alert.id)} style={{ marginBottom: '0.5rem' }}>
                      <span className={alert.severity === 'critical' ? 'error' : 'muted'}>
                        [{String(alert.severity ?? 'info')}] {String(alert.message ?? '')}
                      </span>
                      {alert.link ? (
                        <>
                          {' '}
                          <Link href={String(alert.link).replace('/crm/seo', '/seo')} className="nav-link">
                            Xem
                          </Link>
                        </>
                      ) : null}
                    </li>
                  ))}
                </ul>
              ) : (
                <p className="muted">Không có alert mở.</p>
              )}
            </div>
          </>
        )}
      </main>
    </div>
  );
}
