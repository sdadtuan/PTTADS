'use client';

import Link from 'next/link';
import { useCallback, useEffect, useMemo, useState } from 'react';
import { useParams, useRouter, useSearchParams } from 'next/navigation';
import { OpsNav } from '@/components/OpsNav';
import {
  fetchSeoClientTasks,
  fetchSeoClientWorkspace,
  fetchSeoGa4OAuthUrl,
  fetchSeoGscOAuthUrl,
  staffMe,
  staffRefresh,
  triggerSeoClientSync,
  updateSeoClientSettings,
  type SeoClientTasksResponse,
  type SeoClientWorkspaceResponse,
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
import { canConfigureSeoSettings, canViewSeoClientWorkspace } from '@/lib/seo/caps';
import type { SeoClientTab } from '@/lib/seo/types';

function parseTab(raw: string | null): SeoClientTab {
  if (raw === 'tasks' || raw === 'settings') return raw;
  return 'overview';
}

export default function SeoClientWorkspacePage() {
  const router = useRouter();
  const params = useParams();
  const searchParams = useSearchParams();
  const customerId = Number.parseInt(String(params.id ?? ''), 10);
  const tab = parseTab(searchParams.get('tab'));

  const [user, setUser] = useState<StoredStaffUser | null>(null);
  const [workspace, setWorkspace] = useState<SeoClientWorkspaceResponse | null>(null);
  const [tasks, setTasks] = useState<SeoClientTasksResponse | null>(null);
  const [error, setError] = useState('');
  const [message, setMessage] = useState('');
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [syncing, setSyncing] = useState<'gsc' | 'ga4' | null>(null);

  const [domainsText, setDomainsText] = useState('');
  const [marketsText, setMarketsText] = useState('');
  const [industry, setIndustry] = useState('');
  const [contractTier, setContractTier] = useState('standard');
  const [notes, setNotes] = useState('');
  const [gscSiteUrl, setGscSiteUrl] = useState('');
  const [ga4PropertyId, setGa4PropertyId] = useState('');
  const [connecting, setConnecting] = useState<'gsc' | 'ga4' | null>(null);

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
      if (!canViewSeoClientWorkspace(me)) {
        setError('Không có quyền SEO/AEO workspace');
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

  const loadWorkspace = useCallback(
    async (access: string) => {
      if (!Number.isFinite(customerId)) {
        setError('Client ID không hợp lệ');
        return;
      }
      setLoading(true);
      setError('');
      try {
        const data = await fetchSeoClientWorkspace(access, customerId);
        setWorkspace(data);
        setDomainsText((data.settings.domains ?? []).join('\n'));
        setMarketsText((data.settings.markets ?? []).join(', '));
        setIndustry(data.settings.industry ?? '');
        setContractTier(data.settings.contract_tier ?? 'standard');
        setNotes(data.settings.notes ?? '');
        const gscSite = data.integrations.gsc.site_url ?? data.settings.domains[0] ?? '';
        setGscSiteUrl(gscSite.startsWith('http') ? gscSite : gscSite ? `https://${gscSite}` : '');
        setGa4PropertyId(data.integrations.ga4.property_id ?? '');
        if (tab === 'tasks') {
          const taskData = await fetchSeoClientTasks(access, customerId);
          setTasks(taskData);
        }
      } catch (err) {
        setError(err instanceof Error ? err.message : 'Tải workspace thất bại');
      } finally {
        setLoading(false);
      }
    },
    [customerId, tab],
  );

  useEffect(() => {
    void (async () => {
      const access = await ensureAuth();
      if (!access) return;
      await loadWorkspace(access);
    })();
  }, [ensureAuth, loadWorkspace]);

  useEffect(() => {
    const gscOk = searchParams.get('gsc_connected');
    const ga4Ok = searchParams.get('ga4_connected');
    const gscErr = searchParams.get('gsc_oauth_error');
    const ga4Err = searchParams.get('ga4_oauth_error');
    if (gscOk === '1') setMessage('GSC OAuth kết nối thành công.');
    if (ga4Ok === '1') setMessage('GA4 OAuth kết nối thành công.');
    if (gscErr) setError(`GSC OAuth: ${decodeURIComponent(gscErr)}`);
    if (ga4Err) setError(`GA4 OAuth: ${decodeURIComponent(ga4Err)}`);
  }, [searchParams]);

  const canConfigure = useMemo(() => canConfigureSeoSettings(user), [user]);

  function logout() {
    clearSession();
    router.push('/login');
  }

  function setTab(next: SeoClientTab) {
    router.replace(`/seo/clients/${customerId}?tab=${next}`);
  }

  async function saveSettings() {
    const access = getAccessToken();
    if (!access || !canConfigure) return;
    setSaving(true);
    setMessage('');
    setError('');
    try {
      const domains = domainsText
        .split(/[\n,]/)
        .map((s) => s.trim())
        .filter(Boolean);
      const markets = marketsText
        .split(/[,;\n]/)
        .map((s) => s.trim())
        .filter(Boolean);
      const out = await updateSeoClientSettings(access, customerId, {
        domains,
        markets,
        industry: industry.trim(),
        contract_tier: contractTier,
        notes: notes.trim(),
      });
      setWorkspace((prev) => (prev ? { ...prev, settings: out.settings } : prev));
      setMessage('Đã lưu cấu hình client.');
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Lưu settings thất bại');
    } finally {
      setSaving(false);
    }
  }

  async function runSync(source: 'gsc' | 'ga4') {
    const access = getAccessToken();
    if (!access || !canConfigure) return;
    setSyncing(source);
    setMessage('');
    setError('');
    try {
      const out = await triggerSeoClientSync(access, customerId, source);
      setMessage(
        out.mode === 'queue'
          ? `Đã enqueue sync ${source.toUpperCase()} (job ${out.job_id ?? '—'}).`
          : `Sync ${source.toUpperCase()} — queue tắt (${out.error ?? 'none'}).`,
      );
      await loadWorkspace(access);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Trigger sync thất bại');
    } finally {
      setSyncing(null);
    }
  }

  async function connectOAuth(provider: 'gsc' | 'ga4') {
    const access = getAccessToken();
    if (!access || !canConfigure) return;
    setConnecting(provider);
    setError('');
    try {
      const out =
        provider === 'gsc'
          ? await fetchSeoGscOAuthUrl(access, customerId, gscSiteUrl.trim() || undefined)
          : await fetchSeoGa4OAuthUrl(access, customerId, ga4PropertyId.trim() || undefined);
      window.location.href = out.authorization_url;
    } catch (err) {
      setError(err instanceof Error ? err.message : `Kết nối ${provider.toUpperCase()} thất bại`);
      setConnecting(null);
    }
  }

  if (!user) {
    return (
      <main style={{ padding: '2rem' }}>
        <p className="muted">Đang tải…</p>
      </main>
    );
  }

  const client = workspace?.client;

  return (
    <main style={{ maxWidth: 1100, margin: '0 auto', padding: '1.5rem' }}>
      <OpsNav user={user} onLogout={logout} />

      <div className="card" style={{ marginBottom: '1rem' }}>
        <div style={{ display: 'flex', justifyContent: 'space-between', flexWrap: 'wrap', gap: '0.75rem' }}>
          <div>
            <p className="muted" style={{ marginTop: 0 }}>
              S-03 Client workspace · B1
            </p>
            <h1 style={{ margin: '0.25rem 0' }}>{client?.customer_name ?? `Client #${customerId}`}</h1>
            <p className="muted" style={{ margin: 0 }}>
              ID {customerId} · {client?.customer_company ?? '—'}
            </p>
          </div>
          <div style={{ display: 'flex', gap: '0.5rem', alignItems: 'flex-start' }}>
            <Link href="/seo/clients" className="btn btn-secondary btn-sm">
              ← Clients
            </Link>
            <Link href="/seo/hub" className="btn btn-secondary btn-sm">
              Hub
            </Link>
          </div>
        </div>

        <div style={{ display: 'flex', gap: '0.5rem', marginTop: '1rem', flexWrap: 'wrap' }}>
          {(['overview', 'tasks', 'settings'] as SeoClientTab[]).map((t) => (
            <button
              key={t}
              type="button"
              className={tab === t ? 'btn btn-sm' : 'btn btn-secondary btn-sm'}
              onClick={() => setTab(t)}
            >
              {t === 'overview' ? 'Tổng quan' : t === 'tasks' ? 'Tasks' : 'Settings'}
            </button>
          ))}
        </div>
      </div>

      {error ? <p className="error">{error}</p> : null}
      {message ? <p className="muted">{message}</p> : null}

      {loading ? <p className="muted">Đang tải workspace…</p> : null}

      {!loading && tab === 'overview' && workspace ? (
        <div style={{ display: 'grid', gap: '1rem' }}>
          <div
            className="card"
            style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(140px, 1fr))', gap: '1rem' }}
          >
            <div>
              <p className="muted" style={{ margin: 0 }}>
                Health
              </p>
              <strong>
                {client?.health_score ?? '—'} · {client?.health_tier ?? '—'}
              </strong>
            </div>
            <div>
              <p className="muted" style={{ margin: 0 }}>
                AEO coverage
              </p>
              <strong>{client?.aeo_coverage_pct ?? 0}%</strong>
            </div>
            <div>
              <p className="muted" style={{ margin: 0 }}>
                GSC clicks (28d)
              </p>
              <strong>{String(workspace.gsc_totals?.clicks ?? '—')}</strong>
            </div>
            <div>
              <p className="muted" style={{ margin: 0 }}>
                Critical issues
              </p>
              <strong>{client?.critical_issues ?? 0}</strong>
            </div>
          </div>

          <div className="card">
            <h2 style={{ marginTop: 0, fontSize: '1.05rem' }}>Content delivery</h2>
            <div style={{ display: 'flex', gap: '1.5rem', flexWrap: 'wrap' }}>
              <span>In writing: {workspace.content_delivery.in_writing ?? 0}</span>
              <span>In review: {workspace.content_delivery.in_review ?? 0}</span>
              <span>Overdue: {workspace.content_delivery.overdue ?? 0}</span>
              <span>Published: {workspace.content_delivery.published ?? 0}</span>
            </div>
          </div>

          <div className="card">
            <h2 style={{ marginTop: 0, fontSize: '1.05rem' }}>Integrations</h2>
            <p style={{ margin: '0.25rem 0' }}>
              GSC: {workspace.integrations.gsc.connected ? 'Connected' : 'Disconnected'}{' '}
              {workspace.integrations.gsc.site_url ? `· ${workspace.integrations.gsc.site_url}` : ''}
            </p>
            <p style={{ margin: '0.25rem 0' }}>
              GA4: {workspace.integrations.ga4.connected ? 'Connected' : 'Disconnected'}{' '}
              {workspace.integrations.ga4.property_id ? `· ${workspace.integrations.ga4.property_id}` : ''}
            </p>
          </div>

          {workspace.sync_runs.length ? (
            <div className="card">
              <h2 style={{ marginTop: 0, fontSize: '1.05rem' }}>Recent sync runs</h2>
              <table className="perf-table">
                <thead>
                  <tr>
                    <th>Source</th>
                    <th>Status</th>
                    <th>Rows</th>
                    <th>Started</th>
                  </tr>
                </thead>
                <tbody>
                  {workspace.sync_runs.map((run) => (
                    <tr key={run.id}>
                      <td>{run.source}</td>
                      <td>{run.status}</td>
                      <td>{run.rows_imported}</td>
                      <td>{run.started_at ? new Date(run.started_at).toLocaleString() : '—'}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          ) : null}
        </div>
      ) : null}

      {!loading && tab === 'tasks' ? (
        <div className="card">
          <h2 style={{ marginTop: 0, fontSize: '1.05rem' }}>
            Open tasks ({tasks?.open_count ?? 0})
          </h2>
          {!tasks?.service_tasks.length && !tasks?.technical_issues.length ? (
            <p className="muted">Không có task/issue mở.</p>
          ) : (
            <ul style={{ margin: 0, paddingLeft: '1.2rem' }}>
              {(tasks?.service_tasks ?? []).map((t) => (
                <li key={`svc-${t.task_id}`} style={{ marginBottom: '0.5rem' }}>
                  <Link href={t.url} className="nav-link">
                    [{t.stage}] {t.title}
                  </Link>
                  <span className="muted"> · {t.service_slug}</span>
                </li>
              ))}
              {(tasks?.technical_issues ?? []).map((t) => (
                <li key={`tech-${t.issue_id}`} style={{ marginBottom: '0.5rem' }}>
                  <Link href={t.url} className="nav-link">
                    {t.title}
                  </Link>
                  <span className="muted">
                    {' '}
                    · {t.severity} · {t.status}
                  </span>
                </li>
              ))}
            </ul>
          )}
        </div>
      ) : null}

      {!loading && tab === 'settings' && workspace ? (
        <div className="card">
          <h2 style={{ marginTop: 0, fontSize: '1.05rem' }}>Client settings (S-04)</h2>
          {!canConfigure ? (
            <p className="muted">Bạn chỉ có quyền xem — cần cap crm_seo_aeo_settings.</p>
          ) : null}
          <label className="muted" style={{ display: 'block', marginBottom: '0.75rem' }}>
            Domains (mỗi dòng hoặc dấu phẩy)
            <textarea
              value={domainsText}
              onChange={(e) => setDomainsText(e.target.value)}
              rows={3}
              style={{ display: 'block', width: '100%', marginTop: '0.35rem' }}
              disabled={!canConfigure}
            />
          </label>
          <label className="muted" style={{ display: 'block', marginBottom: '0.75rem' }}>
            Markets
            <input
              value={marketsText}
              onChange={(e) => setMarketsText(e.target.value)}
              style={{ display: 'block', width: '100%', marginTop: '0.35rem' }}
              disabled={!canConfigure}
            />
          </label>
          <label className="muted" style={{ display: 'block', marginBottom: '0.75rem' }}>
            Industry
            <input
              value={industry}
              onChange={(e) => setIndustry(e.target.value)}
              style={{ display: 'block', width: '100%', marginTop: '0.35rem' }}
              disabled={!canConfigure}
            />
          </label>
          <label className="muted" style={{ display: 'block', marginBottom: '0.75rem' }}>
            Contract tier
            <select
              value={contractTier}
              onChange={(e) => setContractTier(e.target.value)}
              style={{ display: 'block', marginTop: '0.35rem' }}
              disabled={!canConfigure}
            >
              <option value="standard">standard</option>
              <option value="premium">premium</option>
              <option value="enterprise">enterprise</option>
            </select>
          </label>
          <label className="muted" style={{ display: 'block', marginBottom: '0.75rem' }}>
            Notes
            <textarea
              value={notes}
              onChange={(e) => setNotes(e.target.value)}
              rows={2}
              style={{ display: 'block', width: '100%', marginTop: '0.35rem' }}
              disabled={!canConfigure}
            />
          </label>
          <label className="muted" style={{ display: 'block', marginBottom: '0.75rem' }}>
            GSC site URL (Search Console property)
            <input
              value={gscSiteUrl}
              onChange={(e) => setGscSiteUrl(e.target.value)}
              placeholder="https://example.com/ hoặc sc-domain:example.com"
              style={{ display: 'block', width: '100%', marginTop: '0.35rem' }}
              disabled={!canConfigure}
            />
          </label>
          <label className="muted" style={{ display: 'block', marginBottom: '0.75rem' }}>
            GA4 property ID
            <input
              value={ga4PropertyId}
              onChange={(e) => setGa4PropertyId(e.target.value)}
              placeholder="123456789"
              style={{ display: 'block', width: '100%', marginTop: '0.35rem' }}
              disabled={!canConfigure}
            />
          </label>
          <div style={{ display: 'flex', gap: '0.5rem', flexWrap: 'wrap', marginBottom: '1rem' }}>
            <button
              type="button"
              className="btn btn-sm"
              disabled={!canConfigure || connecting !== null}
              onClick={() => void connectOAuth('gsc')}
            >
              {connecting === 'gsc' ? 'Redirect GSC…' : 'Kết nối GSC (Google)'}
            </button>
            <button
              type="button"
              className="btn btn-sm"
              disabled={!canConfigure || connecting !== null}
              onClick={() => void connectOAuth('ga4')}
            >
              {connecting === 'ga4' ? 'Redirect GA4…' : 'Kết nối GA4 (Google)'}
            </button>
          </div>
          <div style={{ display: 'flex', gap: '0.5rem', flexWrap: 'wrap' }}>
            <button type="button" className="btn btn-sm" disabled={!canConfigure || saving} onClick={() => void saveSettings()}>
              {saving ? 'Đang lưu…' : 'Lưu settings'}
            </button>
            <button
              type="button"
              className="btn btn-secondary btn-sm"
              disabled={!canConfigure || syncing !== null}
              onClick={() => void runSync('gsc')}
            >
              {syncing === 'gsc' ? 'Sync GSC…' : 'Sync GSC'}
            </button>
            <button
              type="button"
              className="btn btn-secondary btn-sm"
              disabled={!canConfigure || syncing !== null}
              onClick={() => void runSync('ga4')}
            >
              {syncing === 'ga4' ? 'Sync GA4…' : 'Sync GA4'}
            </button>
          </div>
        </div>
      ) : null}
    </main>
  );
}
