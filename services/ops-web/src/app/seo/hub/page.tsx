'use client';

import Link from 'next/link';
import { useCallback, useEffect, useState } from 'react';
import { useRouter } from 'next/navigation';
import { OpsNav } from '@/components/OpsNav';
import { fetchSeoHub, staffMe, staffRefresh, type SeoHubResponse } from '@/lib/api';
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

function tierClass(tier: string): string {
  if (tier === 'good') return 'badge';
  if (tier === 'warn') return 'badge';
  return 'error';
}

export default function SeoHubPage() {
  const router = useRouter();
  const [user, setUser] = useState<StoredStaffUser | null>(null);
  const [hub, setHub] = useState<SeoHubResponse | null>(null);
  const [days, setDays] = useState(90);
  const [customerId, setCustomerId] = useState('');
  const [market, setMarket] = useState('');
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

  const loadHub = useCallback(
    async (access: string) => {
      setLoading(true);
      setError('');
      try {
        const data = await fetchSeoHub(access, {
          days,
          market: market.trim() || undefined,
          customer_id: customerId ? Number.parseInt(customerId, 10) : undefined,
        });
        setHub(data);
      } catch (err) {
        setError(err instanceof Error ? err.message : 'Tải SEO hub thất bại');
      } finally {
        setLoading(false);
      }
    },
    [customerId, days, market],
  );

  useEffect(() => {
    void (async () => {
      const access = await ensureAuth();
      if (!access) return;
      await loadHub(access);
    })();
  }, [ensureAuth, loadHub]);

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

  const summary = hub?.summary;

  return (
    <main style={{ maxWidth: 1200, margin: '0 auto', padding: '1.5rem' }}>
      <OpsNav user={user} onLogout={logout} />
      <div className="card" style={{ marginBottom: '1rem' }}>
        <p className="muted" style={{ marginTop: 0 }}>
          SEO/AEO Ops hub · Nest PG · Phase 1 B1
        </p>
        <div style={{ display: 'flex', gap: '0.75rem', flexWrap: 'wrap', marginBottom: '1rem' }}>
          <Link href="/seo/clients" className="btn btn-sm">
            Danh sách client
          </Link>
        </div>
        <div style={{ display: 'flex', gap: '0.75rem', flexWrap: 'wrap' }}>
          <label className="muted">
            Days{' '}
            <select
              value={days}
              onChange={(e) => setDays(Number(e.target.value))}
              style={{ marginLeft: '0.35rem' }}
            >
              <option value={28}>28</option>
              <option value={90}>90</option>
            </select>
          </label>
          <label className="muted">
            Client ID{' '}
            <input
              value={customerId}
              onChange={(e) => setCustomerId(e.target.value)}
              placeholder="all"
              style={{ width: 80, marginLeft: '0.35rem' }}
            />
          </label>
          <label className="muted">
            Market{' '}
            <select value={market} onChange={(e) => setMarket(e.target.value)} style={{ marginLeft: '0.35rem' }}>
              <option value="">All</option>
              <option value="VN">VN</option>
              <option value="US">US</option>
            </select>
          </label>
          <button
            type="button"
            className="btn btn-secondary btn-sm"
            disabled={loading}
            onClick={() => {
              const access = getAccessToken();
              if (access) void loadHub(access);
            }}
          >
            Làm mới
          </button>
        </div>
      </div>

      {error ? <p className="error">{error}</p> : null}

      {summary && summary.failed_sync_runs > 0 ? (
        <div className="card" style={{ marginBottom: '1rem', borderLeft: '4px solid #c0392b' }}>
          <strong>Sync banner:</strong> {summary.failed_sync_runs} sync run thất bại trong 7 ngày qua.{' '}
          <Link href="/seo/clients" className="nav-link">
            Kiểm tra client settings
          </Link>
        </div>
      ) : null}

      {hub?.executive?.content_delivery ? (
        <div className="card" style={{ marginBottom: '1rem' }}>
          <h2 style={{ marginTop: 0, fontSize: '1.1rem' }}>Content delivery</h2>
          <div style={{ display: 'flex', gap: '1.5rem', flexWrap: 'wrap' }}>
            <span>In writing: {hub.executive.content_delivery.in_writing ?? 0}</span>
            <span>In review: {hub.executive.content_delivery.in_review ?? 0}</span>
            <span>Overdue: {hub.executive.content_delivery.overdue ?? 0}</span>
            <span>Published: {hub.executive.content_delivery.published ?? 0}</span>
          </div>
        </div>
      ) : null}

      {summary ? (
        <div
          className="card"
          style={{
            display: 'grid',
            gridTemplateColumns: 'repeat(auto-fill, minmax(140px, 1fr))',
            gap: '1rem',
            marginBottom: '1rem',
          }}
        >
          <div>
            <p className="muted" style={{ margin: 0 }}>
              Clients
            </p>
            <strong>{summary.seo_clients}</strong>
          </div>
          <div>
            <p className="muted" style={{ margin: 0 }}>
              AEO coverage
            </p>
            <strong>{summary.aeo_coverage_pct}%</strong>
          </div>
          <div>
            <p className="muted" style={{ margin: 0 }}>
              Critical issues
            </p>
            <strong>{summary.critical_issues}</strong>
          </div>
          <div>
            <p className="muted" style={{ margin: 0 }}>
              GSC clicks (28d)
            </p>
            <strong>{String(hub?.executive?.gsc_totals?.clicks ?? '—')}</strong>
          </div>
          <div>
            <p className="muted" style={{ margin: 0 }}>
              Publish SLA
            </p>
            <strong>{summary.publish_sla_pct}%</strong>
          </div>
        </div>
      ) : null}

      {hub?.alerts?.length ? (
        <div className="card" style={{ marginBottom: '1rem' }}>
          <h2 style={{ marginTop: 0, fontSize: '1.1rem' }}>Alerts</h2>
          <ul style={{ margin: 0, paddingLeft: '1.2rem' }}>
            {hub.alerts.map((alert) => (
              <li key={alert.message} style={{ marginBottom: '0.5rem' }}>
                <span className={alert.severity === 'danger' ? 'error' : 'muted'}>{alert.message}</span>{' '}
                <Link href={alert.link.replace('/crm/seo', '/seo')} className="nav-link">
                  {alert.link_label}
                </Link>
              </li>
            ))}
          </ul>
        </div>
      ) : null}

      <div className="card">
        <h2 style={{ marginTop: 0, fontSize: '1.1rem' }}>Clients overview</h2>
        <div style={{ overflowX: 'auto' }}>
          <table className="perf-table">
            <thead>
              <tr>
                <th>ID</th>
                <th>Client</th>
                <th>AEO</th>
                <th>Critical</th>
                <th>Health</th>
              </tr>
            </thead>
            <tbody>
              {(hub?.clients ?? []).map((c) => (
                <tr key={c.customer_id}>
                  <td>{c.customer_id}</td>
                  <td>
                    <Link href={`/seo/clients/${c.customer_id}`} className="nav-link">
                      {c.customer_name}
                    </Link>
                  </td>
                  <td>
                    {c.aeo_coverage_pct}% ({c.aeo_visible}/{c.aeo_queries})
                  </td>
                  <td>{c.critical_issues}</td>
                  <td>
                    <span className={tierClass(c.health_tier)}>
                      {c.health_score} · {c.health_tier}
                    </span>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
          {!loading && (hub?.clients?.length ?? 0) === 0 ? (
            <p className="muted">Chưa có client SEO trong PG — seed seo_client_settings hoặc pilot map.</p>
          ) : null}
        </div>
      </div>
    </main>
  );
}
