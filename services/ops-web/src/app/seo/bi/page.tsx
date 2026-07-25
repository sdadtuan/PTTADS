'use client';

import Link from 'next/link';
import { Suspense, useCallback, useEffect, useMemo, useState } from 'react';
import { useRouter, useSearchParams } from 'next/navigation';
import { OpsNav } from '@/components/OpsNav';
import {
  exportSeoClickhouse,
  fetchSeoAttribution,
  fetchSeoBiDashboard,
  fetchSeoBiParity,
  fetchSeoBiStatus,
  fetchSeoClients,
  staffMe,
  staffRefresh,
  type SeoHubClientRow,
} from '@/lib/api';
import {
  clearSession,
  getAccessToken,
  getRefreshToken,
  getStoredUser,
  updateAccessToken,
  type StoredStaffUser,
} from '@/lib/auth';
import { canViewSeoBi } from '@/lib/seo/caps';

export default function SeoBiPage() {
  return (
    <Suspense fallback={<main style={{ padding: '2rem' }}><p className="muted">Đang tải SEO BI…</p></main>}>
      <SeoBiContent />
    </Suspense>
  );
}

function SeoBiContent() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const [user, setUser] = useState<StoredStaffUser | null>(null);
  const [clients, setClients] = useState<SeoHubClientRow[]>([]);
  const [customerId, setCustomerId] = useState('');
  const [status, setStatus] = useState<Record<string, unknown>>({});
  const [dashboard, setDashboard] = useState<Record<string, unknown>>({});
  const [parity, setParity] = useState<Record<string, unknown>>({});
  const [attribution, setAttribution] = useState<Record<string, unknown>>({});
  const [loading, setLoading] = useState(true);
  const [exportBusy, setExportBusy] = useState(false);
  const [error, setError] = useState('');
  const [toast, setToast] = useState('');

  const ensureAuth = useCallback(async (): Promise<string | null> => {
    let access = getAccessToken();
    if (!access) { router.replace('/login'); return null; }
    const cached = getStoredUser();
    if (cached) setUser(cached);
    try {
      const me = await staffMe(access);
      setUser(me);
      if (!canViewSeoBi(me)) { setError('Không có quyền SEO BI'); return null; }
      return access;
    } catch {
      const refresh = getRefreshToken();
      if (!refresh) { clearSession(); router.replace('/login'); return null; }
      const out = await staffRefresh(refresh);
      updateAccessToken(out.access_token);
      return out.access_token;
    }
  }, [router]);

  const load = useCallback(async (token: string, cid?: string) => {
    const [st, dash, par] = await Promise.all([
      fetchSeoBiStatus(token),
      fetchSeoBiDashboard(token, cid ? Number(cid) : undefined, 28),
      fetchSeoBiParity(token, 7),
    ]);
    setStatus(st as unknown as Record<string, unknown>);
    setDashboard(dash as unknown as Record<string, unknown>);
    setParity(par as unknown as Record<string, unknown>);
    if (cid) {
      const attr = await fetchSeoAttribution(token, Number(cid), 28);
      setAttribution(attr as unknown as Record<string, unknown>);
    } else {
      setAttribution({});
    }
  }, []);

  useEffect(() => {
    void (async () => {
      const token = await ensureAuth();
      if (!token) { setLoading(false); return; }
      try {
        const hub = await fetchSeoClients(token);
        setClients(hub.clients ?? []);
        const qCid = searchParams.get('customer_id') ?? '';
        const initial = qCid || String(hub.clients?.[0]?.customer_id ?? '');
        setCustomerId(initial);
        await load(token, initial || undefined);
      } catch (e) {
        setError(e instanceof Error ? e.message : 'Lỗi tải BI');
      } finally {
        setLoading(false);
      }
    })();
  }, [ensureAuth, load, searchParams]);

  const gscSeries = useMemo(
    () => (dashboard.gsc_series as Array<Record<string, unknown>>) ?? [],
    [dashboard.gsc_series],
  );

  const onExport = async () => {
    const token = getAccessToken();
    if (!token) return;
    setExportBusy(true);
    try {
      const out = await exportSeoClickhouse(token);
      setToast(out.ok ? `Đã enqueue export (${out.mode})` : `Export thất bại: ${out.error ?? out.mode}`);
    } catch (e) {
      setToast(e instanceof Error ? e.message : 'Export lỗi');
    } finally {
      setExportBusy(false);
    }
  };

  if (loading) {
    return (
      <main style={{ padding: '2rem' }}>
        <OpsNav user={user} onLogout={() => { clearSession(); router.replace('/login'); }} />
        <p className="muted">Đang tải SEO BI…</p>
      </main>
    );
  }

  return (
    <main style={{ padding: '2rem', maxWidth: 1100 }}>
      <OpsNav user={user} onLogout={() => { clearSession(); router.replace('/login'); }} />
      <header style={{ marginBottom: '1.5rem' }}>
        <h1>SEO BI &amp; Grafana (Gate D)</h1>
        <p className="muted">
          ClickHouse export, parity sample 7 ngày, organic attribution. Grafana:{' '}
          <code>{String(status.grafana_dashboard ?? 'deploy/grafana/seo-ops-dashboard.json')}</code>
        </p>
      </header>

      {error ? <p className="error">{error}</p> : null}
      {toast ? <p className="badge">{toast}</p> : null}

      <section className="card" style={{ marginBottom: '1rem' }}>
        <h2>Infra status</h2>
        <ul>
          <li>ClickHouse: {status.clickhouse_configured ? 'configured' : 'chưa cấu hình'}</li>
          <li>BI export: {status.bi_export_enabled ? 'enabled' : 'disabled'}</li>
          <li>CWV stub: {status.cwv_stub ? 'ON (pilot)' : 'OFF (prod PageSpeed)'}</li>
          <li>SERP provider: <code>{String(status.serp_provider ?? 'stub')}</code></li>
        </ul>
        <div style={{ display: 'flex', gap: '0.75rem', flexWrap: 'wrap', marginTop: '0.75rem' }}>
          <button type="button" disabled={exportBusy} onClick={() => void onExport()}>
            {exportBusy ? 'Đang export…' : 'Export facts → ClickHouse'}
          </button>
          <Link href="/seo/automations" className="button-link">Automations &amp; timers</Link>
        </div>
      </section>

      <section className="card" style={{ marginBottom: '1rem' }}>
        <h2>Client filter</h2>
        <select
          value={customerId}
          onChange={(e) => {
            const v = e.target.value;
            setCustomerId(v);
            const token = getAccessToken();
            if (token) void load(token, v || undefined);
          }}
        >
          <option value="">Tất cả clients</option>
          {clients.map((c) => (
            <option key={c.customer_id} value={String(c.customer_id)}>
              {c.customer_name} (#{c.customer_id})
            </option>
          ))}
        </select>
      </section>

      <section className="card" style={{ marginBottom: '1rem' }}>
        <h2>GSC trend (28 ngày)</h2>
        <p>
          Clicks: <strong>{Number((dashboard.totals as Record<string, number>)?.clicks ?? 0)}</strong>
          {' · '}
          Impressions: <strong>{Number((dashboard.totals as Record<string, number>)?.impressions ?? 0)}</strong>
        </p>
        {gscSeries.length ? (
          <table className="data-table">
            <thead><tr><th>Ngày</th><th>Clicks</th><th>Impressions</th></tr></thead>
            <tbody>
              {gscSeries.slice(-14).map((row) => (
                <tr key={String(row.stat_date)}>
                  <td>{String(row.stat_date)}</td>
                  <td>{Number(row.clicks)}</td>
                  <td>{Number(row.impressions)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        ) : (
          <p className="muted">Chưa có GSC daily stats — chạy sync GSC trước.</p>
        )}
      </section>

      <section className="card" style={{ marginBottom: '1rem' }}>
        <h2>BI parity sample (7 ngày)</h2>
        <p>Metrics có facts: {(parity.metrics as string[] | undefined)?.join(', ') || '—'}</p>
        <pre style={{ fontSize: '0.85rem', overflow: 'auto' }}>
          {JSON.stringify(parity.totals_by_metric ?? {}, null, 2)}
        </pre>
      </section>

      {customerId ? (
        <section className="card">
          <h2>Organic attribution (#{customerId})</h2>
          <pre style={{ fontSize: '0.85rem', overflow: 'auto' }}>
            {JSON.stringify(attribution.summary ?? {}, null, 2)}
          </pre>
        </section>
      ) : null}
    </main>
  );
}
