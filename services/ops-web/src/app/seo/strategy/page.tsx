'use client';

import Link from 'next/link';
import { Suspense, useCallback, useEffect, useState } from 'react';
import { useRouter, useSearchParams } from 'next/navigation';
import { OpsNav } from '@/components/OpsNav';
import {
  createSeoStrategyGoal,
  fetchSeoClients,
  fetchSeoOkrTree,
  refreshSeoStrategyKpis,
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
import { canConfigureSeoSettings, canViewSeoStrategy, canWriteSeo } from '@/lib/seo/caps';

type OkrGoal = Record<string, unknown> & {
  id: number;
  title?: string;
  description?: string;
  period?: string;
  status?: string;
  kpis?: Array<Record<string, unknown>>;
  initiatives?: Array<Record<string, unknown>>;
};

export default function SeoStrategyPage() {
  return (
    <Suspense
      fallback={
        <main style={{ padding: '2rem' }}>
          <p className="muted">Đang tải strategy OKR…</p>
        </main>
      }
    >
      <SeoStrategyContent />
    </Suspense>
  );
}

function SeoStrategyContent() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const [user, setUser] = useState<StoredStaffUser | null>(null);
  const [clients, setClients] = useState<SeoHubClientRow[]>([]);
  const [customerId, setCustomerId] = useState('');
  const [goals, setGoals] = useState<OkrGoal[]>([]);
  const [unlinked, setUnlinked] = useState<Array<Record<string, unknown>>>([]);
  const [loading, setLoading] = useState(true);
  const [refreshBusy, setRefreshBusy] = useState(false);
  const [error, setError] = useState('');
  const [toast, setToast] = useState('');

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
      if (!canViewSeoStrategy(me)) {
        setError('Không có quyền SEO Strategy');
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

  const loadOkr = useCallback(async (access: string, cid: number) => {
    setLoading(true);
    setError('');
    try {
      const out = await fetchSeoOkrTree(access, cid);
      setGoals(out.goals as OkrGoal[]);
      setUnlinked(out.unlinked_initiatives ?? []);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Không tải được OKR tree');
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
      await loadOkr(access, cid);
    })();
  }, [customerId, ensureAuth, loadOkr]);

  const logout = () => {
    clearSession();
    router.push('/login');
  };

  const canWrite = canWriteSeo(user);
  const canRefresh = canConfigureSeoSettings(user);

  async function handleAddGoal() {
    if (!canWrite || !customerId) return;
    const title = window.prompt('Tên goal (OKR)');
    if (!title?.trim()) return;
    const access = await ensureAuth();
    if (!access) return;
    try {
      await createSeoStrategyGoal(access, Number.parseInt(customerId, 10), { title: title.trim() });
      setToast(`Đã tạo goal "${title.trim()}"`);
      await loadOkr(access, Number.parseInt(customerId, 10));
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Tạo goal thất bại');
    }
  }

  async function handleRefreshKpis() {
    if (!canRefresh || !customerId) return;
    const access = await ensureAuth();
    if (!access) return;
    setRefreshBusy(true);
    try {
      const out = await refreshSeoStrategyKpis(access, Number.parseInt(customerId, 10));
      setToast(`Đã refresh ${out.updated} KPI`);
      await loadOkr(access, Number.parseInt(customerId, 10));
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Refresh KPI thất bại');
    } finally {
      setRefreshBusy(false);
    }
  }

  return (
    <div className="page">
      <OpsNav user={user} onLogout={logout} />
      <main className="main-content">
        <div className="page-header">
          <div>
            <h1>Strategy OKR</h1>
            <p className="muted">S-05 · Goals → KPIs → Initiatives</p>
          </div>
          <div className="page-actions">
            <Link href="/seo/hub" className="btn btn-secondary btn-sm">
              Hub
            </Link>
            <Link href="/seo/reports" className="btn btn-secondary btn-sm">
              Báo cáo
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
            {canWrite && (
              <button type="button" className="btn btn-sm" onClick={() => void handleAddGoal()}>
                + Goal
              </button>
            )}
            {canRefresh && (
              <button
                type="button"
                className="btn btn-secondary btn-sm"
                disabled={refreshBusy}
                onClick={() => void handleRefreshKpis()}
              >
                {refreshBusy ? 'Đang refresh…' : 'Refresh KPIs'}
              </button>
            )}
          </div>
        </div>

        {error && <p className="error">{error}</p>}
        {toast && <p className="badge">{toast}</p>}

        {!customerId ? (
          <p className="muted">Chọn client để xem OKR tree.</p>
        ) : loading ? (
          <p className="muted">Đang tải…</p>
        ) : goals.length === 0 && unlinked.length === 0 ? (
          <p className="muted">Chưa có goal — thêm goal hoặc seed initiatives.</p>
        ) : (
          <>
            {goals.map((goal) => (
              <div key={goal.id} className="card" style={{ marginBottom: '1rem' }}>
                <h2 style={{ marginTop: 0, fontSize: '1.1rem' }}>
                  {String(goal.title ?? `Goal #${goal.id}`)}
                  {goal.period ? (
                    <span className="muted" style={{ fontWeight: 'normal', marginLeft: '0.5rem' }}>
                      · {String(goal.period)}
                    </span>
                  ) : null}
                </h2>
                {goal.description ? <p className="muted">{String(goal.description)}</p> : null}
                <p className="muted" style={{ fontSize: '0.85rem' }}>
                  Status: {String(goal.status ?? 'active')}
                </p>

                {(goal.kpis ?? []).length > 0 && (
                  <div className="table-wrap" style={{ marginBottom: '0.75rem' }}>
                    <table>
                      <thead>
                        <tr>
                          <th>KPI</th>
                          <th>Current</th>
                          <th>Target</th>
                          <th>Unit</th>
                        </tr>
                      </thead>
                      <tbody>
                        {(goal.kpis ?? []).map((kpi, idx) => (
                          <tr key={String(kpi.id ?? idx)}>
                            <td>{String(kpi.metric_label ?? kpi.metric_key ?? '—')}</td>
                            <td>{String(kpi.current_value ?? '—')}</td>
                            <td>{String(kpi.target_value ?? '—')}</td>
                            <td>{String(kpi.unit ?? '—')}</td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                )}

                {(goal.initiatives ?? []).length > 0 && (
                  <>
                    <h3 style={{ fontSize: '0.95rem', margin: '0 0 0.5rem' }}>Initiatives</h3>
                    <ul style={{ margin: 0, paddingLeft: '1.2rem' }}>
                      {(goal.initiatives ?? []).map((init, idx) => (
                        <li key={String(init.id ?? idx)} style={{ marginBottom: '0.35rem' }}>
                          <strong>{String(init.title ?? init.name ?? `Initiative #${init.id}`)}</strong>
                          {init.status ? (
                            <span className="muted"> · {String(init.status)}</span>
                          ) : null}
                        </li>
                      ))}
                    </ul>
                  </>
                )}
              </div>
            ))}

            {unlinked.length > 0 && (
              <div className="card">
                <h2 style={{ marginTop: 0, fontSize: '1.1rem' }}>Initiatives chưa gắn goal</h2>
                <ul style={{ margin: 0, paddingLeft: '1.2rem' }}>
                  {unlinked.map((init, idx) => (
                    <li key={String(init.id ?? idx)} style={{ marginBottom: '0.35rem' }}>
                      {String(init.title ?? init.name ?? `Initiative #${init.id}`)}
                    </li>
                  ))}
                </ul>
              </div>
            )}
          </>
        )}
      </main>
    </div>
  );
}
