'use client';

import Link from 'next/link';
import { useCallback, useEffect, useState, type CSSProperties } from 'react';
import { useRouter, useSearchParams } from 'next/navigation';
import { OpsNav } from '@/components/OpsNav';
import {
  fetchCrmCreatives,
  fetchCrmCreativesStats,
  postCrmCreativeSubmit,
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

type StatusTab = 'all' | 'pending_client' | 'approved' | 'rejected';

type CreativeRow = {
  id: string;
  client_id: string;
  title: string;
  status: string;
  version: number;
  external_campaign_id: string | null;
  external_campaign_name: string | null;
  submitted_at: string;
  reviewed_at: string | null;
  review_note: string | null;
  lifecycle_id: number | null;
};

const TABS: Array<{ id: StatusTab; label: string }> = [
  { id: 'all', label: 'Tất cả' },
  { id: 'pending_client', label: 'Chờ client' },
  { id: 'approved', label: 'Đã duyệt' },
  { id: 'rejected', label: 'Từ chối' },
];

const STATUS_LABEL: Record<string, string> = {
  pending_client: 'Chờ client',
  approved: 'Đã duyệt',
  rejected: 'Từ chối',
  withdrawn: 'Thu hồi',
};

export function CrmCreativesContent() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const [user, setUser] = useState<StoredStaffUser | null>(null);
  const [tab, setTab] = useState<StatusTab>('pending_client');
  const [rows, setRows] = useState<CreativeRow[]>([]);
  const [stats, setStats] = useState<Record<string, number>>({});
  const [error, setError] = useState('');
  const [message, setMessage] = useState('');
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [showSubmit, setShowSubmit] = useState(false);
  const [form, setForm] = useState({
    client_id: '',
    external_campaign_id: '',
    external_campaign_name: '',
    title: '',
    description: '',
    asset_url: '',
    resubmit: false,
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
      if (!hasCap(me, 'crm_board', 'view')) {
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
      fetchCrmCreativesStats(access),
      fetchCrmCreatives(access, status),
    ]);
    setStats(statsOut.stats ?? {});
    setRows(listOut.rows ?? []);
  }, []);

  useEffect(() => {
    const q = searchParams.get('status');
    if (q === 'all' || q === 'pending_client' || q === 'approved' || q === 'rejected') {
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
    try {
      await postCrmCreativeSubmit(access, form);
      setMessage(form.resubmit ? 'Đã gửi creative phiên bản mới' : 'Đã gửi creative — chờ client duyệt portal');
      setShowSubmit(false);
      await reload(access, tab);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Gửi thất bại');
    } finally {
      setSaving(false);
    }
  }

  function prefillResubmit(row: CreativeRow) {
    setForm({
      client_id: row.client_id,
      external_campaign_id: row.external_campaign_id ?? '',
      external_campaign_name: row.external_campaign_name ?? '',
      title: row.title,
      description: '',
      asset_url: '',
      resubmit: true,
    });
    setShowSubmit(true);
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

  const canEdit = hasCap(user, 'crm_board', 'edit');

  return (
    <main style={{ maxWidth: 1100, margin: '0 auto', padding: '1.5rem' }}>
      <OpsNav user={user} onLogout={logout} />
      <div style={{ display: 'flex', justifyContent: 'space-between', gap: '0.75rem', flexWrap: 'wrap' }}>
        <div>
          <h1 style={{ margin: 0, fontSize: '1.25rem' }}>Creative Hub</h1>
          <p className="muted" style={{ margin: '0.35rem 0 0' }}>
            MKT gửi creative → client duyệt portal → auto-tick Launch QA checklist
          </p>
        </div>
        {canEdit ? (
          <button type="button" className="btn btn-sm" onClick={() => setShowSubmit((v) => !v)}>
            {showSubmit ? 'Đóng form' : 'Gửi creative mới'}
          </button>
        ) : null}
      </div>

      {(stats.pending_creatives ?? stats.pending_client ?? 0) > 0 ? (
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
          {stats.pending_creatives ?? stats.pending_client} creative đang chờ client duyệt trên portal.
        </p>
      ) : null}

      {loading ? <p className="muted" style={{ marginTop: '1rem' }}>Đang tải…</p> : null}
      {error ? <p className="error">{error}</p> : null}
      {message ? <p style={{ color: 'var(--accent)' }}>{message}</p> : null}

      {showSubmit && canEdit ? (
        <form
          onSubmit={(e) => void onSubmit(e)}
          className="card"
          style={{ marginTop: '1rem', padding: '1rem', display: 'grid', gap: '0.5rem' }}
        >
          <h3 style={{ margin: 0, fontSize: '1rem' }}>
            {form.resubmit ? 'Gửi lại creative (version +1)' : 'Gửi creative mới'}
          </h3>
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
            placeholder="Tiêu đề"
            value={form.title}
            onChange={(e) => setForm({ ...form, title: e.target.value })}
            required
            style={inputStyle}
          />
          <textarea
            placeholder="Mô tả / brief"
            value={form.description}
            onChange={(e) => setForm({ ...form, description: e.target.value })}
            rows={2}
            style={inputStyle}
          />
          <input
            placeholder="Asset URL (tuỳ chọn)"
            value={form.asset_url}
            onChange={(e) => setForm({ ...form, asset_url: e.target.value })}
            style={inputStyle}
          />
          <button type="submit" className="btn btn-sm" disabled={saving}>
            Gửi portal
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
              <th style={{ textAlign: 'left', padding: '0.35rem' }}>Creative</th>
              <th style={{ textAlign: 'left', padding: '0.35rem' }}>Campaign</th>
              <th style={{ textAlign: 'left', padding: '0.35rem' }}>v</th>
              <th style={{ textAlign: 'left', padding: '0.35rem' }}>Trạng thái</th>
              <th style={{ textAlign: 'left', padding: '0.35rem' }}>Gửi</th>
              <th style={{ textAlign: 'left', padding: '0.35rem' }}>Link</th>
            </tr>
          </thead>
          <tbody>
            {rows.length === 0 ? (
              <tr>
                <td colSpan={6} className="muted" style={{ padding: '0.75rem' }}>
                  Không có creative.
                </td>
              </tr>
            ) : null}
            {rows.map((row) => (
              <tr key={row.id} style={{ borderTop: '1px solid var(--border)' }}>
                <td style={{ padding: '0.35rem' }}>
                  <strong>{row.title}</strong>
                  {row.review_note ? (
                    <div className="muted" style={{ fontSize: '0.8rem' }}>
                      Note: {row.review_note}
                    </div>
                  ) : null}
                </td>
                <td style={{ padding: '0.35rem' }}>{row.external_campaign_id ?? '—'}</td>
                <td style={{ padding: '0.35rem' }}>{row.version}</td>
                <td style={{ padding: '0.35rem' }}>{STATUS_LABEL[row.status] ?? row.status}</td>
                <td style={{ padding: '0.35rem' }}>{row.submitted_at?.slice(0, 10) ?? '—'}</td>
                <td style={{ padding: '0.35rem' }}>
                  {row.lifecycle_id ? (
                    <Link href={`/crm/service-delivery/${row.lifecycle_id}?tab=launch_qa`} className="nav-link">
                      Lifecycle
                    </Link>
                  ) : null}
                  {row.status === 'rejected' && canEdit ? (
                    <>
                      {' · '}
                      <button type="button" className="btn btn-sm btn-ghost" onClick={() => prefillResubmit(row)}>
                        Gửi lại
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
