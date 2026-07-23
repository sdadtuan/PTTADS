'use client';

import Link from 'next/link';
import { useCallback, useEffect, useState } from 'react';
import { useParams, useRouter, useSearchParams } from 'next/navigation';
import { ClientOnboardingWidget } from '@/components/ClientOnboardingWidget';
import { OpsNav } from '@/components/OpsNav';
import { AgencyReadOnlyBadge, canAgencyConfigure, canAgencyWrite } from '@/components/AgencyReadOnlyBadge';
import { HubCampaignMapsPanel } from '@/components/HubCampaignMapsPanel';
import {
  activateAgencyClient,
  addClientChannelAccount,
  deleteClientChannelAccount,
  fetchAgencyClientContracts,
  fetchAgencyClient,
  fetchClientOffboardAudit,
  fetchClientLeads,
  fetchClientOnboardingSummary,
  fetchClientPerformance,
  offboardAgencyClient,
  patchAgencyClient,
  patchClientChannelAccount,
  patchClientOnboardingItem,
  postClientOnboardingNudge,
  postClientOnboardingStartWorkflow,
  setClientChannelToken,
  staffMe,
  staffRefresh,
  syncClientInsights,
  fetchGoogleOAuthStartUrl,
  syncGoogleClientInsights,
} from '@/lib/api';
import { jobTypeLabel } from '@/lib/job-labels';
import type {
  AgencyClient,
  ClientLeadSummary,
  ClientOffboardAuditRow,
  OnboardingItem,
  OnboardingSummaryResponse,
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

type TabId = 'overview' | 'checklist' | 'channels' | 'campaigns' | 'leads' | 'contracts';

const CLIENT_STATUSES = ['prospect', 'onboarding', 'active', 'paused'] as const;

const OFFBOARD_REASONS = [
  { value: 'contract_ended', label: 'Hết hợp đồng' },
  { value: 'churn', label: 'Churn / rời agency' },
  { value: 'compliance', label: 'Tuân thủ / bảo mật' },
  { value: 'other', label: 'Khác' },
] as const;

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
  if (status === 'archived') return 'badge-paused';
  if (status === 'offboarding') return 'badge-onboarding';
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
  const [onboarding, setOnboarding] = useState<OnboardingSummaryResponse | null>(null);
  const [perfRows, setPerfRows] = useState<PerformanceRow[]>([]);
  const [error, setError] = useState('');
  const [actionMsg, setActionMsg] = useState('');
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState(false);
  const [channelForm, setChannelForm] = useState({
    channel: 'meta',
    external_account_id: '',
    display_name: '',
    facebook_page_id: '',
  });
  const [editForm, setEditForm] = useState<ClientEditForm>({
    name: '',
    industry_slug: '',
    owner_am_id: '',
    notes: '',
    status: 'prospect',
  });
  const [clientLeads, setClientLeads] = useState<ClientLeadSummary[]>([]);
  const [clientContracts, setClientContracts] = useState<
    Array<{ id: number; title: string; status: string; amount_vnd: number; lead_id: number | null }>
  >([]);
  const [tokenAccountId, setTokenAccountId] = useState('');
  const [tokenValue, setTokenValue] = useState('');
  const [editChannelId, setEditChannelId] = useState<string | null>(null);
  const [editChannelForm, setEditChannelForm] = useState({
    external_account_id: '',
    display_name: '',
    status: 'active',
    facebook_page_id: '',
  });
  const [accessToken, setAccessToken] = useState('');
  const [offboardReason, setOffboardReason] = useState('contract_ended');
  const [offboardNote, setOffboardNote] = useState('');
  const [offboardAudit, setOffboardAudit] = useState<ClientOffboardAuditRow[]>([]);
  const [showOffboardConfirm, setShowOffboardConfirm] = useState(false);

  const canWrite = canAgencyWrite(user);
  const canConfigure = canAgencyConfigure(user);
  const tenantLocked = Boolean(client?.tenant_locked || client?.status === 'archived');
  const canMutate = canWrite && !tenantLocked;

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
      const [detail, perf, ob, leadsOut] = await Promise.all([
        fetchAgencyClient(access, clientId),
        fetchClientPerformance(access, clientId, { group_by: 'campaign' }),
        fetchClientOnboardingSummary(access, clientId),
        fetchClientLeads(access, clientId).catch(() => ({ leads: [] })),
      ]);
      setClient(detail);
      setPerfRows(perf.rows ?? []);
      setOnboarding(ob);
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
      setAccessToken(access);
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

  useEffect(() => {
    if (tab !== 'contracts' || !accessToken || !clientId) return;
    void (async () => {
      try {
        const out = await fetchAgencyClientContracts(accessToken, clientId);
        setClientContracts(out.contracts ?? []);
      } catch {
        setClientContracts([]);
      }
    })();
  }, [tab, accessToken, clientId]);

  useEffect(() => {
    if (!clientId || !accessToken || !tenantLocked) {
      setOffboardAudit([]);
      return;
    }
    void (async () => {
      try {
        const out = await fetchClientOffboardAudit(accessToken, clientId);
        setOffboardAudit(out.rows ?? []);
      } catch {
        setOffboardAudit([]);
      }
    })();
  }, [clientId, accessToken, tenantLocked]);

  function setTab(next: TabId) {
    const qs = new URLSearchParams(searchParams.toString());
    if (next === 'overview') qs.delete('tab');
    else qs.set('tab', next);
    const suffix = qs.toString() ? `?${qs.toString()}` : '';
    router.replace(`/agency/clients/${clientId}${suffix}`);
  }

  async function handleOffboard() {
    const access = getAccessToken();
    if (!access || !canConfigure || tenantLocked) return;
    if (
      !window.confirm(
        'Offboard client này? Tất cả token kênh sẽ bị thu hồi, portal users bị vô hiệu hoá, client chuyển archived.',
      )
    ) {
      return;
    }
    setBusy(true);
    setActionMsg('');
    setError('');
    try {
      const out = await offboardAgencyClient(access, clientId, {
        reason: offboardReason,
        note: offboardNote.trim() || undefined,
      });
      await reload(access);
      const auditOut = await fetchClientOffboardAudit(access, clientId);
      setOffboardAudit(auditOut.rows ?? []);
      setShowOffboardConfirm(false);
      setOffboardNote('');
      const idem = out.idempotent ? ' (idempotent)' : '';
      setActionMsg(
        `Client đã offboard · ${out.tokens_revoked} token thu hồi · ${out.portal_users_deactivated} portal user vô hiệu${idem}`,
      );
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Offboard thất bại');
    } finally {
      setBusy(false);
    }
  }

  async function toggleChecklist(item: OnboardingItem) {
    const access = getAccessToken();
    if (!access || !canMutate) return;
    setBusy(true);
    setActionMsg('');
    try {
      const out = await patchClientOnboardingItem(access, clientId, item.item_key, {
        completed: !item.completed,
        completed_by: user?.email ?? user?.display_name ?? 'staff',
      });
      const summary = await fetchClientOnboardingSummary(access, clientId);
      setOnboarding(summary);
      setActionMsg('Đã cập nhật checklist');
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Cập nhật checklist thất bại');
    } finally {
      setBusy(false);
    }
  }

  async function handleActivate(force = false) {
    const access = getAccessToken();
    if (!access || !canMutate) return;
    setBusy(true);
    setActionMsg('');
    setError('');
    try {
      const updated = await activateAgencyClient(access, clientId, force);
      setClient(updated);
      const summary = await fetchClientOnboardingSummary(access, clientId);
      setOnboarding(summary);
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

  async function handleNudgeWorkflow() {
    const access = getAccessToken();
    if (!access || !canMutate) return;
    setBusy(true);
    setActionMsg('');
    try {
      await postClientOnboardingNudge(access, clientId);
      const summary = await fetchClientOnboardingSummary(access, clientId);
      setOnboarding(summary);
      setActionMsg('Đã gửi nudge workflow');
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Nudge workflow thất bại');
    } finally {
      setBusy(false);
    }
  }

  async function handleStartWorkflow() {
    const access = getAccessToken();
    if (!access || !canMutate) return;
    setBusy(true);
    setActionMsg('');
    try {
      await postClientOnboardingStartWorkflow(access, clientId, {
        started_by: user?.email ?? user?.display_name ?? 'staff',
      });
      const summary = await fetchClientOnboardingSummary(access, clientId);
      setOnboarding(summary);
      setActionMsg('Đã khởi tạo onboarding workflow');
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Khởi tạo workflow thất bại');
    } finally {
      setBusy(false);
    }
  }

  async function handleAddChannel(e: React.FormEvent) {
    e.preventDefault();
    const access = getAccessToken();
    if (!access || !canMutate) return;
    setBusy(true);
    setActionMsg('');
    setError('');
    try {
      const updated = await addClientChannelAccount(access, clientId, channelForm);
      setClient(updated);
      setChannelForm({ channel: 'meta', external_account_id: '', display_name: '', facebook_page_id: '' });
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
      facebook_page_id: acc.facebook_page_id ?? '',
    });
    setActionMsg('');
    setError('');
  }

  async function handleUpdateChannel(e: React.FormEvent) {
    e.preventDefault();
    const access = getAccessToken();
    if (!access || !canMutate || !editChannelId) return;
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
    if (!access || !canMutate) return;
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
    if (!access || !canMutate) return;
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
    if (!access || !canMutate) return;
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
    if (!access || !canMutate || !tokenAccountId) return;
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
    if (!access || !canMutate) return;
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

  async function handleSyncGoogleInsights() {
    const access = getAccessToken();
    if (!access || !canMutate) return;
    setBusy(true);
    setActionMsg('');
    setError('');
    try {
      const out = await syncGoogleClientInsights(access, clientId);
      const warn = out.pilot?.warning ? ` · ${String(out.pilot.warning)}` : '';
      setActionMsg(`Đã enqueue job: ${jobTypeLabel('google_insights_sync')}${warn}`);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Sync Google insights thất bại');
    } finally {
      setBusy(false);
    }
  }

  async function handleGoogleOAuthConnect(accountId: string) {
    const access = getAccessToken();
    if (!access || !canMutate) return;
    setBusy(true);
    setError('');
    try {
      const out = await fetchGoogleOAuthStartUrl(access, clientId, accountId);
      if (out.pilot?.warning) {
        setActionMsg(String(out.pilot.warning));
      }
      window.location.href = out.authorization_url;
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Không mở được Google OAuth');
      setBusy(false);
    }
  }

  useEffect(() => {
    if (searchParams.get('google_oauth') === 'ok') {
      setActionMsg('Google OAuth connected — refresh token đã lưu vault');
    }
  }, [searchParams]);

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
              {tenantLocked ? (
                <span className="agency-status-badge badge-paused" title="Tenant locked — mutations blocked">
                  tenant locked
                </span>
              ) : null}
            </div>
            <p className="muted">AM: {client.owner_am_id || '—'} · Ngành: {client.industry_slug || '—'}</p>

            <div className="agency-tabs" role="tablist">
              {(
                [
                  ['overview', 'Tổng quan'],
                  ['checklist', `Checklist ${progress.completed}/${progress.total}`],
                  ['channels', 'Kênh ads'],
                  ['campaigns', 'Campaign map'],
                  ['leads', `Leads (${clientLeads.length})`],
                  ['contracts', `Hợp đồng (${clientContracts.length})`],
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
                {canMutate ? (
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

                {tenantLocked ? (
                  <div style={{ marginTop: '1.5rem', padding: '1rem', border: '1px solid var(--border)', borderRadius: 8 }}>
                    <h3 style={{ fontSize: '1rem', marginTop: 0 }}>Offboard audit</h3>
                    <p className="muted" style={{ marginTop: 0 }}>
                      Client đã archived — mọi mutation agency bị chặn (403 tenant_archived).
                    </p>
                    {offboardAudit.length > 0 ? (
                      <table className="perf-table">
                        <thead>
                          <tr>
                            <th>Thời điểm</th>
                            <th>Người thực hiện</th>
                            <th>Lý do</th>
                            <th>Token</th>
                            <th>Portal</th>
                          </tr>
                        </thead>
                        <tbody>
                          {offboardAudit.map((row) => (
                            <tr key={row.id}>
                              <td>{row.created_at?.slice(0, 19).replace('T', ' ') ?? '—'}</td>
                              <td>{row.initiated_by}</td>
                              <td>
                                {row.reason}
                                {row.note ? ` · ${row.note}` : ''}
                              </td>
                              <td>{row.tokens_revoked}</td>
                              <td>{row.portal_users_deactivated}</td>
                            </tr>
                          ))}
                        </tbody>
                      </table>
                    ) : (
                      <p className="muted">Chưa có audit row (DDL chưa apply?).</p>
                    )}
                  </div>
                ) : canConfigure ? (
                  <div style={{ marginTop: '1.5rem', padding: '1rem', border: '1px solid var(--border)', borderRadius: 8 }}>
                    <h3 style={{ fontSize: '1rem', marginTop: 0, color: 'var(--danger, #b91c1c)' }}>
                      Offboard client
                    </h3>
                    <p className="muted" style={{ marginTop: 0, fontSize: '0.9rem' }}>
                      Thu hồi token kênh, vô hiệu hoá portal users, chuyển status → archived. Thao tác không thể hoàn
                      tác tự động.
                    </p>
                    {showOffboardConfirm ? (
                      <div style={{ display: 'grid', gap: '0.75rem', maxWidth: 420 }}>
                        <label>
                          Lý do
                          <select
                            value={offboardReason}
                            onChange={(e) => setOffboardReason(e.target.value)}
                            style={{ padding: '0.5rem', width: '100%' }}
                          >
                            {OFFBOARD_REASONS.map((r) => (
                              <option key={r.value} value={r.value}>
                                {r.label}
                              </option>
                            ))}
                          </select>
                        </label>
                        <label>
                          Ghi chú (tuỳ chọn)
                          <textarea
                            value={offboardNote}
                            onChange={(e) => setOffboardNote(e.target.value)}
                            rows={2}
                          />
                        </label>
                        <div style={{ display: 'flex', gap: '0.5rem', flexWrap: 'wrap' }}>
                          <button
                            type="button"
                            className="btn btn-sm"
                            disabled={busy}
                            onClick={() => void handleOffboard()}
                          >
                            Xác nhận offboard
                          </button>
                          <button
                            type="button"
                            className="btn btn-secondary btn-sm"
                            disabled={busy}
                            onClick={() => setShowOffboardConfirm(false)}
                          >
                            Hủy
                          </button>
                        </div>
                      </div>
                    ) : (
                      <button
                        type="button"
                        className="btn btn-secondary btn-sm"
                        disabled={busy}
                        onClick={() => setShowOffboardConfirm(true)}
                      >
                        Bắt đầu offboard…
                      </button>
                    )}
                  </div>
                ) : null}

                <h3 style={{ fontSize: '1rem', marginTop: '1.5rem' }}>Performance (Meta + Google, 7 ngày)</h3>
                {canMutate ? (
                  <div style={{ display: 'flex', gap: '0.5rem', flexWrap: 'wrap', marginBottom: '0.75rem' }}>
                    <button
                      type="button"
                      className="btn btn-secondary btn-sm"
                      disabled={busy}
                      onClick={() => void handleSyncInsights()}
                    >
                      Sync Meta now
                    </button>
                    <button
                      type="button"
                      className="btn btn-secondary btn-sm"
                      disabled={busy}
                      onClick={() => void handleSyncGoogleInsights()}
                    >
                      Sync Google now
                    </button>
                  </div>
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

            {tab === 'checklist' && onboarding ? (
              <div style={{ marginTop: '1rem' }}>
                <ClientOnboardingWidget
                  client={client}
                  summary={onboarding}
                  canWrite={canMutate}
                  busy={busy}
                  onToggleItem={(item) => void toggleChecklist(item)}
                  onActivate={(force) => void handleActivate(force)}
                  onNudgeWorkflow={() => void handleNudgeWorkflow()}
                  onStartWorkflow={() => void handleStartWorkflow()}
                />
              </div>
            ) : null}

            {tab === 'channels' ? (
              <div style={{ marginTop: '1rem' }}>
                {canMutate ? (
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
                    {channelForm.channel === 'meta' ? (
                      <input
                        placeholder="Facebook Page ID (webhook routing — tuỳ chọn)"
                        value={channelForm.facebook_page_id}
                        onChange={(e) => setChannelForm((f) => ({ ...f, facebook_page_id: e.target.value }))}
                        style={{ padding: '0.5rem' }}
                      />
                    ) : null}
                    <button type="submit" className="btn btn-sm" disabled={busy}>
                      Thêm channel
                    </button>
                  </form>
                ) : null}

                {editChannelId && canMutate ? (
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
                    <input
                      placeholder="Facebook Page ID (webhook routing)"
                      value={editChannelForm.facebook_page_id}
                      onChange={(e) => setEditChannelForm((f) => ({ ...f, facebook_page_id: e.target.value }))}
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
                      <th>Page ID</th>
                      <th>Tên hiển thị</th>
                      <th>Token</th>
                      <th>Status</th>
                      {canMutate ? <th /> : null}
                    </tr>
                  </thead>
                  <tbody>
                    {(client.channel_accounts ?? []).map((acc) => (
                      <tr key={acc.id}>
                        <td>{acc.channel}</td>
                        <td>{acc.external_account_id ?? '—'}</td>
                        <td>{acc.facebook_page_id ?? '—'}</td>
                        <td>{acc.display_name ?? '—'}</td>
                        <td>{acc.token_status ?? (acc.has_token ? 'ok' : '—')}</td>
                        <td>{acc.status ?? '—'}</td>
                        {canMutate ? (
                          <td style={{ whiteSpace: 'nowrap' }}>
                            <button type="button" className="btn btn-secondary btn-sm" disabled={busy} onClick={() => startEditChannel(acc)}>
                              Sửa
                            </button>{' '}
                            {acc.channel === 'meta' && (acc.has_token || acc.token_status === 'valid') ? (
                              <button type="button" className="btn btn-secondary btn-sm" disabled={busy} onClick={() => void handleRevokeToken(acc.id)}>
                                Thu hồi token
                              </button>
                            ) : null}{' '}
                            {acc.channel === 'google' && canMutate ? (
                              <button
                                type="button"
                                className="btn btn-secondary btn-sm"
                                disabled={busy}
                                onClick={() => void handleGoogleOAuthConnect(acc.id)}
                              >
                                Connect OAuth
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
                        <td colSpan={canMutate ? 6 : 5} className="muted">
                          Chưa có channel account — thêm Meta act_… ở form trên
                        </td>
                      </tr>
                    ) : null}
                  </tbody>
                </table>

                {canMutate && (client.channel_accounts ?? []).some((a) => a.channel === 'meta') ? (
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
                ) : canMutate ? (
                  <p className="muted" style={{ marginTop: '1rem' }}>
                    Thêm Meta channel account trước khi lưu token.
                  </p>
                ) : null}
              </div>
            ) : null}

            {tab === 'campaigns' ? (
              <div style={{ marginTop: '1rem' }}>
                <p className="muted" style={{ marginTop: 0 }}>
                  <Link href={`/crm/hub?client_id=${clientId}`} className="nav-link">
                    Xem tất cả trên Hub map
                  </Link>
                </p>
                {accessToken ? (
                  <HubCampaignMapsPanel
                    token={accessToken}
                    canWrite={canMutate}
                    clientId={clientId}
                    clientLabel={`${client.code} · ${client.name}`}
                    onFeedback={setActionMsg}
                    onError={setError}
                  />
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

            {tab === 'contracts' ? (
              <div style={{ marginTop: '1rem', overflowX: 'auto' }}>
                <table className="perf-table">
                  <thead>
                    <tr>
                      <th>HĐ</th>
                      <th>Trạng thái</th>
                      <th>Giá trị</th>
                      <th>Lead</th>
                    </tr>
                  </thead>
                  <tbody>
                    {clientContracts.map((ct) => (
                      <tr key={ct.id}>
                        <td>{ct.title}</td>
                        <td>{ct.status}</td>
                        <td>{fmtVnd(ct.amount_vnd)}</td>
                        <td>
                          {ct.lead_id ? (
                            <Link href={`/crm/leads/${ct.lead_id}`} className="nav-link">
                              #{ct.lead_id}
                            </Link>
                          ) : (
                            '—'
                          )}
                        </td>
                      </tr>
                    ))}
                    {clientContracts.length === 0 ? (
                      <tr>
                        <td colSpan={4} className="muted">
                          Chưa có hợp đồng gắn client này
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
