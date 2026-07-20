'use client';

import Link from 'next/link';
import { useCallback, useEffect, useState } from 'react';
import { useParams, useRouter } from 'next/navigation';
import { OpsNav } from '@/components/OpsNav';
import { fetchServiceLifecycleDetail, patchServiceLifecycle, staffMe, staffRefresh } from '@/lib/api';
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

const STAGES = ['lead', 'consult', 'proposal', 'onboard', 'deliver', 'handover', 'retain'];

export default function CrmServiceDeliveryDetailPage() {
  const router = useRouter();
  const params = useParams();
  const lifecycleId = Number(params.id);
  const [user, setUser] = useState<StoredStaffUser | null>(null);
  const [row, setRow] = useState<Record<string, unknown> | null>(null);
  const [stage, setStage] = useState('lead');
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
    if (!Number.isFinite(lifecycleId) || lifecycleId <= 0) {
      setError('ID không hợp lệ');
      setLoading(false);
      return;
    }
    void (async () => {
      const access = await ensureAuth();
      if (!access) return;
      setLoading(true);
      try {
        const data = await fetchServiceLifecycleDetail(access, lifecycleId);
        setRow(data);
        setStage(String(data.stage ?? 'lead'));
        setNotes(String(data.notes ?? ''));
      } catch (err) {
        setError(err instanceof Error ? err.message : 'Tải thất bại');
      } finally {
        setLoading(false);
      }
    })();
  }, [ensureAuth, lifecycleId]);

  async function onSave(e: React.FormEvent) {
    e.preventDefault();
    if (!user) return;
    const access = getAccessToken();
    if (!access) return;
    setSaving(true);
    setError('');
    setMessage('');
    try {
      const updated = await patchServiceLifecycle(access, lifecycleId, { stage, notes: notes.trim() });
      setRow({ ...row, ...updated });
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

  const events = (row?.events as Array<{ id: number; to_stage: string; notes: string; created_at: string }>) ?? [];

  if (!user) {
    return (
      <main style={{ padding: '2rem' }}>
        <p className="muted">Đang tải…</p>
      </main>
    );
  }

  return (
    <main style={{ maxWidth: 900, margin: '0 auto', padding: '1.5rem' }}>
      <OpsNav user={user} onLogout={logout} />
      <p style={{ margin: '0 0 1rem' }}>
        <Link href="/crm/service-delivery" className="nav-link">
          ← Service delivery
        </Link>
      </p>
      <div className="card">
        {loading ? <p className="muted">Đang tải…</p> : null}
        {error ? <p className="error">{error}</p> : null}
        {message ? <p style={{ color: 'var(--accent)' }}>{message}</p> : null}
        {row && !loading ? (
          <form onSubmit={(e) => void onSave(e)} style={{ display: 'grid', gap: '0.75rem' }}>
            <h2 style={{ margin: 0, fontSize: '1.15rem' }}>
              #{lifecycleId} · {String(row.service_slug ?? '')}
            </h2>
            <p className="muted">Status: {String(row.status ?? '')}</p>
            <label style={{ display: 'grid', gap: '0.35rem' }}>
              <span className="muted">Stage</span>
              <select
                value={stage}
                onChange={(e) => setStage(e.target.value)}
                disabled={!hasCap(user, 'crm_board', 'edit') || saving}
                style={{
                  background: 'var(--bg)',
                  border: '1px solid var(--border)',
                  borderRadius: 8,
                  padding: '0.55rem 0.75rem',
                  color: 'var(--text)',
                }}
              >
                {STAGES.map((s) => (
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
              Lưu stage
            </button>
            {events.length > 0 ? (
              <div>
                <h3 style={{ fontSize: '1rem' }}>Events</h3>
                <ul style={{ margin: 0, paddingLeft: '1.1rem' }}>
                  {events.slice(-10).map((ev) => (
                    <li key={ev.id}>
                      → {ev.to_stage}: {ev.notes || '—'} ({ev.created_at})
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
