'use client';

import Link from 'next/link';
import { Suspense, useCallback, useEffect, useState } from 'react';
import { useRouter, useSearchParams } from 'next/navigation';
import { OpsNav } from '@/components/OpsNav';
import {
  createSeoExperiment,
  fetchSeoClients,
  fetchSeoExperiments,
  fetchSeoExperimentsStatus,
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
import { canViewSeoExperiments, canWriteSeo } from '@/lib/seo/caps';

export default function SeoExperimentsPage() {
  return (
    <Suspense fallback={<main style={{ padding: '2rem' }}><p className="muted">Đang tải experiments…</p></main>}>
      <SeoExperimentsContent />
    </Suspense>
  );
}

function SeoExperimentsContent() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const [user, setUser] = useState<StoredStaffUser | null>(null);
  const [clients, setClients] = useState<SeoHubClientRow[]>([]);
  const [customerId, setCustomerId] = useState('');
  const [enabled, setEnabled] = useState(false);
  const [experiments, setExperiments] = useState<Array<Record<string, unknown>>>([]);
  const [title, setTitle] = useState('');
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [toast, setToast] = useState('');

  const ensureAuth = useCallback(async (): Promise<string | null> => {
    let access = getAccessToken();
    if (!access) { router.replace('/login'); return null; }
    try {
      const me = await staffMe(access);
      setUser(me);
      if (!canViewSeoExperiments(me)) { setError('Experiments chưa bật hoặc không có quyền'); return null; }
      return access;
    } catch {
      const refresh = getRefreshToken();
      if (!refresh) { clearSession(); router.replace('/login'); return null; }
      const out = await staffRefresh(refresh);
      updateAccessToken(out.access_token);
      return out.access_token;
    }
  }, [router]);

  const loadData = useCallback(async (access: string, cid: number) => {
    setLoading(true);
    try {
      const status = await fetchSeoExperimentsStatus(access);
      setEnabled(status.enabled);
      if (!status.enabled) {
        setExperiments([]);
        return;
      }
      const out = await fetchSeoExperiments(access, cid);
      setExperiments(out.experiments);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Không tải experiments');
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
    const cid = Number.parseInt(customerId, 10);
    if (!customerId || Number.isNaN(cid)) return;
    void (async () => {
      const access = await ensureAuth();
      if (!access) return;
      await loadData(access, cid);
    })();
  }, [customerId, ensureAuth, loadData]);

  return (
    <>
      <OpsNav user={user} onLogout={() => { clearSession(); router.replace('/login'); }} />
      <main style={{ padding: '1.5rem 2rem', maxWidth: 1200 }}>
        <h1>SEO Experiments</h1>
        <p className="muted">Hypothesis testing — S-16 (PTT_SEO_EXPERIMENTS_ENABLED=1)</p>

        {!enabled && !loading && (
          <div className="card" style={{ marginBottom: '1rem' }}>
            <p>Experiments disabled. Set <code>PTT_SEO_EXPERIMENTS_ENABLED=1</code> on API và <code>NEXT_PUBLIC_PTT_SEO_EXPERIMENTS_ENABLED=1</code> trên ops-web.</p>
          </div>
        )}

        <div className="card" style={{ marginBottom: '1rem', display: 'flex', gap: '1rem', flexWrap: 'wrap', alignItems: 'end' }}>
          <label>
            Client
            <select value={customerId} onChange={(e) => setCustomerId(e.target.value)} style={{ display: 'block', marginTop: 4 }}>
              <option value="">— chọn —</option>
              {clients.map((c) => (
                <option key={c.customer_id} value={c.customer_id}>{c.customer_name}</option>
              ))}
            </select>
          </label>
        </div>

        {enabled && canWriteSeo(user) && customerId && (
          <div className="card" style={{ marginBottom: '1rem', display: 'flex', gap: '0.75rem' }}>
            <input placeholder="Experiment title" value={title} onChange={(e) => setTitle(e.target.value)} style={{ flex: 1 }} />
            <button type="button" disabled={!title.trim()} onClick={() => void (async () => {
              const access = await ensureAuth();
              if (!access) return;
              await createSeoExperiment(access, Number(customerId), { title: title.trim() });
              setTitle('');
              setToast('Experiment created');
              await loadData(access, Number(customerId));
            })()}>Create draft</button>
          </div>
        )}

        {error && <p className="error">{error}</p>}
        {toast && <p className="muted">{toast}</p>}

        {loading ? <p className="muted">Đang tải…</p> : enabled && (
          <div className="card">
            <table style={{ width: '100%', borderCollapse: 'collapse' }}>
              <thead>
                <tr><th align="left">Title</th><th align="left">Type</th><th align="left">Status</th><th align="left">Updated</th></tr>
              </thead>
              <tbody>
                {experiments.map((e) => (
                  <tr key={String(e.id)}>
                    <td>{String(e.title)}</td>
                    <td>{String(e.experiment_type)}</td>
                    <td>{String(e.status)}</td>
                    <td className="muted">{String(e.updated_at ?? '—')}</td>
                  </tr>
                ))}
                {!experiments.length && <tr><td colSpan={4} className="muted">Chưa có experiment.</td></tr>}
              </tbody>
            </table>
          </div>
        )}

        <p style={{ marginTop: '1rem' }}><Link href="/seo/hub">← Hub</Link></p>
      </main>
    </>
  );
}
