'use client';

import Link from 'next/link';
import { useCallback, useEffect, useState, type CSSProperties } from 'react';
import { useRouter, useSearchParams } from 'next/navigation';
import { OpsNav } from '@/components/OpsNav';
import {
  fetchCrmCampaignWrites,
  fetchCrmCampaignWritesStats,
  postCrmCampaignWriteApprove,
  postCrmCampaignWriteReject,
  postCrmCampaignWriteSubmit,
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

type StatusTab = 'all' | 'pending_approval' | 'executed' | 'execution_failed' | 'rejected';

type WriteRow = {
  id: string;
  client_id: string;
  external_campaign_id: string;
  external_campaign_name: string | null;
  change_type: string;
  new_value: Record<string, unknown>;
  status: string;
  submitted_by: string;
  execution_error: string | null;
  created_at: string;
  lifecycle_id: number | null;
};

const TABS: Array<{ id: StatusTab; label: string }> = [
  { id: 'all', label: 'Tất cả' },
  { id: 'pending_approval', label: 'Chờ duyệt' },
  { id: 'executed', label: 'Đã chạy Meta' },
  { id: 'execution_failed', label: 'Lỗi execution' },
  { id: 'rejected', label: 'Từ chối' },
];

const STATUS_LABEL: Record<string, string> = {
  pending_approval: 'Chờ duyệt',
  approved: 'Đã duyệt',
  executed: 'Executed',
  execution_failed: 'Execution failed',
  rejected: 'Từ chối',
};

export function CrmCampaignWritesContent() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const [user, setUser] = useState<StoredStaffUser | null>(null);
  const [tab, setTab] = useState<StatusTab>('pending_approval');
  const [rows, setRows] = useState<WriteRow[]>([]);
  const [stats, setStats] = useState<Record<string, number>>({});
  const [error, setError] = useState('');
  const [message, setMessage] = useState('');
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [showSubmit, setShowSubmit] = useState(false);
  const [pilotWarning, setPilotWarning] = useState('');
  const [form, setForm] = useState({
    client_id: '',
    external_campaign_id: '',
    external_campaign_name: '',
    daily_budget_vnd: '',
  });

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
      if (!hasCap(me, 'crm_board', 'view') && !hasCap(me, 'meta_campaign_write', 'view')) {
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

  const reload = useCallback(async (access: string, status: StatusTab) => {
    const [statsOut, listOut] = await Promise.all([
      fetchCrmCampaignWritesStats(access),
      fetchCrmCampaignWrites(access, status),
    ]);
    setStats(statsOut.stats ?? {});
    setRows(listOut.rows ?? []);
  }, []);

  useEffect(() => {
    const q = searchParams.get('status');
    if (
      q === 'all' ||
      q === 'pending_approval' ||
      q === 'executed' ||
      q === 'execution_failed' ||
      q === 'rejected'
    ) {
      setTab(q);
    }
  }, [searchParams]);

  useEffect(() => {
    void (async () => {
      const access = await ensureAuth();
      if (!access) return;
      setLoading(true);
      setError('');
      try {
        await reload(access, tab);
      } catch (err) {
        setError(err instanceof Error ? err.message : 'Tải thất bại');
      } finally {
        setLoading(false);
      }
    })();
  }, [ensureAuth, reload, tab]);

  async function onSubmit(e: React.FormEvent) {
    e.preventDefault();
    if (!user || !hasCap(user, 'crm_board', 'edit')) return;
    const access = getAccessToken();
    if (!access) return;
    setSaving(true);
    setMessage('');
    setError('');
    setPilotWarning('');
    try {
      const out = (await postCrmCampaignWriteSubmit(access, {
        ...form,
        daily_budget_vnd: Number(form.daily_budget_vnd),
      })) as { pilot_check?: { warning?: string | null } };
      const warn = out.pilot_check?.warning;
      if (warn) setPilotWarning(warn);
      setMessage('Đã gửi yêu cầu đổi budget — chờ GDKD duyệt');
      setShowSubmit(false);
      await reload(access, tab);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Gửi thất bại');
    } finally {
      setSaving(false);
    }
  }

  async function onApprove(row: WriteRow) {
    if (!user || !hasCap(user, 'meta_campaign_write', 'approve')) return;
    const access = getAccessToken();
    if (!access) return;
    setSaving(true);
    setError('');
    try {
      await postCrmCampaignWriteApprove(access, row.id);
      setMessage('Đã duyệt — Temporal sẽ execute trên Meta');
      await reload(access, tab);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Duyệt thất bại');
    } finally {
      setSaving(false);
    }
  }

  async function onReject(row: WriteRow) {
    if (!user || !hasCap(user, 'meta_campaign_write', 'approve')) return;
    const access = getAccessToken();
    if (!access) return;
    setSaving(true);
    setError('');
    try {
      await postCrmCampaignWriteReject(access, row.id, 'Rejected from hub');
      setMessage('Đã từ chối');
      await reload(access, tab);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Từ chối thất bại');
    } finally {
      setSaving(false);
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

  const canSubmit = hasCap(user, 'crm_board', 'edit');
  const canApprove = hasCap(user, 'meta_campaign_write', 'approve');

  return (
    <main style={{ maxWidth: 1100, margin: '0 auto', padding: '1.5rem' }}>
      <OpsNav user={user} onLogout={logout} />
      <div style={{ display: 'flex', justifyContent: 'space-between', gap: '0.75rem', flexWrap: 'wrap' }}>
        <div>
          <h1 style={{ margin: 0, fontSize: '1.25rem' }}>Campaign Write Hub</h1>
          <p className="muted" style={{ margin: '0.35rem 0 0' }}>
            AM gửi đổi budget Meta → GDKD duyệt → executed auto-tick Launch QA budget_confirmed
          </p>
        </div>
        {canSubmit ? (
          <button type="button" className="btn btn-sm" onClick={() => setShowSubmit((v) => !v)}>
            {showSubmit ? 'Đóng form' : 'Gửi đổi budget'}
          </button>
        ) : null}
      </div>

      {(stats.pending_campaign_writes ?? stats.pending_approval ?? 0) > 0 ? (
        <p
          style={{
            margin: '1rem 0 0',
            padding: '0.55rem 0.75rem',
            borderRadius: 8,
            border: '1px solid #c90',
            background: 'rgba(255, 200, 0, 0.04)',
            fontSize: '0.9rem',
          }}
        >
          {stats.pending_campaign_writes ?? stats.pending_approval} yêu cầu chờ duyệt Meta write.
        </p>
      ) : null}

      {loading ? <p className="muted" style={{ marginTop: '1rem' }}>Đang tải…</p> : null}
      {error ? <p className="error">{error}</p> : null}
      {message ? <p style={{ color: 'var(--accent)' }}>{message}</p> : null}
      {pilotWarning ? (
        <p style={{ color: '#c90', fontSize: '0.9rem' }}>Pilot: {pilotWarning}</p>
      ) : null}

      {showSubmit && canSubmit ? (
        <form
          onSubmit={(e) => void onSubmit(e)}
          className="card"
          style={{ marginTop: '1rem', padding: '1rem', display: 'grid', gap: '0.5rem' }}
        >
          <h3 style={{ margin: 0, fontSize: '1rem' }}>Gửi đổi daily budget (Meta)</h3>
          <input
            placeholder="Client UUID"
            value={form.client_id}
            onChange={(e) => setForm({ ...form, client_id: e.target.value })}
            required
            style={inputStyle}
          />
          <input
            placeholder="Campaign code (external_campaign_id)"
            value={form.external_campaign_id}
            onChange={(e) => setForm({ ...form, external_campaign_id: e.target.value })}
            required
            style={inputStyle}
          />
          <input
            placeholder="Daily budget VND"
            type="number"
            min={0}
            value={form.daily_budget_vnd}
            onChange={(e) => setForm({ ...form, daily_budget_vnd: e.target.value })}
            required
            style={inputStyle}
          />
          <button type="submit" className="btn btn-sm" disabled={saving}>
            Gửi duyệt
          </button>
        </form>
      ) : null}

      <div style={{ display: 'flex', flexWrap: 'wrap', gap: '0.35rem', margin: '1rem 0 0.75rem' }}>
        {TABS.map((t) => (
          <button
            key={t.id}
            type="button"
            className={tab === t.id ? 'btn btn-sm' : 'btn btn-sm btn-ghost'}
            onClick={() => setTab(t.id)}
          >
            {t.label} ({stats[t.id] ?? (t.id === 'all' ? stats.all : 0) ?? 0})
          </button>
        ))}
      </div>

      <div className="card" style={{ padding: '0.75rem', overflowX: 'auto' }}>
        <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: '0.85rem' }}>
          <thead>
            <tr className="muted">
              <th style={{ textAlign: 'left', padding: '0.35rem' }}>Campaign</th>
              <th style={{ textAlign: 'left', padding: '0.35rem' }}>Budget mới</th>
              <th style={{ textAlign: 'left', padding: '0.35rem' }}>Trạng thái</th>
              <th style={{ textAlign: 'left', padding: '0.35rem' }}>Gửi</th>
              <th style={{ textAlign: 'left', padding: '0.35rem' }}>Thao tác</th>
            </tr>
          </thead>
          <tbody>
            {rows.length === 0 ? (
              <tr>
                <td colSpan={5} className="muted" style={{ padding: '0.75rem' }}>
                  Không có yêu cầu.
                </td>
              </tr>
            ) : null}
            {rows.map((row) => (
              <tr key={row.id} style={{ borderTop: '1px solid var(--border)' }}>
                <td style={{ padding: '0.35rem' }}>
                  <strong>{row.external_campaign_id}</strong>
                  {row.execution_error ? (
                    <div className="muted" style={{ fontSize: '0.8rem' }}>
                      {row.execution_error}
                    </div>
                  ) : null}
                </td>
                <td style={{ padding: '0.35rem' }}>
                  {Number(row.new_value?.daily_budget_vnd ?? 0).toLocaleString('vi-VN')} VND
                </td>
                <td style={{ padding: '0.35rem' }}>{STATUS_LABEL[row.status] ?? row.status}</td>
                <td style={{ padding: '0.35rem' }}>{row.created_at?.slice(0, 10) ?? '—'}</td>
                <td style={{ padding: '0.35rem' }}>
                  {row.lifecycle_id ? (
                    <Link href={`/crm/service-delivery/${row.lifecycle_id}?tab=launch_qa`} className="nav-link">
                      Lifecycle
                    </Link>
                  ) : null}
                  {row.status === 'pending_approval' && canApprove ? (
                    <>
                      {' · '}
                      <button type="button" className="btn btn-sm" disabled={saving} onClick={() => void onApprove(row)}>
                        Duyệt
                      </button>
                      {' · '}
                      <button type="button" className="btn btn-sm btn-ghost" disabled={saving} onClick={() => void onReject(row)}>
                        Từ chối
                      </button>
                    </>
                  ) : null}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </main>
  );
}

const inputStyle: CSSProperties = {
  background: 'var(--bg)',
  border: '1px solid var(--border)',
  borderRadius: 8,
  padding: '0.45rem 0.65rem',
  color: 'var(--text)',
};
