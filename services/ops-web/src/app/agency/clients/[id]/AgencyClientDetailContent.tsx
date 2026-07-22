'use client';

import Link from 'next/link';
import { useCallback, useEffect, useState } from 'react';
import { useParams, useRouter, useSearchParams } from 'next/navigation';
import { OpsNav } from '@/components/OpsNav';
import {
  activateAgencyClient,
  addClientChannelAccount,
  fetchAgencyClient,
  fetchClientOnboarding,
  fetchClientPerformance,
  patchClientOnboardingItem,
  staffMe,
  staffRefresh,
} from '@/lib/api';
import type { AgencyClient, OnboardingItem, OnboardingResponse, PerformanceRow } from '@/lib/api';
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

type TabId = 'overview' | 'checklist' | 'channels';

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

  const canWrite = hasCap(user, 'crm_agency', 'create');

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
      const [detail, perf, ob] = await Promise.all([
        fetchAgencyClient(access, clientId),
        fetchClientPerformance(access, clientId, { group_by: 'campaign' }),
        fetchClientOnboarding(access, clientId),
      ]);
      setClient(detail);
      setPerfRows(perf.rows ?? []);
      setOnboarding(ob);
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
      setActionMsg('Client đã kích hoạt');
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
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Thêm channel thất bại');
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
              <span className={`agency-status-badge ${statusBadgeClass(client.status)}`}>{client.status}</span>
            </div>
            <p className="muted">AM: {client.owner_am_id || '—'} · Ngành: {client.industry_slug || '—'}</p>

            <div className="agency-tabs" role="tablist">
              {(
                [
                  ['overview', 'Tổng quan'],
                  ['checklist', `Checklist ${progress.completed}/${progress.total}`],
                  ['channels', 'Kênh ads'],
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
                <h3 style={{ fontSize: '1rem', marginTop: '1.5rem' }}>Performance (Meta, 7 ngày)</h3>
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
                <div style={{ marginTop: '1rem', display: 'flex', gap: '0.75rem', flexWrap: 'wrap' }}>
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
                      disabled={busy || client.status === 'active'}
                      onClick={() => {
                        if (window.confirm('Bỏ qua checklist và kích hoạt (force)?')) {
                          void handleActivate(true);
                        }
                      }}
                    >
                      Force activate
                    </button>
                  ) : null}
                </div>
                {activateDisabled && client.status !== 'active' ? (
                  <p className="muted">Hoàn thành checklist trước khi kích hoạt (PTT_CLIENT_STRICT_ONBOARDING).</p>
                ) : null}
              </div>
            ) : null}

            {tab === 'channels' ? (
              <div style={{ marginTop: '1rem' }}>
                <table className="perf-table">
                  <thead>
                    <tr>
                      <th>Channel</th>
                      <th>External ID</th>
                      <th>Tên hiển thị</th>
                      <th>Status</th>
                    </tr>
                  </thead>
                  <tbody>
                    {(client.channel_accounts ?? []).map((acc) => (
                      <tr key={acc.id}>
                        <td>{acc.channel}</td>
                        <td>{acc.external_account_id ?? '—'}</td>
                        <td>{acc.display_name ?? '—'}</td>
                        <td>{acc.status ?? '—'}</td>
                      </tr>
                    ))}
                    {(client.channel_accounts ?? []).length === 0 ? (
                      <tr>
                        <td colSpan={4} className="muted">
                          Chưa có channel account
                        </td>
                      </tr>
                    ) : null}
                  </tbody>
                </table>

                {canWrite ? (
                  <form onSubmit={(e) => void handleAddChannel(e)} style={{ marginTop: '1.25rem', display: 'grid', gap: '0.75rem', maxWidth: 480 }}>
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
                      Lưu channel
                    </button>
                  </form>
                ) : null}
              </div>
            ) : null}
          </>
        ) : null}
      </div>
    </main>
  );
}
