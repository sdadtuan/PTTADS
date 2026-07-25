'use client';

import Link from 'next/link';
import { Suspense, useCallback, useEffect, useRef, useState } from 'react';
import { useRouter, useSearchParams } from 'next/navigation';
import { OpsNav } from '@/components/OpsNav';
import {
  addSeoRankKeyword,
  captureSeoRanks,
  fetchSeoClients,
  fetchSeoRankKeywords,
  importSeoRankCsv,
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
  updateStoredUser,
  type StoredStaffUser,
} from '@/lib/auth';
import { canViewSeoRanks, canWriteSeo } from '@/lib/seo/caps';

export default function SeoRanksPage() {
  return (
    <Suspense fallback={<main style={{ padding: '2rem' }}><p className="muted">Đang tải rank tracker…</p></main>}>
      <SeoRanksContent />
    </Suspense>
  );
}

function SeoRanksContent() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const fileRef = useRef<HTMLInputElement>(null);
  const [user, setUser] = useState<StoredStaffUser | null>(null);
  const [clients, setClients] = useState<SeoHubClientRow[]>([]);
  const [customerId, setCustomerId] = useState('');
  const [keywords, setKeywords] = useState<Array<Record<string, unknown>>>([]);
  const [sov, setSov] = useState<Record<string, unknown>>({});
  const [phrase, setPhrase] = useState('');
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
      if (!canViewSeoRanks(me)) { setError('Không có quyền Rank Tracker'); return null; }
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
      const out = await fetchSeoRankKeywords(access, cid);
      setKeywords(out.keywords);
      setSov(out.sov);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Không tải ranks');
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
        <h1>Rank Tracker + SOV</h1>
        <p className="muted">Tracked keywords, SERP capture (stub), share of voice — S-17</p>

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
          {sov.sov_pct != null && (
            <div>
              <strong>SOV (top {String(sov.top_n ?? 10)}): {String(sov.sov_pct)}%</strong>
              <span className="muted"> — {String(sov.in_top_n)}/{String(sov.tracked)} keywords</span>
            </div>
          )}
          {canWriteSeo(user) && customerId && (
            <>
              <button type="button" disabled={busy} onClick={() => void (async () => {
                const access = await ensureAuth();
                if (!access) return;
                setBusy(true);
                try {
                  const out = await captureSeoRanks(access, Number(customerId));
                  setToast(`Captured ${String((out.result as { captured?: number }).captured ?? 0)} snapshots`);
                  await loadData(access, Number(customerId));
                } catch (err) {
                  setError(err instanceof Error ? err.message : 'Capture failed');
                } finally { setBusy(false); }
              })()}>Capture ranks (stub)</button>
              <input ref={fileRef} type="file" accept=".csv" style={{ display: 'none' }} onChange={() => void (async () => {
                const file = fileRef.current?.files?.[0];
                if (!file) return;
                const access = await ensureAuth();
                if (!access) return;
                const text = await file.text();
                await importSeoRankCsv(access, Number(customerId), text);
                setToast('CSV imported');
                await loadData(access, Number(customerId));
              })()} />
              <button type="button" onClick={() => fileRef.current?.click()}>Import CSV</button>
            </>
          )}
        </div>

        {canWriteSeo(user) && customerId && (
          <div className="card" style={{ marginBottom: '1rem', display: 'flex', gap: '0.75rem' }}>
            <input placeholder="Keyword phrase" value={phrase} onChange={(e) => setPhrase(e.target.value)} style={{ flex: 1 }} />
            <button type="button" disabled={!phrase.trim() || busy} onClick={() => void (async () => {
              const access = await ensureAuth();
              if (!access) return;
              await addSeoRankKeyword(access, Number(customerId), { phrase: phrase.trim() });
              setPhrase('');
              await loadData(access, Number(customerId));
            })()}>Track keyword</button>
          </div>
        )}

        {error && <p className="error">{error}</p>}
        {toast && <p className="muted">{toast}</p>}

        {loading ? <p className="muted">Đang tải…</p> : (
          <div className="card">
            <table style={{ width: '100%', borderCollapse: 'collapse' }}>
              <thead>
                <tr>
                  <th align="left">Phrase</th>
                  <th align="left">Position</th>
                  <th align="left">Latest date</th>
                  <th align="left">Target URL</th>
                </tr>
              </thead>
              <tbody>
                {keywords.map((k) => (
                  <tr key={String(k.id)}>
                    <td>{String(k.phrase)}</td>
                    <td>{k.latest_position != null ? String(k.latest_position) : '—'}</td>
                    <td className="muted">{k.latest_date != null ? String(k.latest_date) : '—'}</td>
                    <td>{String(k.target_url || '—')}</td>
                  </tr>
                ))}
                {!keywords.length && <tr><td colSpan={4} className="muted">Chưa track keyword nào.</td></tr>}
              </tbody>
            </table>
          </div>
        )}

        <p style={{ marginTop: '1rem' }}><Link href="/seo/hub">← Hub</Link></p>
      </main>
    </>
  );
}
