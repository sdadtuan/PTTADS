'use client';

import Link from 'next/link';
import { Suspense, useCallback, useEffect, useState } from 'react';
import { useRouter, useSearchParams } from 'next/navigation';
import { OpsNav } from '@/components/OpsNav';
import {
  fetchSeoClients,
  fetchSeoCmsJobs,
  fetchSeoCmsTarget,
  staffMe,
  staffRefresh,
  testSeoCmsWebhook,
  upsertSeoCmsTarget,
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
import { canViewSeoCms } from '@/lib/seo/caps';

export default function SeoCmsPage() {
  return (
    <Suspense fallback={<main style={{ padding: '2rem' }}><p className="muted">Đang tải CMS pilot…</p></main>}>
      <SeoCmsContent />
    </Suspense>
  );
}

function SeoCmsContent() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const [user, setUser] = useState<StoredStaffUser | null>(null);
  const [clients, setClients] = useState<SeoHubClientRow[]>([]);
  const [customerId, setCustomerId] = useState('');
  const [baseUrl, setBaseUrl] = useState('');
  const [cmsType, setCmsType] = useState('webhook');
  const [active, setActive] = useState(true);
  const [jobs, setJobs] = useState<Array<Record<string, unknown>>>([]);
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  const [toast, setToast] = useState('');

  const ensureAuth = useCallback(async (): Promise<string | null> => {
    let access = getAccessToken();
    if (!access) { router.replace('/login'); return null; }
    try {
      const me = await staffMe(access);
      setUser(me);
      if (!canViewSeoCms(me)) { setError('Không có quyền CMS pilot'); return null; }
      return access;
    } catch {
      const refresh = getRefreshToken();
      if (!refresh) { clearSession(); router.replace('/login'); return null; }
      const out = await staffRefresh(refresh);
      updateAccessToken(out.access_token);
      return out.access_token;
    }
  }, [router]);

  const loadClient = useCallback(async (token: string, cid: string) => {
    const [targetRes, jobsRes] = await Promise.all([
      fetchSeoCmsTarget(token, Number(cid)),
      fetchSeoCmsJobs(token, Number(cid)),
    ]);
    const target = targetRes.target;
    setBaseUrl(String(target?.base_url ?? ''));
    setCmsType(String(target?.cms_type ?? 'webhook'));
    setActive(target?.active !== false);
    setJobs(jobsRes.jobs ?? []);
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
        if (initial) await loadClient(token, initial);
      } catch (e) {
        setError(e instanceof Error ? e.message : 'Lỗi tải CMS');
      } finally {
        setLoading(false);
      }
    })();
  }, [ensureAuth, loadClient, searchParams]);

  const saveTarget = async () => {
    const token = getAccessToken();
    if (!token || !customerId) return;
    setBusy(true);
    try {
      await upsertSeoCmsTarget(token, Number(customerId), {
        cms_type: cmsType,
        base_url: baseUrl,
        active,
        auth: { send_pilot_secret_header: true },
      });
      setToast('Đã lưu CMS target');
      await loadClient(token, customerId);
    } catch (e) {
      setToast(e instanceof Error ? e.message : 'Lưu thất bại');
    } finally {
      setBusy(false);
    }
  };

  const runTest = async () => {
    const token = getAccessToken();
    if (!token || !customerId) return;
    setBusy(true);
    try {
      const out = await testSeoCmsWebhook(token, Number(customerId));
      setToast(out.ok ? `Webhook OK — ${out.status}` : `Webhook fail — ${out.status}`);
    } catch (e) {
      setToast(e instanceof Error ? e.message : 'Test thất bại');
    } finally {
      setBusy(false);
    }
  };

  if (loading) {
    return (
      <main style={{ padding: '2rem' }}>
        <OpsNav user={user} onLogout={() => { clearSession(); router.replace('/login'); }} />
        <p className="muted">Đang tải CMS pilot…</p>
      </main>
    );
  }

  return (
    <main style={{ padding: '2rem', maxWidth: 960 }}>
      <OpsNav user={user} onLogout={() => { clearSession(); router.replace('/login'); }} />
      <header style={{ marginBottom: '1.5rem' }}>
        <h1>CMS auto-publish pilot (Gate E5)</h1>
        <p className="muted">
          Bật <code>PTT_SEO_CMS_AUTO_PUBLISH=1</code> để queue webhook khi content → published.
          Runbook: <code>docs/runbooks/seo-cms-webhook-pilot.md</code>
        </p>
      </header>

      {error ? <p className="error">{error}</p> : null}
      {toast ? <p className="badge">{toast}</p> : null}

      <section className="card" style={{ marginBottom: '1rem' }}>
        <label>
          Client
          <select
            value={customerId}
            onChange={(e) => {
              const v = e.target.value;
              setCustomerId(v);
              const token = getAccessToken();
              if (token && v) void loadClient(token, v);
            }}
          >
            <option value="">Chọn client</option>
            {clients.map((c) => (
              <option key={c.customer_id} value={String(c.customer_id)}>
                {c.customer_name} (#{c.customer_id})
              </option>
            ))}
          </select>
        </label>

        {customerId ? (
          <div style={{ marginTop: '1rem', display: 'grid', gap: '0.75rem' }}>
            <label>
              CMS type
              <input value={cmsType} onChange={(e) => setCmsType(e.target.value)} />
            </label>
            <label>
              Webhook URL
              <input value={baseUrl} onChange={(e) => setBaseUrl(e.target.value)} placeholder="https://…" />
            </label>
            <label>
              <input type="checkbox" checked={active} onChange={(e) => setActive(e.target.checked)} />
              {' '}Active
            </label>
            <div style={{ display: 'flex', gap: '0.75rem' }}>
              <button type="button" disabled={busy} onClick={() => void saveTarget()}>Lưu target</button>
              <button type="button" disabled={busy} onClick={() => void runTest()}>Test webhook</button>
              <Link href={`/seo/content?customer_id=${customerId}`}>Content pipeline</Link>
            </div>
          </div>
        ) : null}
      </section>

      {jobs.length ? (
        <section className="card">
          <h2>Publish jobs</h2>
          <table className="data-table">
            <thead><tr><th>ID</th><th>Content</th><th>Status</th><th>Remote</th></tr></thead>
            <tbody>
              {jobs.map((j) => (
                <tr key={String(j.id)}>
                  <td>{String(j.id)}</td>
                  <td>{String(j.content_id)}</td>
                  <td>{String(j.status)}</td>
                  <td>{String(j.remote_url ?? '')}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </section>
      ) : null}
    </main>
  );
}
