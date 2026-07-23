'use client';

import Link from 'next/link';
import { useCallback, useEffect, useState } from 'react';
import { useParams, useRouter } from 'next/navigation';
import { OpsNav } from '@/components/OpsNav';
import { ServiceDeliveryWorkflowPanel } from '@/components/ServiceDeliveryWorkflowPanel';
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

export default function CrmServiceDeliveryDetailPage() {
  const router = useRouter();
  const params = useParams();
  const lifecycleId = Number(params.id);
  const [user, setUser] = useState<StoredStaffUser | null>(null);
  const [row, setRow] = useState<Record<string, unknown> | null>(null);
  const [stage, setStage] = useState('lead');
  const [notes, setNotes] = useState('');
  const [assignedAm, setAssignedAm] = useState('');
  const [assignedSp, setAssignedSp] = useState('');
  const [token, setToken] = useState('');
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
      setToken(access);
      setLoading(true);
      try {
        const data = await fetchServiceLifecycleDetail(access, lifecycleId);
        setRow(data);
        setStage(String(data.stage ?? 'lead'));
        setNotes(String(data.notes ?? ''));
        setAssignedAm(data.assigned_am != null ? String(data.assigned_am) : '');
        setAssignedSp(data.assigned_sp != null ? String(data.assigned_sp) : '');
      } catch (err) {
        setError(err instanceof Error ? err.message : 'Tải thất bại');
      } finally {
        setLoading(false);
      }
    })();
  }, [ensureAuth, lifecycleId]);

  async function onSaveMeta(e: React.FormEvent) {
    e.preventDefault();
    if (!user) return;
    const access = getAccessToken();
    if (!access) return;
    setSaving(true);
    setError('');
    setMessage('');
    try {
      const updated = await patchServiceLifecycle(access, lifecycleId, {
        notes: notes.trim(),
        assigned_am: assignedAm ? Number(assignedAm) : null,
        assigned_sp: assignedSp ? Number(assignedSp) : null,
      });
      setRow({ ...row, ...updated });
      setMessage('Đã lưu ghi chú / AM / SP');
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
    <main style={{ maxWidth: 1000, margin: '0 auto', padding: '1.5rem' }}>
      <OpsNav user={user} onLogout={logout} />
      <p style={{ margin: '0 0 1rem' }}>
        <Link href="/crm/service-delivery" className="nav-link">
          ← Service delivery
        </Link>
      </p>
      {loading ? <p className="muted">Đang tải…</p> : null}
      {error ? <p className="error">{error}</p> : null}
      {message ? <p style={{ color: 'var(--accent)' }}>{message}</p> : null}
      {row && !loading ? (
        <>
          <div className="card" style={{ marginBottom: '1rem', padding: '1rem' }}>
            <h2 style={{ margin: 0, fontSize: '1.15rem' }}>
              #{lifecycleId} · {String(row.service_slug ?? '')}
            </h2>
            <p className="muted">
              Stage: {stage} · Status: {String(row.status ?? '')}
            </p>
            <form onSubmit={(e) => void onSaveMeta(e)} style={{ display: 'grid', gap: '0.65rem', marginTop: '0.75rem' }}>
              <label style={{ display: 'grid', gap: '0.35rem' }}>
                <span className="muted">Ghi chú</span>
                <textarea
                  value={notes}
                  onChange={(e) => setNotes(e.target.value)}
                  rows={2}
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
              <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '0.65rem' }}>
                <label style={{ display: 'grid', gap: '0.35rem' }}>
                  <span className="muted">AM (staff id)</span>
                  <input
                    value={assignedAm}
                    onChange={(e) => setAssignedAm(e.target.value)}
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
                  <span className="muted">SP (staff id)</span>
                  <input
                    value={assignedSp}
                    onChange={(e) => setAssignedSp(e.target.value)}
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
              </div>
              <button type="submit" className="btn btn-sm" disabled={saving || !hasCap(user, 'crm_board', 'edit')}>
                Lưu meta
              </button>
            </form>
          </div>

          {token ? (
            <ServiceDeliveryWorkflowPanel
              token={token}
              user={user}
              lifecycleId={lifecycleId}
              initialStage={stage}
              onStageChanged={setStage}
            />
          ) : null}

          {events.length > 0 ? (
            <div className="card" style={{ marginTop: '1rem', padding: '1rem' }}>
              <h3 style={{ fontSize: '1rem', marginTop: 0 }}>Events</h3>
              <ul style={{ margin: 0, paddingLeft: '1.1rem' }}>
                {events.slice(-10).map((ev) => (
                  <li key={ev.id}>
                    → {ev.to_stage}: {ev.notes || '—'} ({ev.created_at})
                  </li>
                ))}
              </ul>
            </div>
          ) : null}
        </>
      ) : null}
    </main>
  );
}
