'use client';

import { useCallback, useEffect, useState } from 'react';
import { useRouter } from 'next/navigation';
import { OpsNav } from '@/components/OpsNav';
import {
  createSalesMarketEntry,
  createSalesPartner,
  createSalesPlan,
  createSalesTraining,
  fetchSalesMarket,
  fetchSalesPartners,
  fetchSalesPipelineCases,
  fetchSalesPlans,
  fetchSalesReports,
  fetchSalesSummary,
  fetchSalesTrainings,
  fetchSalesTransactions,
  staffMe,
  staffRefresh,
  type SalesPlanRow,
} from '@/lib/api';
import {
  clearSession,
  getAccessToken,
  getRefreshToken,
  getStoredUser,
  hasCap,
  updateAccessToken,
  updateStoredUser,
  type StoredStaffUser,
} from '@/lib/auth';

type SalesTab = 'plans' | 'funnel' | 'partners' | 'trainings' | 'market' | 'reports';

export default function CrmSalesPage() {
  const router = useRouter();
  const [user, setUser] = useState<StoredStaffUser | null>(null);
  const [tab, setTab] = useState<SalesTab>('plans');
  const [plans, setPlans] = useState<SalesPlanRow[]>([]);
  const [counts, setCounts] = useState<Record<string, number>>({});
  const [rows, setRows] = useState<Array<Record<string, unknown>>>([]);
  const [report, setReport] = useState<Record<string, unknown> | null>(null);
  const [newTitle, setNewTitle] = useState('');
  const [newPartnerName, setNewPartnerName] = useState('');
  const [newTrainingTitle, setNewTrainingTitle] = useState('');
  const [newMarketTitle, setNewMarketTitle] = useState('');
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(false);
  const [saving, setSaving] = useState(false);

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
      if (!hasCap(me, 'crm_sales_overview', 'view') && !hasCap(me, 'crm_sales_plans', 'view')) {
        setError('Không có quyền kinh doanh');
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

  const loadTab = useCallback(
    async (access: string, nextTab: SalesTab) => {
      setLoading(true);
      setError('');
      try {
        if (nextTab === 'plans') {
          const [summary, planRows] = await Promise.all([fetchSalesSummary(access), fetchSalesPlans(access)]);
          setCounts(summary.counts ?? {});
          setPlans(planRows);
          setRows([]);
          setReport(null);
        } else if (nextTab === 'funnel') {
          setRows(await fetchSalesPipelineCases(access));
        } else if (nextTab === 'partners') {
          setRows(await fetchSalesPartners(access));
        } else if (nextTab === 'trainings') {
          setRows(await fetchSalesTrainings(access));
        } else if (nextTab === 'market') {
          setRows(await fetchSalesMarket(access));
        } else if (nextTab === 'reports') {
          const [tx, rep] = await Promise.all([fetchSalesTransactions(access), fetchSalesReports(access)]);
          setRows(tx);
          setReport(rep);
        }
      } catch (err) {
        setError(err instanceof Error ? err.message : 'Tải sales thất bại');
      } finally {
        setLoading(false);
      }
    },
    [],
  );

  useEffect(() => {
    void (async () => {
      const access = await ensureAuth();
      if (!access) return;
      await loadTab(access, tab);
    })();
  }, [ensureAuth, tab, loadTab]);

  async function onCreatePlan(e: React.FormEvent) {
    e.preventDefault();
    if (!newTitle.trim()) return;
    const access = getAccessToken();
    if (!access) return;
    setSaving(true);
    try {
      await createSalesPlan(access, { title: newTitle.trim() });
      setNewTitle('');
      await loadTab(access, 'plans');
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Tạo plan thất bại');
    } finally {
      setSaving(false);
    }
  }

  async function onCreatePartner(e: React.FormEvent) {
    e.preventDefault();
    if (!newPartnerName.trim()) return;
    const access = getAccessToken();
    if (!access) return;
    setSaving(true);
    try {
      await createSalesPartner(access, { name: newPartnerName.trim() });
      setNewPartnerName('');
      await loadTab(access, 'partners');
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Tạo đối tác thất bại');
    } finally {
      setSaving(false);
    }
  }

  async function onCreateTraining(e: React.FormEvent) {
    e.preventDefault();
    if (!newTrainingTitle.trim()) return;
    const access = getAccessToken();
    if (!access) return;
    setSaving(true);
    try {
      await createSalesTraining(access, { title: newTrainingTitle.trim() });
      setNewTrainingTitle('');
      await loadTab(access, 'trainings');
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Tạo training thất bại');
    } finally {
      setSaving(false);
    }
  }

  async function onCreateMarket(e: React.FormEvent) {
    e.preventDefault();
    if (!newMarketTitle.trim()) return;
    const access = getAccessToken();
    if (!access) return;
    setSaving(true);
    try {
      await createSalesMarketEntry(access, { title: newMarketTitle.trim() });
      setNewMarketTitle('');
      await loadTab(access, 'market');
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Tạo nghiên cứu thất bại');
    } finally {
      setSaving(false);
    }
  }

  function logout() {
    clearSession();
    router.push('/login');
  }

  const tabs: Array<{ id: SalesTab; label: string; cap?: boolean }> = [
    { id: 'plans', label: 'Plans' },
    { id: 'funnel', label: 'Funnel', cap: hasCap(user, 'crm_sales_funnel', 'view') },
    { id: 'partners', label: 'Partners' },
    { id: 'trainings', label: 'Training' },
    { id: 'market', label: 'Market' },
    { id: 'reports', label: 'Reports' },
  ];

  if (!user) {
    return (
      <main style={{ padding: '2rem' }}>
        <p className="muted">Đang tải…</p>
      </main>
    );
  }

  return (
    <main style={{ maxWidth: 960, margin: '0 auto', padding: '1.5rem' }}>
      <OpsNav user={user} onLogout={logout} />
      <div className="card">
        <h2 style={{ marginTop: 0, fontSize: '1.15rem' }}>Kinh doanh</h2>
        <div style={{ display: 'flex', gap: '0.35rem', flexWrap: 'wrap', marginBottom: '1rem' }}>
          {tabs
            .filter((t) => t.cap !== false)
            .map((t) => (
              <button
                key={t.id}
                type="button"
                className={`btn btn-sm${tab === t.id ? '' : ' btn-secondary'}`}
                onClick={() => setTab(t.id)}
              >
                {t.label}
              </button>
            ))}
        </div>
        {loading ? <p className="muted">Đang tải…</p> : null}
        {error ? <p className="error">{error}</p> : null}

        {tab === 'plans' ? (
          <>
            {Object.keys(counts).length > 0 ? (
              <p className="muted">
                Đối tác active {counts.partners_active ?? 0} · Giao dịch mở {counts.transactions_open ?? 0} · NV KD{' '}
                {counts.kd_staff ?? 0}
              </p>
            ) : null}
            <ul style={{ margin: '0 0 1rem', paddingLeft: '1.1rem' }}>
              {plans.map((p) => (
                <li key={p.id}>
                  #{p.id} · {p.title} — {p.status} · FY{p.fiscal_year}
                </li>
              ))}
            </ul>
            {hasCap(user, 'crm_sales_plans', 'create') ? (
              <form onSubmit={(e) => void onCreatePlan(e)} style={{ display: 'flex', gap: '0.5rem' }}>
                <input
                  value={newTitle}
                  onChange={(e) => setNewTitle(e.target.value)}
                  placeholder="Tên kế hoạch KD mới"
                  disabled={saving}
                  style={{
                    flex: 1,
                    background: 'var(--bg)',
                    border: '1px solid var(--border)',
                    borderRadius: 8,
                    padding: '0.55rem 0.75rem',
                    color: 'var(--text)',
                  }}
                />
                <button type="submit" className="btn btn-secondary btn-sm" disabled={saving || !newTitle.trim()}>
                  + Plan
                </button>
              </form>
            ) : null}
          </>
        ) : null}

        {tab === 'funnel' ? (
          <ul style={{ margin: 0, paddingLeft: '1.1rem' }}>
            {rows.map((r, i) => (
              <li key={String(r.id ?? i)}>
                {String(r.title ?? '—')} · {String(r.pipeline_stage ?? '—')} ·{' '}
                {Number(r.deal_value_vnd ?? 0).toLocaleString('vi-VN')} VND
              </li>
            ))}
          </ul>
        ) : null}

        {tab === 'partners' ? (
          <>
            <ul style={{ margin: '0 0 1rem', paddingLeft: '1.1rem' }}>
              {rows.map((r, i) => (
                <li key={String(r.id ?? i)}>
                  {String(r.name ?? '—')} · {String(r.status ?? '—')}
                </li>
              ))}
            </ul>
            {hasCap(user, 'crm_sales_prospects', 'create') || hasCap(user, 'crm_sales_plans', 'create') ? (
              <form onSubmit={(e) => void onCreatePartner(e)} style={{ display: 'flex', gap: '0.5rem' }}>
                <input
                  value={newPartnerName}
                  onChange={(e) => setNewPartnerName(e.target.value)}
                  placeholder="Tên đối tác"
                  disabled={saving}
                  style={{
                    flex: 1,
                    background: 'var(--bg)',
                    border: '1px solid var(--border)',
                    borderRadius: 8,
                    padding: '0.55rem 0.75rem',
                    color: 'var(--text)',
                  }}
                />
                <button type="submit" className="btn btn-secondary btn-sm" disabled={saving || !newPartnerName.trim()}>
                  + Partner
                </button>
              </form>
            ) : null}
          </>
        ) : null}

        {tab === 'trainings' ? (
          <>
            <ul style={{ margin: '0 0 1rem', paddingLeft: '1.1rem' }}>
              {rows.map((r, i) => (
                <li key={String(r.id ?? i)}>{String(r.title ?? '—')}</li>
              ))}
            </ul>
            {hasCap(user, 'crm_sales_training', 'create') || hasCap(user, 'crm_sales_plans', 'create') ? (
              <form onSubmit={(e) => void onCreateTraining(e)} style={{ display: 'flex', gap: '0.5rem' }}>
                <input
                  value={newTrainingTitle}
                  onChange={(e) => setNewTrainingTitle(e.target.value)}
                  placeholder="Tiêu đề training"
                  disabled={saving}
                  style={{
                    flex: 1,
                    background: 'var(--bg)',
                    border: '1px solid var(--border)',
                    borderRadius: 8,
                    padding: '0.55rem 0.75rem',
                    color: 'var(--text)',
                  }}
                />
                <button
                  type="submit"
                  className="btn btn-secondary btn-sm"
                  disabled={saving || !newTrainingTitle.trim()}
                >
                  + Training
                </button>
              </form>
            ) : null}
          </>
        ) : null}

        {tab === 'market' ? (
          <>
            <ul style={{ margin: '0 0 1rem', paddingLeft: '1.1rem' }}>
              {rows.map((r, i) => (
                <li key={String(r.id ?? i)}>{String(r.title ?? '—')}</li>
              ))}
            </ul>
            {hasCap(user, 'crm_sales_market', 'create') || hasCap(user, 'crm_sales_plans', 'create') ? (
              <form onSubmit={(e) => void onCreateMarket(e)} style={{ display: 'flex', gap: '0.5rem' }}>
                <input
                  value={newMarketTitle}
                  onChange={(e) => setNewMarketTitle(e.target.value)}
                  placeholder="Tiêu đề nghiên cứu"
                  disabled={saving}
                  style={{
                    flex: 1,
                    background: 'var(--bg)',
                    border: '1px solid var(--border)',
                    borderRadius: 8,
                    padding: '0.55rem 0.75rem',
                    color: 'var(--text)',
                  }}
                />
                <button type="submit" className="btn btn-secondary btn-sm" disabled={saving || !newMarketTitle.trim()}>
                  + Research
                </button>
              </form>
            ) : null}
          </>
        ) : null}

        {tab === 'reports' ? (
          <>
            {report ? (
              <pre
                style={{
                  background: 'var(--bg)',
                  border: '1px solid var(--border)',
                  borderRadius: 8,
                  padding: '0.75rem',
                  overflow: 'auto',
                  fontSize: '0.85rem',
                }}
              >
                {JSON.stringify(report, null, 2)}
              </pre>
            ) : null}
            <ul style={{ margin: '1rem 0 0', paddingLeft: '1.1rem' }}>
              {rows.map((r, i) => (
                <li key={String(r.id ?? i)}>
                  {String(r.title ?? r.reference ?? '—')} · {String(r.status ?? '—')}
                </li>
              ))}
            </ul>
          </>
        ) : null}
      </div>
    </main>
  );
}
