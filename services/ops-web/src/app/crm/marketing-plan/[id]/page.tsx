'use client';

import Link from 'next/link';
import { useCallback, useEffect, useState } from 'react';
import { useParams, useRouter } from 'next/navigation';
import { OpsNav } from '@/components/OpsNav';
import { fetchMarketingPlanDetail, patchMarketingPlan, staffMe, staffRefresh } from '@/lib/api';
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

export default function CrmMarketingPlanDetailPage() {
  const router = useRouter();
  const params = useParams();
  const planId = Number(params.id);
  const [user, setUser] = useState<StoredStaffUser | null>(null);
  const [plan, setPlan] = useState<Record<string, unknown> | null>(null);
  const [name, setName] = useState('');
  const [status, setStatus] = useState('');
  const [notes, setNotes] = useState('');
  const [error, setError] = useState('');
  const [message, setMessage] = useState('');
  const [loading, setLoading] = useState(true);
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

  useEffect(() => {
    if (!Number.isFinite(planId) || planId <= 0) {
      setError('ID không hợp lệ');
      setLoading(false);
      return;
    }
    void (async () => {
      const access = await ensureAuth();
      if (!access) return;
      setLoading(true);
      try {
        const data = await fetchMarketingPlanDetail(access, planId);
        setPlan(data);
        setName(String(data.name ?? ''));
        setStatus(String(data.status ?? 'draft'));
        setNotes(String(data.notes ?? ''));
      } catch (err) {
        setError(err instanceof Error ? err.message : 'Tải thất bại');
      } finally {
        setLoading(false);
      }
    })();
  }, [ensureAuth, planId]);

  async function onSave(e: React.FormEvent) {
    e.preventDefault();
    if (!user) return;
    const access = getAccessToken();
    if (!access) return;
    setSaving(true);
    setError('');
    setMessage('');
    try {
      const updated = await patchMarketingPlan(access, planId, {
        name: name.trim(),
        status,
        notes: notes.trim(),
      });
      setPlan({ ...plan, ...updated });
      setMessage('Đã lưu');
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Lưu thất bại');
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

  const milestones = (plan?.milestones as Array<{ id: number; title: string; status: string }>) ?? [];

  return (
    <main style={{ maxWidth: 900, margin: '0 auto', padding: '1.5rem' }}>
      <OpsNav user={user} onLogout={logout} />
      <p style={{ margin: '0 0 1rem' }}>
        <Link href="/crm/marketing-plan" className="nav-link">
          ← Kế hoạch marketing
        </Link>
      </p>
      <div className="card">
        {loading ? <p className="muted">Đang tải…</p> : null}
        {error ? <p className="error">{error}</p> : null}
        {message ? <p style={{ color: 'var(--accent)' }}>{message}</p> : null}
        {plan && !loading ? (
          <form onSubmit={(e) => void onSave(e)} style={{ display: 'grid', gap: '0.75rem' }}>
            <h2 style={{ margin: 0, fontSize: '1.15rem' }}>#{planId} · {String(plan.name ?? '')}</h2>
            <label style={{ display: 'grid', gap: '0.35rem' }}>
              <span className="muted">Tên</span>
              <input
                value={name}
                onChange={(e) => setName(e.target.value)}
                disabled={!hasCap(user, 'crm_board', 'edit') || saving}
                style={{
                  background: 'var(--bg)',
                  border: '1px solid var(--border)',
                  borderRadius: 8,
                  padding: '0.55rem 0.75rem',
                  color: 'var(--text)',
                }}
              />
            </label>
            <label style={{ display: 'grid', gap: '0.35rem' }}>
              <span className="muted">Trạng thái</span>
              <select
                value={status}
                onChange={(e) => setStatus(e.target.value)}
                disabled={!hasCap(user, 'crm_board', 'edit') || saving}
                style={{
                  background: 'var(--bg)',
                  border: '1px solid var(--border)',
                  borderRadius: 8,
                  padding: '0.55rem 0.75rem',
                  color: 'var(--text)',
                }}
              >
                {['draft', 'review', 'active', 'paused', 'completed', 'archived', 'cancelled'].map((s) => (
                  <option key={s} value={s}>
                    {s}
                  </option>
                ))}
              </select>
            </label>
            <label style={{ display: 'grid', gap: '0.35rem' }}>
              <span className="muted">Ghi chú</span>
              <textarea
                value={notes}
                onChange={(e) => setNotes(e.target.value)}
                rows={3}
                disabled={!hasCap(user, 'crm_board', 'edit') || saving}
                style={{
                  background: 'var(--bg)',
                  border: '1px solid var(--border)',
                  borderRadius: 8,
                  padding: '0.55rem 0.75rem',
                  color: 'var(--text)',
                  resize: 'vertical',
                }}
              />
            </label>
            <button type="submit" className="btn btn-sm" disabled={saving || !hasCap(user, 'crm_board', 'edit')}>
              Lưu
            </button>
            {milestones.length > 0 ? (
              <div>
                <h3 style={{ fontSize: '1rem' }}>Milestone ({milestones.length})</h3>
                <ul style={{ margin: 0, paddingLeft: '1.1rem' }}>
                  {milestones.map((m) => (
                    <li key={m.id}>
                      {m.title} — {m.status}
                    </li>
                  ))}
                </ul>
              </div>
            ) : null}
          </form>
        ) : null}
      </div>
    </main>
  );
}
