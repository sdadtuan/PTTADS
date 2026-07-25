'use client';

import Link from 'next/link';
import { Suspense, useCallback, useEffect, useState } from 'react';
import { useRouter, useSearchParams } from 'next/navigation';
import { OpsNav } from '@/components/OpsNav';
import {
  fetchSeoAutomationsStatus,
  fetchSeoClients,
  runSeoAutomationsAlertChecks,
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
import { canConfigureSeoSettings, canViewSeoAutomations } from '@/lib/seo/caps';

export default function SeoAutomationsPage() {
  return (
    <Suspense fallback={<main style={{ padding: '2rem' }}><p className="muted">Đang tải automations…</p></main>}>
      <SeoAutomationsContent />
    </Suspense>
  );
}

function SeoAutomationsContent() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const [user, setUser] = useState<StoredStaffUser | null>(null);
  const [clients, setClients] = useState<SeoHubClientRow[]>([]);
  const [customerId, setCustomerId] = useState('');
  const [summary, setSummary] = useState<Record<string, unknown>>({});
  const [syncRuns, setSyncRuns] = useState<Array<Record<string, unknown>>>([]);
  const [recentJobs, setRecentJobs] = useState<Array<Record<string, unknown>>>([]);
  const [openAlerts, setOpenAlerts] = useState<Array<Record<string, unknown>>>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [toast, setToast] = useState('');

  const ensureAuth = useCallback(async (): Promise<string | null> => {
    let access = getAccessToken();
    if (!access) { router.replace('/login'); return null; }
    try {
      const me = await staffMe(access);
      setUser(me);
      if (!canViewSeoAutomations(me)) { setError('Không có quyền Automations'); return null; }
      return access;
    } catch {
      const refresh = getRefreshToken();
      if (!refresh) { clearSession(); router.replace('/login'); return null; }
      const out = await staffRefresh(refresh);
      updateAccessToken(out.access_token);
      return out.access_token;
    }
  }, [router]);

  const loadData = useCallback(async (access: string, cid?: number) => {
    setLoading(true);
    try {
      const out = await fetchSeoAutomationsStatus(access, cid);
      setSummary(out.summary);
      setSyncRuns(out.sync_runs);
      setRecentJobs(out.recent_jobs);
      setOpenAlerts(out.open_alerts);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Không tải automations');
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    const cid = searchParams.get('customer_id');
    if (cid) setCustomerId(cid);
  }, [searchParams]);

  useEffect(() => {
    void (async () => {
      const access = await ensureAuth();
      if (!access) return;
      const out = await fetchSeoClients(access);
      setClients(out.clients);
      if (!customerId && out.clients[0]) setCustomerId(String(out.clients[0].customer_id));
    })();
  }, [ensureAuth, customerId]);

  useEffect(() => {
    void (async () => {
      const access = await ensureAuth();
      if (!access) return;
      const cid = customerId ? Number.parseInt(customerId, 10) : undefined;
      await loadData(access, cid && !Number.isNaN(cid) ? cid : undefined);
    })();
  }, [customerId, ensureAuth, loadData]);

  return (
    <>
      <OpsNav user={user} onLogout={() => { clearSession(); router.replace('/login'); }} />
      <main style={{ padding: '1.5rem 2rem', maxWidth: 1200 }}>
        <h1>Automations &amp; Alerts</h1>
        <p className="muted">Sync runs, job queue, alert checks — S-13</p>

        <div className="card" style={{ marginBottom: '1rem', display: 'flex', gap: '1rem', flexWrap: 'wrap', alignItems: 'end' }}>
          <label>
            Client filter
            <select value={customerId} onChange={(e) => setCustomerId(e.target.value)} style={{ display: 'block', marginTop: 4 }}>
              <option value="">Tất cả</option>
              {clients.map((c) => (
                <option key={c.customer_id} value={c.customer_id}>{c.customer_name}</option>
              ))}
            </select>
          </label>
          {canConfigureSeoSettings(user) && (
            <button type="button" onClick={() => void (async () => {
              const access = await ensureAuth();
              if (!access) return;
              const out = await runSeoAutomationsAlertChecks(access);
              setToast(`Alert checks: ${out.created.length} created`);
              const cid = customerId ? Number.parseInt(customerId, 10) : undefined;
              await loadData(access, cid && !Number.isNaN(cid) ? cid : undefined);
            })()}>Run alert checks</button>
          )}
        </div>

        {!loading && (
          <div className="card" style={{ marginBottom: '1rem', display: 'flex', gap: '1.5rem', flexWrap: 'wrap' }}>
            <span>Failed sync (7d): <strong>{String(summary.failed_sync_runs_7d ?? 0)}</strong></span>
            <span>Open alerts: <strong>{String(summary.open_alerts ?? 0)}</strong></span>
            <span>Pending SEO jobs: <strong>{String(summary.pending_seo_jobs ?? 0)}</strong></span>
            <span>Jobs enabled: <strong>{summary.jobs_enabled ? 'yes' : 'no'}</strong></span>
          </div>
        )}

        {error && <p className="error">{error}</p>}
        {toast && <p className="muted">{toast}</p>}

        {loading ? <p className="muted">Đang tải…</p> : (
          <>
            <div className="card" style={{ marginBottom: '1rem' }}>
              <h2 style={{ marginTop: 0, fontSize: '1rem' }}>Recent sync runs</h2>
              <table style={{ width: '100%', borderCollapse: 'collapse' }}>
                <thead>
                  <tr><th align="left">Source</th><th align="left">Status</th><th align="left">Started</th><th align="left">Rows</th></tr>
                </thead>
                <tbody>
                  {syncRuns.map((r) => (
                    <tr key={String(r.id)}>
                      <td>{String(r.source)}</td>
                      <td>{String(r.status)}</td>
                      <td className="muted">{String(r.started_at ?? '—')}</td>
                      <td>{String(r.rows_imported ?? 0)}</td>
                    </tr>
                  ))}
                  {!syncRuns.length && <tr><td colSpan={4} className="muted">Chưa có sync run.</td></tr>}
                </tbody>
              </table>
            </div>

            <div className="card" style={{ marginBottom: '1rem' }}>
              <h2 style={{ marginTop: 0, fontSize: '1rem' }}>Recent SEO jobs</h2>
              <table style={{ width: '100%', borderCollapse: 'collapse' }}>
                <thead>
                  <tr><th align="left">Type</th><th align="left">Status</th><th align="left">Created</th></tr>
                </thead>
                <tbody>
                  {recentJobs.map((j) => (
                    <tr key={String(j.id)}>
                      <td>{String(j.job_type)}</td>
                      <td>{String(j.status)}</td>
                      <td className="muted">{String(j.created_at ?? '—')}</td>
                    </tr>
                  ))}
                  {!recentJobs.length && <tr><td colSpan={3} className="muted">Chưa có job.</td></tr>}
                </tbody>
              </table>
            </div>

            <div className="card">
              <h2 style={{ marginTop: 0, fontSize: '1rem' }}>Open alerts</h2>
              <ul style={{ margin: 0, paddingLeft: '1.25rem' }}>
                {openAlerts.map((a) => (
                  <li key={String(a.id)}>{String(a.message)} <span className="muted">({String(a.alert_type)})</span></li>
                ))}
                {!openAlerts.length && <li className="muted">Không có alert mở.</li>}
              </ul>
            </div>
          </>
        )}

        <p style={{ marginTop: '1rem' }}><Link href="/seo/hub">← Hub</Link> · <Link href="/seo/reports">Reports</Link></p>
      </main>
    </>
  );
}
