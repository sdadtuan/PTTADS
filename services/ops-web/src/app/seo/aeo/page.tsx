'use client';

import Link from 'next/link';
import { Suspense, useCallback, useEffect, useState } from 'react';
import { useRouter, useSearchParams } from 'next/navigation';
import { OpsNav } from '@/components/OpsNav';
import {
  createSeoAeoQuery,
  enqueueSeoAeoScan,
  fetchSeoAeoConsole,
  fetchSeoClients,
  staffMe,
  staffRefresh,
  syncSeoAeoScan,
  type SeoAeoQueryRow,
  type SeoHubClientRow,
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
import { canViewSeoAeo, canWriteSeo } from '@/lib/seo/caps';

export default function SeoAeoPage() {
  return (
    <Suspense fallback={<main style={{ padding: '2rem' }}><p className="muted">Đang tải AEO console…</p></main>}>
      <SeoAeoContent />
    </Suspense>
  );
}

function SeoAeoContent() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const [user, setUser] = useState<StoredStaffUser | null>(null);
  const [clients, setClients] = useState<SeoHubClientRow[]>([]);
  const [customerId, setCustomerId] = useState('');
  const [queries, setQueries] = useState<SeoAeoQueryRow[]>([]);
  const [coverage, setCoverage] = useState<Record<string, unknown>>({});
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  const [toast, setToast] = useState('');
  const [newQuery, setNewQuery] = useState('');
  const [newBrand, setNewBrand] = useState('');

  const ensureAuth = useCallback(async (): Promise<string | null> => {
    let access = getAccessToken();
    if (!access) { router.replace('/login'); return null; }
    const cached = getStoredUser();
    if (cached) setUser(cached);
    try {
      const me = await staffMe(access);
      setUser(me);
      updateStoredUser(me);
      if (!canViewSeoAeo(me)) { setError('Không có quyền AEO Console'); return null; }
      return access;
    } catch {
      const refresh = getRefreshToken();
      if (!refresh) { clearSession(); router.replace('/login'); return null; }
      const out = await staffRefresh(refresh);
      updateAccessToken(out.access_token);
      access = out.access_token;
      const me = await staffMe(access);
      setUser(me);
      updateStoredUser(me);
      return access;
    }
  }, [router]);

  const loadData = useCallback(async (access: string, cid: number) => {
    setLoading(true);
    setError('');
    try {
      const out = await fetchSeoAeoConsole(access, cid);
      setQueries(out.queries);
      setCoverage(out.coverage);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Không tải được AEO console');
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

  const canWrite = canWriteSeo(user);

  return (
    <>
      <OpsNav user={user} onLogout={() => { clearSession(); router.replace('/login'); }} />
      <main style={{ padding: '1.5rem 2rem', maxWidth: 1200 }}>
        <header style={{ marginBottom: '1.5rem' }}>
          <h1 style={{ margin: 0 }}>AEO Console</h1>
          <p className="muted">Coverage, batch scan, AI mentions — S-10</p>
        </header>

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
          {coverage.total != null && (
            <div>
              <strong>Coverage: {String(coverage.coverage_pct ?? 0)}%</strong>
              <span className="muted"> ({String(coverage.visible ?? 0)}/{String(coverage.total ?? 0)} visible)</span>
            </div>
          )}
          {canWrite && customerId && (
            <>
              <button type="button" disabled={busy} onClick={() => void (async () => {
                const access = await ensureAuth();
                if (!access) return;
                setBusy(true);
                try {
                  const out = await enqueueSeoAeoScan(access, Number(customerId));
                  setToast(`Scan enqueued (${out.mode})`);
                  await loadData(access, Number(customerId));
                } catch (err) {
                  setError(err instanceof Error ? err.message : 'Scan failed');
                } finally { setBusy(false); }
              })()}>Batch scan (queue)</button>
              <button type="button" disabled={busy} onClick={() => void (async () => {
                const access = await ensureAuth();
                if (!access) return;
                setBusy(true);
                try {
                  await syncSeoAeoScan(access, Number(customerId));
                  setToast('Sync scan hoàn tất');
                  await loadData(access, Number(customerId));
                } catch (err) {
                  setError(err instanceof Error ? err.message : 'Sync scan failed');
                } finally { setBusy(false); }
              })()}>Scan sync (stub)</button>
            </>
          )}
        </div>

        {canWrite && customerId && (
          <div className="card" style={{ marginBottom: '1rem' }}>
            <h2 style={{ marginTop: 0, fontSize: '1rem' }}>Thêm AEO query</h2>
            <div style={{ display: 'flex', gap: '0.75rem', flexWrap: 'wrap' }}>
              <input placeholder="Query text" value={newQuery} onChange={(e) => setNewQuery(e.target.value)} style={{ flex: 2, minWidth: 200 }} />
              <input placeholder="Brand name" value={newBrand} onChange={(e) => setNewBrand(e.target.value)} style={{ flex: 1, minWidth: 120 }} />
              <button type="button" disabled={busy || !newQuery.trim() || !newBrand.trim()} onClick={() => void (async () => {
                const access = await ensureAuth();
                if (!access) return;
                setBusy(true);
                try {
                  await createSeoAeoQuery(access, Number(customerId), { query_text: newQuery.trim(), brand_name: newBrand.trim() });
                  setNewQuery('');
                  setToast('Đã thêm query');
                  await loadData(access, Number(customerId));
                } catch (err) {
                  setError(err instanceof Error ? err.message : 'Thêm query thất bại');
                } finally { setBusy(false); }
              })()}>Thêm</button>
            </div>
          </div>
        )}

        {error && <p className="error">{error}</p>}
        <p className="muted" aria-live="polite" role="status">
          {toast}
        </p>

        {loading ? (
          <p className="muted">Đang tải…</p>
        ) : (
          <div className="card">
            <table style={{ width: '100%', borderCollapse: 'collapse' }}>
              <thead>
                <tr>
                  <th align="left">Query</th>
                  <th align="left">Brand</th>
                  <th align="left">Visible</th>
                  <th align="left">Citation</th>
                  <th align="left">Last scan</th>
                </tr>
              </thead>
              <tbody>
                {queries.map((q) => (
                  <tr key={q.id}>
                    <td>{q.query_text}</td>
                    <td>{q.brand_name}</td>
                    <td>{q.brand_visible ? '✓' : '—'}</td>
                    <td>{q.citation_status}</td>
                    <td className="muted">{q.last_scan_date ?? '—'}</td>
                  </tr>
                ))}
                {!queries.length && (
                  <tr><td colSpan={5} className="muted">Chưa có AEO query — thêm query và chạy scan.</td></tr>
                )}
              </tbody>
            </table>
          </div>
        )}

        <p style={{ marginTop: '1rem' }}>
          <Link href="/seo/hub">← Hub</Link>
          {' · '}
          <Link href={`/seo/clients/${customerId || ''}`}>Client workspace</Link>
        </p>
      </main>
    </>
  );
}
