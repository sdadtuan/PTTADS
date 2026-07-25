'use client';

import Link from 'next/link';
import { Suspense, useCallback, useEffect, useState } from 'react';
import { useRouter, useSearchParams } from 'next/navigation';
import { OpsNav } from '@/components/OpsNav';
import {
  fetchSeoClients,
  fetchSeoFreshnessQueue,
  rescoreSeoFreshness,
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
import { canViewSeoFreshness, canWriteSeo } from '@/lib/seo/caps';

export default function SeoFreshnessPage() {
  return (
    <Suspense fallback={<main style={{ padding: '2rem' }}><p className="muted">Đang tải freshness queue…</p></main>}>
      <SeoFreshnessContent />
    </Suspense>
  );
}

function SeoFreshnessContent() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const [user, setUser] = useState<StoredStaffUser | null>(null);
  const [clients, setClients] = useState<SeoHubClientRow[]>([]);
  const [customerId, setCustomerId] = useState('');
  const [items, setItems] = useState<Array<Record<string, unknown>>>([]);
  const [minPriority, setMinPriority] = useState('');
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
      if (!canViewSeoFreshness(me)) { setError('Không có quyền Freshness'); return null; }
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
      const out = await fetchSeoFreshnessQueue(access, cid, minPriority || undefined);
      setItems(out.items);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Không tải freshness');
    } finally {
      setLoading(false);
    }
  }, [minPriority]);

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
        <h1>Freshness Queue</h1>
        <p className="muted">Decay scoring, refresh priority — port freshness.py</p>

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
          <label>
            Min priority
            <select value={minPriority} onChange={(e) => setMinPriority(e.target.value)} style={{ display: 'block', marginTop: 4 }}>
              <option value="">All</option>
              <option value="low">Low+</option>
              <option value="medium">Medium+</option>
              <option value="high">High+</option>
              <option value="urgent">Urgent</option>
            </select>
          </label>
          {canWriteSeo(user) && customerId && (
            <button type="button" disabled={busy} onClick={() => void (async () => {
              const access = await ensureAuth();
              if (!access) return;
              setBusy(true);
              try {
                const out = await rescoreSeoFreshness(access, Number(customerId));
                setToast(`Rescored ${out.scored} items`);
                await loadData(access, Number(customerId));
              } catch (err) {
                setError(err instanceof Error ? err.message : 'Rescore failed');
              } finally { setBusy(false); }
            })()}>Rescore all</button>
          )}
        </div>

        {error && <p className="error">{error}</p>}
        {toast && <p className="muted">{toast}</p>}

        {loading ? <p className="muted">Đang tải…</p> : (
          <div className="card">
            <table style={{ width: '100%', borderCollapse: 'collapse' }}>
              <thead>
                <tr>
                  <th align="left">Title</th>
                  <th align="left">Decay</th>
                  <th align="left">Priority</th>
                  <th align="left">Age (days)</th>
                  <th align="left">Status</th>
                </tr>
              </thead>
              <tbody>
                {items.map((item) => (
                  <tr key={String(item.id)}>
                    <td>
                      <Link href={`/seo/content/${String(item.content_id)}`}>{String(item.title)}</Link>
                    </td>
                    <td>{String(item.decay_score)}</td>
                    <td>{String(item.refresh_priority)}</td>
                    <td>{String(item.age_days)}</td>
                    <td>{String(item.workflow_status)}</td>
                  </tr>
                ))}
                {!items.length && <tr><td colSpan={5} className="muted">Queue trống — chạy rescore.</td></tr>}
              </tbody>
            </table>
          </div>
        )}

        <p style={{ marginTop: '1rem' }}><Link href="/seo/hub">← Hub</Link> · <Link href="/seo/content">Content pipeline</Link></p>
      </main>
    </>
  );
}
