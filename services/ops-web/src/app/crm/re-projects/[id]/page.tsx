'use client';

import Link from 'next/link';
import { useCallback, useEffect, useState } from 'react';
import { useParams, useRouter } from 'next/navigation';
import { OpsNav } from '@/components/OpsNav';
import {
  addReProjectStaff,
  createReProjectBudgetLine,
  createReProjectCashFlow,
  createReProjectKpi,
  createReProjectRisk,
  exportReProject,
  exportReProjectAccounting,
  fetchReProjectAccountingDashboard,
  fetchReProjectAccountingForecast,
  fetchReProjectAccountingRisks,
  fetchReProjectBudget,
  fetchReProjectCashFlow,
  fetchReProjectDetail,
  fetchReProjectInventoryByZone,
  fetchReProjectKpis,
  fetchReProjectLeadConfig,
  fetchReProjectProducts,
  fetchReProjectRisks,
  fetchReProjectStaff,
  fetchReProjectSummary,
  fetchReProjectWorkflow,
  pullReProjectKpisFromStaff,
  refreshReProjectLeadsNewKpi,
  saveReProjectLeadConfig,
  syncReProjectAccountingFromPlans,
  syncReProjectAccountingInventory,
  syncReProjectKpisToStaff,
  staffMe,
  staffRefresh,
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

type DetailTab =
  | 'summary'
  | 'products'
  | 'inventory'
  | 'kpi'
  | 'budget'
  | 'risks'
  | 'accounting'
  | 'staff'
  | 'lead-config'
  | 'workflow'
  | 'export';

export default function CrmReProjectDetailPage() {
  const router = useRouter();
  const params = useParams();
  const projectId = Number(params.id);
  const [user, setUser] = useState<StoredStaffUser | null>(null);
  const [project, setProject] = useState<Record<string, unknown> | null>(null);
  const [summary, setSummary] = useState<Record<string, unknown> | null>(null);
  const [products, setProducts] = useState<Array<Record<string, unknown>>>([]);
  const [zones, setZones] = useState<Array<Record<string, unknown>>>([]);
  const [kpis, setKpis] = useState<Array<Record<string, unknown>>>([]);
  const [kpiBoard, setKpiBoard] = useState<Record<string, unknown> | null>(null);
  const [budgetLines, setBudgetLines] = useState<Array<Record<string, unknown>>>([]);
  const [projectRisks, setProjectRisks] = useState<Array<Record<string, unknown>>>([]);
  const [accounting, setAccounting] = useState<Record<string, unknown> | null>(null);
  const [cashFlow, setCashFlow] = useState<Array<Record<string, unknown>>>([]);
  const [forecast, setForecast] = useState<Record<string, unknown> | null>(null);
  const [riskPack, setRiskPack] = useState<Record<string, unknown> | null>(null);
  const [projectStaff, setProjectStaff] = useState<Array<Record<string, unknown>>>([]);
  const [leadConfig, setLeadConfig] = useState<Record<string, unknown> | null>(null);
  const [workflow, setWorkflow] = useState<Record<string, unknown> | null>(null);
  const [newStaffId, setNewStaffId] = useState('');
  const [leadPageId, setLeadPageId] = useState('');
  const [exportReport, setExportReport] = useState('full');
  const [newLineItem, setNewLineItem] = useState('');
  const [newAmount, setNewAmount] = useState('');
  const [newKpiName, setNewKpiName] = useState('');
  const [newBudgetItem, setNewBudgetItem] = useState('');
  const [newRiskTitle, setNewRiskTitle] = useState('');
  const [tab, setTab] = useState<DetailTab>('summary');
  const [acctView, setAcctView] = useState<'dashboard' | 'cashflow' | 'forecast' | 'risks'>('dashboard');
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
      if (!hasCap(me, 'crm_re_projects', 'view') && !hasCap(me, 'crm_re_projects_products', 'view')) {
        setError('Không có quyền');
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

  const reloadAccounting = useCallback(async (access: string) => {
    const [dash, lines, fc, risks] = await Promise.all([
      fetchReProjectAccountingDashboard(access, projectId),
      fetchReProjectCashFlow(access, projectId),
      fetchReProjectAccountingForecast(access, projectId),
      fetchReProjectAccountingRisks(access, projectId),
    ]);
    setAccounting(dash);
    setCashFlow(lines);
    setForecast(fc);
    setRiskPack(risks);
  }, [projectId]);

  const reloadKpiBudgetRisks = useCallback(async (access: string) => {
    const me = getStoredUser();
    const tasks: Promise<void>[] = [];
    if (hasCap(me, 'crm_re_projects_kpi', 'view')) {
      tasks.push(
        fetchReProjectKpis(access, projectId).then((out) => {
          setKpis(out.kpis ?? []);
          setKpiBoard(out.board ?? null);
        }),
      );
    }
    if (hasCap(me, 'crm_re_projects_budget', 'view')) {
      tasks.push(fetchReProjectBudget(access, projectId).then(setBudgetLines));
    }
    if (hasCap(me, 'crm_re_projects_risks', 'view')) {
      tasks.push(fetchReProjectRisks(access, projectId).then(setProjectRisks));
    }
    await Promise.all(tasks);
  }, [projectId]);

  const reloadOpsTabs = useCallback(async (access: string) => {
    const me = getStoredUser();
    const tasks: Promise<void>[] = [];
    if (hasCap(me, 'crm_re_projects', 'view')) {
      tasks.push(fetchReProjectStaff(access, projectId).then(setProjectStaff));
      tasks.push(fetchReProjectLeadConfig(access, projectId).then(setLeadConfig));
      tasks.push(fetchReProjectWorkflow(access, projectId).then(setWorkflow));
    }
    await Promise.all(tasks);
  }, [projectId]);

  useEffect(() => {
    if (!Number.isFinite(projectId) || projectId <= 0) return;
    void (async () => {
      const access = await ensureAuth();
      if (!access) return;
      setLoading(true);
      setError('');
      try {
        const [detail, sum, prods, inv] = await Promise.all([
          fetchReProjectDetail(access, projectId),
          fetchReProjectSummary(access, projectId),
          fetchReProjectProducts(access, projectId),
          fetchReProjectInventoryByZone(access, projectId),
        ]);
        setProject(detail);
        setSummary(sum);
        setProducts(prods);
        setZones(inv);
        const reloads: Promise<void>[] = [reloadKpiBudgetRisks(access), reloadOpsTabs(access)];
        if (hasCap(getStoredUser(), 'crm_re_projects_budget', 'view')) {
          reloads.push(reloadAccounting(access));
        }
        await Promise.all(reloads);
      } catch (err) {
        setError(err instanceof Error ? err.message : 'Tải dự án thất bại');
      } finally {
        setLoading(false);
      }
    })();
  }, [ensureAuth, projectId, reloadAccounting, reloadKpiBudgetRisks, reloadOpsTabs]);

  async function onAddStaff(e: React.FormEvent) {
    e.preventDefault();
    const sid = Number(newStaffId);
    if (!Number.isFinite(sid) || sid <= 0) return;
    const access = getAccessToken();
    if (!access) return;
    setSaving(true);
    setError('');
    try {
      await addReProjectStaff(access, projectId, { staff_id: sid, role: 'sales' });
      setNewStaffId('');
      await reloadOpsTabs(access);
      setTab('staff');
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Thêm nhân sự thất bại');
    } finally {
      setSaving(false);
    }
  }

  async function onSaveLeadConfig() {
    const access = getAccessToken();
    if (!access) return;
    setSaving(true);
    setError('');
    try {
      const cfg = await saveReProjectLeadConfig(access, projectId, {
        facebook_page_id: leadPageId.trim(),
        enabled: true,
        webhook_enabled: true,
        auto_assign: true,
      });
      setLeadConfig(cfg);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Lưu lead config thất bại');
    } finally {
      setSaving(false);
    }
  }

  async function onExportProject() {
    const access = getAccessToken();
    if (!access) return;
    setError('');
    try {
      const bundle = await exportReProject(access, projectId, exportReport);
      const blob = new Blob([JSON.stringify(bundle, null, 2)], { type: 'application/json' });
      const url = URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = String((bundle as Record<string, unknown>).filename ?? `re-${projectId}.json`);
      a.click();
      URL.revokeObjectURL(url);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Export thất bại');
    }
  }

  async function onSyncPlans() {
    const access = getAccessToken();
    if (!access) return;
    setSaving(true);
    setError('');
    try {
      await syncReProjectAccountingFromPlans(access, projectId);
      await reloadAccounting(access);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Sync KH thất bại');
    } finally {
      setSaving(false);
    }
  }

  async function onSyncInventory() {
    const access = getAccessToken();
    if (!access) return;
    setSaving(true);
    setError('');
    try {
      await syncReProjectAccountingInventory(access, projectId);
      await reloadAccounting(access);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Sync tồn kho thất bại');
    } finally {
      setSaving(false);
    }
  }

  async function onAddCashFlow(e: React.FormEvent) {
    e.preventDefault();
    if (!newLineItem.trim()) return;
    const access = getAccessToken();
    if (!access) return;
    setSaving(true);
    setError('');
    try {
      await createReProjectCashFlow(access, projectId, {
        line_item: newLineItem.trim(),
        amount_vnd: Number(newAmount) || 0,
        flow_type: 'outflow',
        category: 'other',
      });
      setNewLineItem('');
      setNewAmount('');
      await reloadAccounting(access);
      setAcctView('cashflow');
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Thêm dòng tiền thất bại');
    } finally {
      setSaving(false);
    }
  }

  async function onAddKpi(e: React.FormEvent) {
    e.preventDefault();
    if (!newKpiName.trim()) return;
    const access = getAccessToken();
    if (!access) return;
    setSaving(true);
    setError('');
    try {
      await createReProjectKpi(access, projectId, {
        metric_name: newKpiName.trim(),
        category: 'sales',
        track_status: 'active',
      });
      setNewKpiName('');
      await reloadKpiBudgetRisks(access);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Thêm KPI thất bại');
    } finally {
      setSaving(false);
    }
  }

  async function onSyncKpisToStaff() {
    const access = getAccessToken();
    if (!access) return;
    setSaving(true);
    setError('');
    try {
      await syncReProjectKpisToStaff(access, projectId);
      await reloadKpiBudgetRisks(access);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Đồng bộ KPI thất bại');
    } finally {
      setSaving(false);
    }
  }

  async function onPullKpisFromStaff() {
    const access = getAccessToken();
    if (!access) return;
    setSaving(true);
    setError('');
    try {
      await pullReProjectKpisFromStaff(access, projectId);
      await reloadKpiBudgetRisks(access);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Kéo KPI thất bại');
    } finally {
      setSaving(false);
    }
  }

  async function onRefreshLeadsNewKpi() {
    const access = getAccessToken();
    if (!access) return;
    setSaving(true);
    setError('');
    try {
      await refreshReProjectLeadsNewKpi(access, projectId);
      await reloadKpiBudgetRisks(access);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Refresh lead KPI thất bại');
    } finally {
      setSaving(false);
    }
  }

  async function onAddBudgetLine(e: React.FormEvent) {
    e.preventDefault();
    if (!newBudgetItem.trim()) return;
    const access = getAccessToken();
    if (!access) return;
    setSaving(true);
    setError('');
    try {
      await createReProjectBudgetLine(access, projectId, {
        line_item: newBudgetItem.trim(),
        category: 'revenue',
      });
      setNewBudgetItem('');
      await reloadKpiBudgetRisks(access);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Thêm ngân sách thất bại');
    } finally {
      setSaving(false);
    }
  }

  async function onAddRisk(e: React.FormEvent) {
    e.preventDefault();
    if (!newRiskTitle.trim()) return;
    const access = getAccessToken();
    if (!access) return;
    setSaving(true);
    setError('');
    try {
      await createReProjectRisk(access, projectId, {
        title: newRiskTitle.trim(),
        category: 'market',
        risk_level: 'medium',
      });
      setNewRiskTitle('');
      await reloadKpiBudgetRisks(access);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Thêm rủi ro thất bại');
    } finally {
      setSaving(false);
    }
  }

  async function onExportAccounting() {
    const access = getAccessToken();
    if (!access) return;
    setError('');
    try {
      const bundle = await exportReProjectAccounting(access, projectId);
      const blob = new Blob([JSON.stringify(bundle, null, 2)], { type: 'application/json' });
      const url = URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = `re-accounting-${projectId}.json`;
      a.click();
      URL.revokeObjectURL(url);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Export thất bại');
    }
  }

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

  const canKpiView = hasCap(user, 'crm_re_projects_kpi', 'view');
  const canKpiEdit =
    hasCap(user, 'crm_re_projects_kpi', 'edit') || hasCap(user, 'crm_re_projects_kpi', 'create');
  const canBudgetView = hasCap(user, 'crm_re_projects_budget', 'view');
  const canBudgetEdit =
    hasCap(user, 'crm_re_projects_budget', 'edit') || hasCap(user, 'crm_re_projects_budget', 'create');
  const canBudgetExport =
    hasCap(user, 'crm_re_projects_budget', 'export') ||
    hasCap(user, 'crm_re_projects_budget', 'view') ||
    hasCap(user, 'crm_re_projects_budget', 'edit');
  const canRisksView = hasCap(user, 'crm_re_projects_risks', 'view');
  const canRisksEdit =
    hasCap(user, 'crm_re_projects_risks', 'edit') || hasCap(user, 'crm_re_projects_risks', 'create');
  const canProjectView = hasCap(user, 'crm_re_projects', 'view');
  const canProjectEdit = hasCap(user, 'crm_re_projects', 'edit') || hasCap(user, 'crm_re_projects', 'create');
  const canProjectExport =
    hasCap(user, 'crm_re_projects', 'export') ||
    hasCap(user, 'crm_re_projects', 'view') ||
    hasCap(user, 'crm_re_projects', 'edit');

  const pnl = (accounting?.pnl ?? {}) as Record<string, unknown>;
  const cf = (accounting?.cash_flow ?? {}) as Record<string, unknown>;
  const acctRisks = (riskPack?.risks ?? []) as Array<Record<string, unknown>>;

  const tabLabels: Record<DetailTab, string> = {
    summary: 'Tổng quan',
    products: 'Sản phẩm',
    inventory: 'Tồn kho',
    kpi: 'KPI',
    budget: 'Ngân sách',
    risks: 'Rủi ro',
    accounting: 'Kế toán',
    staff: 'Nhân sự',
    'lead-config': 'Lead config',
    workflow: 'Quy trình',
    export: 'Export',
  };

  const visibleTabs: DetailTab[] = ['summary', 'products', 'inventory'];
  if (canKpiView) visibleTabs.push('kpi');
  if (canBudgetView) visibleTabs.push('budget');
  if (canRisksView) visibleTabs.push('risks');
  if (canBudgetView) visibleTabs.push('accounting');
  if (canProjectView) visibleTabs.push('staff', 'lead-config', 'workflow');
  if (canProjectExport) visibleTabs.push('export');

  const workflowSteps = (workflow?.steps ?? []) as Array<Record<string, unknown>>;

  return (
    <main style={{ maxWidth: 960, margin: '0 auto', padding: '1.5rem' }}>
      <OpsNav user={user} onLogout={logout} />
      <p style={{ marginBottom: '1rem' }}>
        <Link href="/crm/re-projects" className="nav-link">
          ← Dự án BĐS
        </Link>
      </p>
      <div className="card">
        <h2 style={{ marginTop: 0, fontSize: '1.15rem' }}>{String(project?.name ?? 'Dự án')}</h2>
        {loading ? <p className="muted">Đang tải…</p> : null}
        {error ? <p className="error">{error}</p> : null}
        <div style={{ display: 'flex', gap: '0.35rem', flexWrap: 'wrap', marginBottom: '1rem' }}>
          {visibleTabs.map((t) => (
            <button
              key={t}
              type="button"
              className={`btn btn-sm${tab === t ? '' : ' btn-secondary'}`}
              onClick={() => setTab(t)}
            >
              {tabLabels[t]}
            </button>
          ))}
        </div>

        {tab === 'summary' && summary ? (
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
            {JSON.stringify(summary, null, 2)}
          </pre>
        ) : null}

        {tab === 'products' ? (
          <ul style={{ margin: 0, paddingLeft: '1.1rem' }}>
            {products.map((p, i) => (
              <li key={String(p.id ?? i)}>
                {String(p.unit_code ?? '—')} · {String(p.zone ?? '—')} · {String(p.status ?? '—')} ·{' '}
                {Number(p.list_price_vnd ?? 0).toLocaleString('vi-VN')} VND
              </li>
            ))}
          </ul>
        ) : null}

        {tab === 'inventory' ? (
          <ul style={{ margin: 0, paddingLeft: '1.1rem' }}>
            {zones.map((z, i) => (
              <li key={String(z.zone ?? i)}>
                {String(z.zone ?? '—')}: available {String(z.available ?? 0)} / total {String(z.total ?? 0)}
              </li>
            ))}
          </ul>
        ) : null}

        {tab === 'kpi' ? (
          <>
            {kpiBoard ? (
              <p className="muted" style={{ marginTop: 0 }}>
                Tổng trọng số {String(kpiBoard.weight_total_pct ?? 0)}% · TB đạt{' '}
                {String(kpiBoard.avg_achievement_pct ?? 0)}%
              </p>
            ) : null}
            <ul style={{ margin: '0 0 1rem', paddingLeft: '1.1rem' }}>
              {kpis.map((k, i) => (
                <li key={String(k.id ?? i)}>
                  {String(k.metric_name ?? '—')} · {String(k.period_month ?? '—')} ·{' '}
                  {Number(k.achievement_pct ?? 0)}% · {String(k.track_status_label ?? k.track_status ?? '—')}
                </li>
              ))}
            </ul>
            {canKpiEdit ? (
              <>
                <div style={{ display: 'flex', gap: '0.35rem', flexWrap: 'wrap', marginBottom: '1rem' }}>
                  <button type="button" className="btn btn-sm btn-secondary" disabled={saving} onClick={() => void onSyncKpisToStaff()}>
                    Sync → nhân sự
                  </button>
                  <button type="button" className="btn btn-sm btn-secondary" disabled={saving} onClick={() => void onPullKpisFromStaff()}>
                    Pull ← nhân sự
                  </button>
                  <button type="button" className="btn btn-sm btn-secondary" disabled={saving} onClick={() => void onRefreshLeadsNewKpi()}>
                    Refresh leads
                  </button>
                </div>
                <form onSubmit={(e) => void onAddKpi(e)} style={{ display: 'flex', gap: '0.5rem', flexWrap: 'wrap' }}>
                  <input
                    value={newKpiName}
                    onChange={(e) => setNewKpiName(e.target.value)}
                    placeholder="Tên chỉ tiêu KPI"
                    disabled={saving}
                    style={{
                      flex: 1,
                      minWidth: 160,
                      background: 'var(--bg)',
                      border: '1px solid var(--border)',
                      borderRadius: 8,
                      padding: '0.55rem 0.75rem',
                      color: 'var(--text)',
                    }}
                  />
                  <button type="submit" className="btn btn-secondary btn-sm" disabled={saving || !newKpiName.trim()}>
                    + KPI
                  </button>
                </form>
              </>
            ) : null}
          </>
        ) : null}

        {tab === 'budget' ? (
          <>
            <ul style={{ margin: '0 0 1rem', paddingLeft: '1.1rem' }}>
              {budgetLines.map((line, i) => (
                <li key={String(line.id ?? i)}>
                  {String(line.category_label ?? line.category ?? '—')} · {String(line.line_item ?? '—')} · KH{' '}
                  {Number(line.planned_vnd ?? 0).toLocaleString('vi-VN')} · TT{' '}
                  {Number(line.actual_vnd ?? 0).toLocaleString('vi-VN')}
                </li>
              ))}
            </ul>
            {canBudgetEdit ? (
              <form onSubmit={(e) => void onAddBudgetLine(e)} style={{ display: 'flex', gap: '0.5rem', flexWrap: 'wrap' }}>
                <input
                  value={newBudgetItem}
                  onChange={(e) => setNewBudgetItem(e.target.value)}
                  placeholder="Hạng mục ngân sách"
                  disabled={saving}
                  style={{
                    flex: 1,
                    minWidth: 160,
                    background: 'var(--bg)',
                    border: '1px solid var(--border)',
                    borderRadius: 8,
                    padding: '0.55rem 0.75rem',
                    color: 'var(--text)',
                  }}
                />
                <button type="submit" className="btn btn-secondary btn-sm" disabled={saving || !newBudgetItem.trim()}>
                  + Dòng NS
                </button>
              </form>
            ) : null}
          </>
        ) : null}

        {tab === 'risks' ? (
          <>
            <ul style={{ margin: '0 0 1rem', paddingLeft: '1.1rem' }}>
              {projectRisks.map((r, i) => (
                <li key={String(r.id ?? i)}>
                  {String(r.title ?? '—')} · {String(r.risk_level_label ?? r.risk_level ?? '—')} · score{' '}
                  {String(r.score ?? '—')}
                </li>
              ))}
            </ul>
            {canRisksEdit ? (
              <form onSubmit={(e) => void onAddRisk(e)} style={{ display: 'flex', gap: '0.5rem', flexWrap: 'wrap' }}>
                <input
                  value={newRiskTitle}
                  onChange={(e) => setNewRiskTitle(e.target.value)}
                  placeholder="Tiêu đề rủi ro"
                  disabled={saving}
                  style={{
                    flex: 1,
                    minWidth: 160,
                    background: 'var(--bg)',
                    border: '1px solid var(--border)',
                    borderRadius: 8,
                    padding: '0.55rem 0.75rem',
                    color: 'var(--text)',
                  }}
                />
                <button type="submit" className="btn btn-secondary btn-sm" disabled={saving || !newRiskTitle.trim()}>
                  + Rủi ro
                </button>
              </form>
            ) : null}
          </>
        ) : null}

        {tab === 'accounting' && accounting ? (
          <>
            <div style={{ display: 'flex', gap: '0.35rem', flexWrap: 'wrap', marginBottom: '1rem' }}>
              {(['dashboard', 'cashflow', 'forecast', 'risks'] as const).map((v) => (
                <button
                  key={v}
                  type="button"
                  className={`btn btn-sm${acctView === v ? '' : ' btn-secondary'}`}
                  onClick={() => setAcctView(v)}
                >
                  {v === 'dashboard' ? 'Dashboard' : v === 'cashflow' ? 'Dòng tiền' : v === 'forecast' ? 'Dự báo' : 'Rủi ro'}
                </button>
              ))}
              {canBudgetEdit ? (
                <>
                  <button type="button" className="btn btn-sm btn-secondary" disabled={saving} onClick={() => void onSyncPlans()}>
                    Sync KH
                  </button>
                  <button
                    type="button"
                    className="btn btn-sm btn-secondary"
                    disabled={saving}
                    onClick={() => void onSyncInventory()}
                  >
                    Sync tồn kho
                  </button>
                </>
              ) : null}
              {canBudgetExport ? (
                <button type="button" className="btn btn-sm btn-secondary" onClick={() => void onExportAccounting()}>
                  Export JSON
                </button>
              ) : null}
            </div>

            {acctView === 'dashboard' ? (
              <div>
                <p className="muted">
                  DT TT {Number(pnl.revenue_actual_vnd ?? 0).toLocaleString('vi-VN')} · LN TT{' '}
                  {Number(pnl.profit_actual_vnd ?? 0).toLocaleString('vi-VN')} · Ròng TT{' '}
                  {Number(cf.net_cash_paid_vnd ?? 0).toLocaleString('vi-VN')} VND
                </p>
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
                  {JSON.stringify(accounting, null, 2)}
                </pre>
              </div>
            ) : null}

            {acctView === 'cashflow' ? (
              <>
                <ul style={{ margin: '0 0 1rem', paddingLeft: '1.1rem' }}>
                  {cashFlow.map((line, i) => (
                    <li key={String(line.id ?? i)}>
                      {String(line.flow_type_label ?? line.flow_type ?? '—')} · {String(line.line_item ?? '—')} ·{' '}
                      {Number(line.amount_vnd ?? 0).toLocaleString('vi-VN')} · {String(line.status_label ?? line.status ?? '—')}
                    </li>
                  ))}
                </ul>
                {canBudgetEdit ? (
                  <form onSubmit={(e) => void onAddCashFlow(e)} style={{ display: 'flex', gap: '0.5rem', flexWrap: 'wrap' }}>
                    <input
                      value={newLineItem}
                      onChange={(e) => setNewLineItem(e.target.value)}
                      placeholder="Mô tả dòng chi"
                      disabled={saving}
                      style={{
                        flex: 1,
                        minWidth: 160,
                        background: 'var(--bg)',
                        border: '1px solid var(--border)',
                        borderRadius: 8,
                        padding: '0.55rem 0.75rem',
                        color: 'var(--text)',
                      }}
                    />
                    <input
                      value={newAmount}
                      onChange={(e) => setNewAmount(e.target.value)}
                      placeholder="VND"
                      disabled={saving}
                      style={{
                        width: 120,
                        background: 'var(--bg)',
                        border: '1px solid var(--border)',
                        borderRadius: 8,
                        padding: '0.55rem 0.75rem',
                        color: 'var(--text)',
                      }}
                    />
                    <button type="submit" className="btn btn-secondary btn-sm" disabled={saving || !newLineItem.trim()}>
                      + Dòng tiền
                    </button>
                  </form>
                ) : null}
              </>
            ) : null}

            {acctView === 'forecast' && forecast ? (
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
                {JSON.stringify(forecast, null, 2)}
              </pre>
            ) : null}

            {acctView === 'risks' ? (
              <ul style={{ margin: 0, paddingLeft: '1.1rem' }}>
                {acctRisks.map((r, i) => (
                  <li key={String(r.code ?? i)}>
                    {String(r.title ?? '—')} · {String(r.risk_level ?? '—')} · {String(r.recommendation ?? '')}
                  </li>
                ))}
              </ul>
            ) : null}
          </>
        ) : null}

        {tab === 'staff' ? (
          <>
            <ul style={{ margin: '0 0 1rem', paddingLeft: '1.1rem' }}>
              {projectStaff.map((s, i) => (
                <li key={String(s.id ?? i)}>
                  {String(s.staff_name ?? '—')} · {String(s.role_label ?? s.role ?? '—')} ·{' '}
                  {s.assign_enabled ? 'Nhận lead' : 'Không nhận lead'}
                </li>
              ))}
            </ul>
            {canProjectEdit ? (
              <form onSubmit={(e) => void onAddStaff(e)} style={{ display: 'flex', gap: '0.5rem', flexWrap: 'wrap' }}>
                <input
                  value={newStaffId}
                  onChange={(e) => setNewStaffId(e.target.value)}
                  placeholder="Staff ID"
                  disabled={saving}
                  style={{
                    width: 120,
                    background: 'var(--bg)',
                    border: '1px solid var(--border)',
                    borderRadius: 8,
                    padding: '0.55rem 0.75rem',
                    color: 'var(--text)',
                  }}
                />
                <button type="submit" className="btn btn-secondary btn-sm" disabled={saving || !newStaffId.trim()}>
                  + Nhân sự
                </button>
              </form>
            ) : null}
          </>
        ) : null}

        {tab === 'lead-config' && leadConfig ? (
          <>
            <p className="muted" style={{ marginTop: 0 }}>
              Webhook: {String(leadConfig.webhook_url ?? '—')}
            </p>
            <p className="muted">
              Slug: {String(leadConfig.webhook_slug ?? '—')} · Page ID: {String(leadConfig.facebook_page_id ?? '—')}
            </p>
            {canProjectEdit ? (
              <div style={{ display: 'flex', gap: '0.5rem', flexWrap: 'wrap', marginTop: '1rem' }}>
                <input
                  value={leadPageId || String(leadConfig.facebook_page_id ?? '')}
                  onChange={(e) => setLeadPageId(e.target.value)}
                  placeholder="Facebook page ID"
                  disabled={saving}
                  style={{
                    flex: 1,
                    minWidth: 160,
                    background: 'var(--bg)',
                    border: '1px solid var(--border)',
                    borderRadius: 8,
                    padding: '0.55rem 0.75rem',
                    color: 'var(--text)',
                  }}
                />
                <button type="button" className="btn btn-secondary btn-sm" disabled={saving} onClick={() => void onSaveLeadConfig()}>
                  Lưu config
                </button>
              </div>
            ) : null}
          </>
        ) : null}

        {tab === 'workflow' && workflow ? (
          <>
            <p className="muted" style={{ marginTop: 0 }}>
              Tiến độ {String(workflow.progress_pct ?? 0)}% · Bước tiếp: {String(workflow.next_step_id ?? '—')}
            </p>
            <ul style={{ margin: 0, paddingLeft: '1.1rem' }}>
              {workflowSteps.map((step, i) => (
                <li key={String(step.id ?? i)}>
                  {String(step.label ?? '—')} · {String(step.status_label ?? step.status ?? '—')}
                </li>
              ))}
            </ul>
          </>
        ) : null}

        {tab === 'export' ? (
          <>
            <div style={{ display: 'flex', gap: '0.5rem', flexWrap: 'wrap', marginBottom: '1rem' }}>
              <select
                value={exportReport}
                onChange={(e) => setExportReport(e.target.value)}
                style={{
                  background: 'var(--bg)',
                  border: '1px solid var(--border)',
                  borderRadius: 8,
                  padding: '0.55rem 0.75rem',
                  color: 'var(--text)',
                }}
              >
                <option value="full">Tổng hợp</option>
                <option value="summary">Tóm tắt</option>
                <option value="workflow">Quy trình</option>
                <option value="kpis">KPI</option>
                <option value="products">Tồn kho</option>
                <option value="risks">Rủi ro</option>
                <option value="budget">Ngân sách</option>
                <option value="plans">Kế hoạch</option>
              </select>
              <button type="button" className="btn btn-sm btn-secondary" onClick={() => void onExportProject()}>
                Export JSON
              </button>
            </div>
            <p className="muted">Xuất bundle JSON từ Nest API (`/export?report=…`).</p>
          </>
        ) : null}
      </div>
    </main>
  );
}
