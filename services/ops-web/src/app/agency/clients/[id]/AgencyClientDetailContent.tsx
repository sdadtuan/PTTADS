'use client';

import Link from 'next/link';
import { useCallback, useEffect, useState } from 'react';
import { useParams, useRouter, useSearchParams } from 'next/navigation';
import { OpsNav } from '@/components/OpsNav';
import { AgencyReadOnlyBadge, canAgencyWrite } from '@/components/AgencyReadOnlyBadge';
import {
  activateAgencyClient,
  addClientChannelAccount,
  deleteClientChannelAccount,
  fetchAgencyClient,
  fetchClientLeads,
  fetchClientOnboarding,
  fetchClientPerformance,
  fetchOnboardingWorkflowStatus,
  patchAgencyClient,
  patchClientChannelAccount,
  patchClientOnboardingItem,
  setClientChannelToken,
  staffMe,
  staffRefresh,
  syncClientInsights,
} from '@/lib/api';
import { jobTypeLabel } from '@/lib/job-labels';
import type {
  AgencyClient,
  ClientLeadSummary,
  OnboardingItem,
  OnboardingResponse,
  PerformanceRow,
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

type TabId = 'overview' | 'checklist' | 'channels' | 'leads';

const CLIENT_STATUSES = ['prospect', 'onboarding', 'active', 'paused'] as const;

interface ClientEditForm {
  name: string;
  industry_slug: string;
  owner_am_id: string;
  notes: string;
  status: string;
}

function fmtVnd(n: number | null | undefined): string {
  if (n == null) return '—';
  return Math.round(n).toLocaleString('vi-VN') + ' ₫';
}

function statusBadgeClass(status: string): string {
  if (status === 'active') return 'badge-active';
  if (status === 'onboarding') return 'badge-onboarding';
  if (status === 'paused') return 'badge-paused';
  return 'badge-prospect';
}

export function AgencyClientDetailContent() {
  const router = useRouter();
  const params = useParams();
  const searchParams = useSearchParams();
  const clientId = String(params.id ?? '');
  const tab = (searchParams.get('tab') as TabId) || 'overview';

  const [user, setUser] = useState<StoredStaffUser | null>(null);
  const [client, setClient] = useState<AgencyClient | null>(null);
  const [onboarding, setOnboarding] = useState<OnboardingResponse | null>(null);
  const [perfRows, setPerfRows] = useState<PerformanceRow[]>([]);
  const [error, setError] = useState('');
  const [actionMsg, setActionMsg] = useState('');
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState(false);
  const [channelForm, setChannelForm] = useState({
    channel: 'meta',
    external_account_id: '',
    display_name: '',
  });
  const [editForm, setEditForm] = useState<ClientEditForm>({
    name: '',
    industry_slug: '',
    owner_am_id: '',
    notes: '',
    status: 'prospect',
  });
  const [workflowStatus, setWorkflowStatus] = useState<string>('');
  const [clientLeads, setClientLeads] = useState<ClientLeadSummary[]>([]);
  const [tokenAccountId, setTokenAccountId] = useState('');
  const [tokenValue, setTokenValue] = useState('');
  const [editChannelId, setEditChannelId] = useState<string | null>(null);
  const [editChannelForm, setEditChannelForm] = useState({
    external_account_id: '',
    display_name: '',
    status: 'active',
  });

  const canWrite = canAgencyWrite(user);

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
      if (!hasCap(me, 'crm_agency', 'view')) {
        setError('Không có quyền Agency');
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

  const reload = useCallback(
    async (access: string) => {
      const [detail, perf, ob, wf, leadsOut] = await Promise.all([
        fetchAgencyClient(access, clientId),
        fetchClientPerformance(access, clientId, { group_by: 'campaign' }),
        fetchClientOnboarding(access, clientId),
        fetchOnboardingWorkflowStatus(access, clientId).catch(() => ({ ok: false, status: '' })),
        fetchClientLeads(access, clientId).catch(() => ({ leads: [] })),
      ]);
      setClient(detail);
      setPerfRows(perf.rows ?? []);
      setOnboarding(ob);
      setWorkflowStatus(wf.status ?? (wf.ok ? 'unknown' : 'off'));
      setClientLeads(leadsOut.leads ?? []);
      setEditForm({
        name: detail.name ?? '',
        industry_slug: detail.industry_slug ?? '',
        owner_am_id: detail.owner_am_id ?? '',
        notes: detail.notes ?? '',
        status: detail.status ?? 'prospect',
      });
    },
    [clientId],
  );

  useEffect(() => {
    if (!clientId) return;
    void (async () => {
      const access = await ensureAuth();
      if (!access) return;
      setLoading(true);
      setError('');
      try {
        await reload(access);
      } catch (err) {
        setError(err instanceof Error ? err.message : 'Tải client thất bại');
      } finally {
        setLoading(false);
      }
    })();
  }, [ensureAuth, clientId, reload]);

  function setTab(next: TabId) {
    const qs = new URLSearchParams(searchParams.toString());
    if (next === 'overview') qs.delete('tab');
    else qs.set('tab', next);
    const suffix = qs.toString() ? `?${qs.toString()}` : '';
    router.replace(`/agency/clients/${clientId}${suffix}`);
  }

  async function toggleChecklist(item: OnboardingItem) {
    const access = getAccessToken();
    if (!access || !canWrite) return;
    setBusy(true);
    setActionMsg('');
    try {
      const out = await patchClientOnboardingItem(access, clientId, item.item_key, {
        completed: !item.completed,
        completed_by: user?.email ?? user?.display_name ?? 'staff',
      });
      setOnboarding(out);
      setActionMsg('Đã cập nhật checklist');
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Cập nhật checklist thất bại');
    } finally {
      setBusy(false);
    }
  }

  async function handleActivate(force = false) {
    const access = getAccessToken();
    if (!access || !canWrite) return;
    setBusy(true);
    setActionMsg('');
    setError('');
    try {
      const updated = await activateAgencyClient(access, clientId, force);
      setClient(updated);
      const fx = updated.side_effects;
      if (fx?.jobs_enqueued?.length) {
        setActionMsg(
          `Client đã kích hoạt · ${fx.jobs_enqueued.length} job (${fx.jobs_enqueued.map((j) => jobTypeLabel(j.job_type)).join(', ')})`,
        );
      } else {
        setActionMsg('Client đã kích hoạt');
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Kích hoạt thất bại');
    } finally {
      setBusy(false);
    }
  }

  async function handleAddChannel(e: React.FormEvent) {
    e.preventDefault();
    const access = getAccessToken();
    if (!access || !canWrite) return;
    setBusy(true);
    setActionMsg('');
    setError('');
    try {
      const updated = await addClientChannelAccount(access, clientId, channelForm);
      setClient(updated);
      setChannelForm({ channel: 'meta', external_account_id: '', display_name: '' });
      setActionMsg('Đã thêm channel account');
      const metaAcc = (updated.channel_accounts ?? []).find((a) => a.channel === 'meta');
      if (metaAcc) setTokenAccountId(metaAcc.id);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Thêm channel thất bại');
    } finally {
      setBusy(false);
    }
  }

  function startEditChannel(acc: NonNullable<AgencyClient['channel_accounts']>[number]) {
    setEditChannelId(acc.id);
    setEditChannelForm({
      external_account_id: acc.external_account_id ?? '',
      display_name: acc.display_name ?? '',
      status: acc.status ?? 'active',
    });
    setActionMsg('');
    setError('');
  }

  async function handleUpdateChannel(e: React.FormEvent) {
    e.preventDefault();
    const access = getAccessToken();
    if (!access || !canWrite || !editChannelId) return;
    setBusy(true);
    setActionMsg('');
    setError('');
    try {
      const updated = await patchClientChannelAccount(access, clientId, editChannelId, editChannelForm);
      setClient(updated);
      setEditChannelId(null);
      setActionMsg('Đã cập nhật channel account');
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Cập nhật channel thất bại');
    } finally {
      setBusy(false);
    }
  }

  async function handleDeleteChannel(accountId: string, label: string) {
    const access = getAccessToken();
    if (!access || !canWrite) return;
    if (!window.confirm(`Xóa channel account ${label}? Token vault cũng bị xóa.`)) return;
    setBusy(true);
    setActionMsg('');
    setError('');
    try {
      await deleteClientChannelAccount(access, clientId, accountId);
      const updated = await fetchAgencyClient(access, clientId);
      setClient(updated);
      if (tokenAccountId === accountId) setTokenAccountId('');
      if (editChannelId === accountId) setEditChannelId(null);
      setActionMsg('Đã xóa channel account');
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Xóa channel thất bại');
    } finally {
      setBusy(false);
    }
  }

  async function handleRevokeToken(accountId: string) {
    const access = getAccessToken();
    if (!access || !canWrite) return;
    if (!window.confirm('Thu hồi token Meta trên account này?')) return;
    setBusy(true);
    setActionMsg('');
    setError('');
    try {
      const updated = await setClientChannelToken(access, clientId, accountId, { revoke: true });
      setClient(updated);
      setActionMsg('Đã thu hồi token');
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Thu hồi token thất bại');
    } finally {
      setBusy(false);
    }
  }

  async function handleSaveClient(e: React.FormEvent) {
    e.preventDefault();
    const access = getAccessToken();
    if (!access || !canWrite) return;
    setBusy(true);
    setActionMsg('');
    setError('');
    try {
      const updated = await patchAgencyClient(access, clientId, {
        name: editForm.name.trim(),
        industry_slug: editForm.industry_slug.trim() || undefined,
        owner_am_id: editForm.owner_am_id.trim() || undefined,
        notes: editForm.notes.trim() || undefined,
        status: editForm.status,
      });
      setClient(updated);
      setEditForm({
        name: updated.name ?? '',
        industry_slug: updated.industry_slug ?? '',
        owner_am_id: updated.owner_am_id ?? '',
        notes: updated.notes ?? '',
        status: updated.status ?? 'prospect',
      });
      setActionMsg('Đã lưu thông tin client');
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Lưu client thất bại');
    } finally {
      setBusy(false);
    }
  }

  async function handleConnectToken(e: React.FormEvent) {
    e.preventDefault();
    const access = getAccessToken();
    if (!access || !canWrite || !tokenAccountId) return;
    setBusy(true);
    setError('');
    setActionMsg('');
    try {
      const updated = await setClientChannelToken(access, clientId, tokenAccountId, {
        access_token: tokenValue,
      });
      setClient(updated);
      setTokenValue('');
      const n = updated.side_effects?.jobs_enqueued?.length ?? 0;
      setActionMsg(n ? `Token đã lưu · ${n} sync job queued` : 'Token đã lưu');
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Lưu token thất bại');
    } finally {
      setBusy(false);
    }
  }

  async function handleSyncInsights() {
    const access = getAccessToken();
    if (!access || !canWrite) return;
    setBusy(true);
    setActionMsg('');
    setError('');
    try {
      const out = await syncClientInsights(access, clientId);
      setActionMsg(`Đã enqueue job: ${jobTypeLabel('meta_insights_sync')}`);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Sync insights thất bại');
    } finally {
      setBusy(false);
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

  const progress = onboarding?.progress ?? { total: 0, completed: 0, percent: 0 };
  const activateDisabled =
    !canWrite || client?.status === 'active' || (progress.percent < 100 && client?.status === 'onboarding');

  return (
    <main style={{ maxWidth: 1100, margin: '0 auto', padding: '1.5rem' }}>
      <OpsNav user={user} onLogout={logout} />
      <p style={{ margin: '0 0 1rem' }}>
        <Link href="/agency" className="nav-link">
          ← Agency
        </Link>
      </p>

      <div className="card">
        {loading ? <p className="muted">Đang tải…</p> : null}
        {error ? <p className="error">{error}</p> : null}
        {actionMsg ? <p className="muted">{actionMsg}</p> : null}

        {client && !loading ? (
          <>
            <div style={{ display: 'flex', flexWrap: 'wrap', gap: '1rem', alignItems: 'center', marginBottom: '1rem' }}>
              <h2 style={{ margin: 0, flex: '1 1 auto' }}>
                {client.code} · {client.name}
              </h2>
              <AgencyReadOnlyBadge user={user} />
              <span className={`agency-status-badge ${statusBadgeClass(client.status)}`}>{client.status}</span>
            </div>
            <p className="muted">AM: {client.owner_am_id || '—'} · Ngành: {client.industry_slug || '—'}</p>

            <div className="agency-tabs" role="tablist">
              {(
                [
                  ['overview', 'Tổng quan'],
                  ['checklist', `Checklist ${progress.completed}/${progress.total}`],
                  ['channels', 'Kênh ads'],
                  ['leads', `Leads (${clientLeads.length})`],
                ] as const
              ).map(([id, label]) => (
                <button
                  key={id}
                  type="button"
                  role="tab"
                  className={`agency-tab${tab === id ? ' is-active' : ''}`}
                  onClick={() => setTab(id)}
                >
                  {label}
                </button>
              ))}
            </div>

            {tab === 'overview' ? (
              <>
                <h3 style={{ fontSize: '1rem', marginTop: '0.5rem' }}>Thông tin client</h3>
                {canWrite ? (
                  <form className="agency-client-edit" onSubmit={(e) => void handleSaveClient(e)}>
                    <label>
                      Tên
                      <input
                        value={editForm.name}
                        onChange={(e) => setEditForm((f) => ({ ...f, name: e.target.value }))}
                        required
                      />
                    </label>
                    <label>
                      Ngành (slug)
                      <input
                        value={editForm.industry_slug}
                        onChange={(e) => setEditForm((f) => ({ ...f, industry_slug: e.target.value }))}
                        placeholder="vd. fmcg, bds"
                      />
                    </label>
                    <label>
                      Owner AM (staff id / email)
                      <input
                        value={editForm.owner_am_id}
                        onChange={(e) => setEditForm((f) => ({ ...f, owner_am_id: e.target.value }))}
                      />
                    </label>
                    <label>
                      Trạng thái
                      <select
                        value={editForm.status}
                        onChange={(e) => setEditForm((f) => ({ ...f, status: e.target.value }))}
                      >
                        {CLIENT_STATUSES.map((s) => (
                          <option key={s} value={s}>
                            {s}
                          </option>
                        ))}
                      </select>
                    </label>
                    <label>
                      Ghi chú
                      <textarea
                        value={editForm.notes}
                        onChange={(e) => setEditForm((f) => ({ ...f, notes: e.target.value }))}
                      />
                    </label>
                    <div>
                      <button type="submit" className="btn btn-sm" disabled={busy}>
                        Lưu thông tin
                      </button>
                    </div>
                  </form>
                ) : (
                  <dl className="agency-client-edit" style={{ gridTemplateColumns: 'auto 1fr', display: 'grid', gap: '0.5rem 1rem' }}>
                    <dt className="muted">Tên</dt>
                    <dd style={{ margin: 0 }}>{client.name}</dd>
                    <dt className="muted">Ngành</dt>
                    <dd style={{ margin: 0 }}>{client.industry_slug || '—'}</dd>
                    <dt className="muted">AM</dt>
                    <dd style={{ margin: 0 }}>{client.owner_am_id || '—'}</dd>
                    <dt className="muted">Ghi chú</dt>
                    <dd style={{ margin: 0 }}>{client.notes || '—'}</dd>
                  </dl>
                )}

                <h3 style={{ fontSize: '1rem', marginTop: '1.5rem' }}>Performance (Meta, 7 ngày)</h3>
                {canWrite ? (
                  <button
                    type="button"
                    className="btn btn-secondary btn-sm"
                    style={{ marginBottom: '0.75rem' }}
                    disabled={busy}
                    onClick={() => void handleSyncInsights()}
                  >
                    Sync insights now
                  </button>
                ) : null}
                <div style={{ overflowX: 'auto' }}>
                  <table className="perf-table">
                    <thead>
                      <tr>
                        <th>Campaign</th>
                        <th>Spend</th>
                        <th>Leads</th>
                        <th>CPL</th>
                        <th>Target</th>
                        <th>Δ</th>
                      </tr>
                    </thead>
                    <tbody>
                      {perfRows.map((row, i) => (
                        <tr key={`${row.external_campaign_id ?? i}`}>
                          <td>{row.external_campaign_name || row.external_campaign_id || '—'}</td>
                          <td>{fmtVnd(row.spend)}</td>
                          <td>{row.leads_crm}</td>
                          <td>{fmtVnd(row.cpl)}</td>
                          <td>{fmtVnd(row.target_cpl_vnd)}</td>
                          <td>
                            {row.cpl_delta_pct != null
                              ? `${row.cpl_delta_pct > 0 ? '+' : ''}${row.cpl_delta_pct}%`
                              : '—'}
                          </td>
                        </tr>
                      ))}
                      {perfRows.length === 0 ? (
                        <tr>
                          <td colSpan={6} className="muted">
                            Chưa có daily_performance — chạy sync_meta_insights
                          </td>
                        </tr>
                      ) : null}
                    </tbody>
                  </table>
                </div>
              </>
            ) : null}

            {tab === 'checklist' ? (
              <div style={{ marginTop: '1rem' }}>
                <div className="onboarding-progress" aria-label="Tiến độ checklist">
                  <div className="onboarding-progress-bar" style={{ width: `${progress.percent}%` }} />
                </div>
                <p className="muted">{progress.percent}% · {progress.completed}/{progress.total} mục</p>
                {workflowStatus ? (
                  <p className="muted">Temporal workflow: {workflowStatus}</p>
                ) : null}
                <ul className="onboarding-list">
                  {(onboarding?.items ?? []).map((item) => (
                    <li key={item.id} className="onboarding-item">
                      <label>
                        <input
                          type="checkbox"
                          checked={item.completed}
                          disabled={!canWrite || busy}
                          onChange={() => void toggleChecklist(item)}
                        />
                        <span>{item.label}</span>
                      </label>
                      {item.note ? <span className="muted"> · {item.note}</span> : null}
                    </li>
                  ))}
                </ul>
                <div style={{ marginTop: '1rem', display: 'flex', gap: '0.75rem', flexWrap: 'wrap', alignItems: 'center' }}>
                  {client.status === 'active' ? (
                    <p className="muted" style={{ margin: 0 }}>
                      Client đã <strong>active</strong> — không cần kích hoạt lại.{' '}
                      <Link href="/agency/jobs" className="nav-link">
                        Xem jobs
                      </Link>
                    </p>
                  ) : (
                    <>
                      <button
                        type="button"
                        className="btn btn-sm"
                        disabled={activateDisabled || busy}
                        onClick={() => void handleActivate(false)}
                      >
                        Kích hoạt client
                      </button>
                      {canWrite && progress.percent < 100 ? (
                        <button
                          type="button"
                          className="btn btn-secondary btn-sm"
                          disabled={busy}
                          onClick={() => {
                            if (window.confirm('Bỏ qua checklist và kích hoạt (force)?')) {
                              void handleActivate(true);
                            }
                          }}
                        >
                          Force activate
                        </button>
                      ) : null}
                    </>
                  )}
                </div>
                {activateDisabled && client.status !== 'active' && !canWrite ? (
                  <p className="muted">Chế độ chỉ xem — không thể sửa checklist hoặc kích hoạt.</p>
                ) : null}
                {activateDisabled && client.status !== 'active' && canWrite ? (
                  <p className="muted">Hoàn thành checklist trước khi kích hoạt (PTT_CLIENT_STRICT_ONBOARDING).</p>
                ) : null}
              </div>
            ) : null}

            {tab === 'channels' ? (
              <div style={{ marginTop: '1rem' }}>
                {canWrite ? (
                  <form onSubmit={(e) => void handleAddChannel(e)} style={{ display: 'grid', gap: '0.75rem', maxWidth: 480, marginBottom: '1.25rem' }}>
                    <h3 style={{ fontSize: '1rem', margin: 0 }}>Thêm channel account</h3>
                    <select
                      value={channelForm.channel}
                      onChange={(e) => setChannelForm((f) => ({ ...f, channel: e.target.value }))}
                      style={{ padding: '0.5rem' }}
                    >
                      <option value="meta">Meta</option>
                      <option value="google">Google</option>
                      <option value="zalo">Zalo</option>
                      <option value="email">Email</option>
                    </select>
                    <input
                      placeholder="External account ID (act_… hoặc số Meta)"
                      value={channelForm.external_account_id}
                      onChange={(e) => setChannelForm((f) => ({ ...f, external_account_id: e.target.value }))}
                      required
                      style={{ padding: '0.5rem' }}
                    />
                    <input
                      placeholder="Tên hiển thị (tuỳ chọn)"
                      value={channelForm.display_name}
                      onChange={(e) => setChannelForm((f) => ({ ...f, display_name: e.target.value }))}
                      style={{ padding: '0.5rem' }}
                    />
                    <button type="submit" className="btn btn-sm" disabled={busy}>
                      Thêm channel
                    </button>
                  </form>
                ) : null}

                {editChannelId && canWrite ? (
                  <form
                    onSubmit={(e) => void handleUpdateChannel(e)}
                    style={{ display: 'grid', gap: '0.75rem', maxWidth: 480, marginBottom: '1.25rem' }}
                  >
                    <h3 style={{ fontSize: '1rem', margin: 0 }}>Sửa channel account</h3>
                    <input
                      placeholder="External account ID"
                      value={editChannelForm.external_account_id}
                      onChange={(e) => setEditChannelForm((f) => ({ ...f, external_account_id: e.target.value }))}
                      required
                      style={{ padding: '0.5rem' }}
                    />
                    <input
                      placeholder="Tên hiển thị"
                      value={editChannelForm.display_name}
                      onChange={(e) => setEditChannelForm((f) => ({ ...f, display_name: e.target.value }))}
                      style={{ padding: '0.5rem' }}
                    />
                    <select
                      value={editChannelForm.status}
                      onChange={(e) => setEditChannelForm((f) => ({ ...f, status: e.target.value }))}
                      style={{ padding: '0.5rem' }}
                    >
                      <option value="active">active</option>
                      <option value="inactive">inactive</option>
                      <option value="revoked">revoked</option>
                      <option value="error">error</option>
                    </select>
                    <div style={{ display: 'flex', gap: '0.5rem' }}>
                      <button type="submit" className="btn btn-sm" disabled={busy}>
                        Lưu thay đổi
                      </button>
                      <button type="button" className="btn btn-secondary btn-sm" onClick={() => setEditChannelId(null)}>
                        Hủy
                      </button>
                    </div>
                  </form>
                ) : null}

                <table className="perf-table">
                  <thead>
                    <tr>
                      <th>Channel</th>
                      <th>External ID</th>
                      <th>Tên hiển thị</th>
                      <th>Token</th>
                      <th>Status</th>
                      {canWrite ? <th /> : null}
                    </tr>
                  </thead>
                  <tbody>
                    {(client.channel_accounts ?? []).map((acc) => (
                      <tr key={acc.id}>
                        <td>{acc.channel}</td>
                        <td>{acc.external_account_id ?? '—'}</td>
                        <td>{acc.display_name ?? '—'}</td>
                        <td>{acc.token_status ?? (acc.has_token ? 'ok' : '—')}</td>
                        <td>{acc.status ?? '—'}</td>
                        {canWrite ? (
                          <td style={{ whiteSpace: 'nowrap' }}>
                            <button type="button" className="btn btn-secondary btn-sm" disabled={busy} onClick={() => startEditChannel(acc)}>
                              Sửa
                            </button>{' '}
                            {acc.channel === 'meta' && (acc.has_token || acc.token_status === 'valid') ? (
                              <button type="button" className="btn btn-secondary btn-sm" disabled={busy} onClick={() => void handleRevokeToken(acc.id)}>
                                Thu hồi token
                              </button>
                            ) : null}{' '}
                            <button
                              type="button"
                              className="btn btn-secondary btn-sm"
                              disabled={busy}
                              onClick={() => void handleDeleteChannel(acc.id, acc.external_account_id ?? acc.id.slice(0, 8))}
                            >
                              Xóa
                            </button>
                          </td>
                        ) : null}
                      </tr>
                    ))}
                    {(client.channel_accounts ?? []).length === 0 ? (
                      <tr>
                        <td colSpan={canWrite ? 6 : 5} className="muted">
                          Chưa có channel account — thêm Meta act_… ở form trên
                        </td>
                      </tr>
                    ) : null}
                  </tbody>
                </table>

                {canWrite && (client.channel_accounts ?? []).some((a) => a.channel === 'meta') ? (
                  <form onSubmit={(e) => void handleConnectToken(e)} style={{ marginTop: '1.25rem', display: 'grid', gap: '0.75rem', maxWidth: 480 }}>
                    <h3 style={{ fontSize: '1rem', margin: 0 }}>Connect Meta token (vault)</h3>
                    <p className="muted" style={{ margin: 0, fontSize: '0.85rem' }}>
                      Chọn account Meta rồi dán access token.
                    </p>
                    <select
                      value={tokenAccountId}
                      onChange={(e) => setTokenAccountId(e.target.value)}
                      required
                      style={{ padding: '0.5rem' }}
                    >
                      <option value="">Chọn Meta account…</option>
                      {(client.channel_accounts ?? [])
                        .filter((a) => a.channel === 'meta')
                        .map((a) => (
                          <option key={a.id} value={a.id}>
                            {a.external_account_id} · {a.display_name || a.id.slice(0, 8)}
                          </option>
                        ))}
                    </select>
                    <input
                      type="password"
                      placeholder="Meta access token"
                      value={tokenValue}
                      onChange={(e) => setTokenValue(e.target.value)}
                      required
                      style={{ padding: '0.5rem' }}
                    />
                    <button type="submit" className="btn btn-sm" disabled={busy || !tokenAccountId}>
                      Lưu token + enqueue sync
                    </button>
                  </form>
                ) : canWrite ? (
                  <p className="muted" style={{ marginTop: '1rem' }}>
                    Thêm Meta channel account trước khi lưu token.
                  </p>
                ) : null}
              </div>
            ) : null}

            {tab === 'leads' ? (
              <div style={{ marginTop: '1rem', overflowX: 'auto' }}>
                <table className="perf-table">
                  <thead>
                    <tr>
                      <th>Tên</th>
                      <th>Phone</th>
                      <th>Trạng thái</th>
                      <th>Kênh</th>
                      <th>Ngày</th>
                      <th />
                    </tr>
                  </thead>
                  <tbody>
                    {clientLeads.map((lead) => (
                      <tr key={lead.id}>
                        <td>{lead.full_name || '—'}</td>
                        <td>{lead.phone || '—'}</td>
                        <td>{lead.status || '—'}</td>
                        <td>{lead.channel || '—'}</td>
                        <td>{lead.created_at?.slice(0, 10) ?? '—'}</td>
                        <td>
                          <Link href={`/crm/leads/${lead.id}`} className="nav-link">
                            Mở CRM
                          </Link>
                        </td>
                      </tr>
                    ))}
                    {clientLeads.length === 0 ? (
                      <tr>
                        <td colSpan={6} className="muted">
                          Chưa có lead gắn client này (agency_client_id)
                        </td>
                      </tr>
                    ) : null}
                  </tbody>
                </table>
              </div>
            ) : null}
          </>
        ) : null}
      </div>
    </main>
  );
}
