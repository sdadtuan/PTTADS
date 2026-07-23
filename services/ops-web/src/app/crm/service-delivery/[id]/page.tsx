'use client';

import Link from 'next/link';
import { useCallback, useEffect, useState } from 'react';
import { useParams, useRouter } from 'next/navigation';
import { LifecycleFinancePanel } from '@/components/LifecycleFinancePanel';
import { LifecycleHubLinksPanel } from '@/components/LifecycleHubLinksPanel';
import { LifecycleStaffPicker } from '@/components/LifecycleStaffPicker';
import { LifecycleTmmtPanel } from '@/components/LifecycleTmmtPanel';
import { OpsNav } from '@/components/OpsNav';
import { ServiceDeliveryWorkflowPanel } from '@/components/ServiceDeliveryWorkflowPanel';
import {
  fetchServiceLifecycleContext,
  fetchServiceLifecycleDetail,
  patchServiceLifecycle,
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

const STAGES = ['lead', 'consult', 'proposal', 'onboard', 'deliver', 'handover', 'retain'];

export default function CrmServiceDeliveryDetailPage() {
  const router = useRouter();
  const params = useParams();
  const lifecycleId = Number(params.id);
  const [user, setUser] = useState<StoredStaffUser | null>(null);
  const [row, setRow] = useState<Record<string, unknown> | null>(null);
  const [context, setContext] = useState<Record<string, unknown> | null>(null);
  const [stage, setStage] = useState('lead');
  const [notes, setNotes] = useState('');
  const [backStage, setBackStage] = useState('');
  const [token, setToken] = useState('');
  const [error, setError] = useState('');
  const [message, setMessage] = useState('');
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [detailTab, setDetailTab] = useState<'workflow' | 'tmmt' | 'finance'>('workflow');

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
      setToken(access);
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
      setToken(access);
      return access;
    }
  }, [router]);

  const reloadDetail = useCallback(async (access: string) => {
    const [data, ctx] = await Promise.all([
      fetchServiceLifecycleDetail(access, lifecycleId),
      fetchServiceLifecycleContext(access, lifecycleId).catch(() => null),
    ]);
    setRow(data);
    setContext(ctx);
    setStage(String(data.stage ?? 'lead'));
    setNotes(String(data.notes ?? ''));
  }, [lifecycleId]);

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
        await reloadDetail(access);
      } catch (err) {
        setError(err instanceof Error ? err.message : 'Tải thất bại');
      } finally {
        setLoading(false);
      }
    })();
  }, [ensureAuth, lifecycleId, reloadDetail]);

  async function onSaveNotes(e: React.FormEvent) {
    e.preventDefault();
    if (!user || !token) return;
    setSaving(true);
    setError('');
    setMessage('');
    try {
      await patchServiceLifecycle(token, lifecycleId, { notes: notes.trim() });
      setMessage('Đã lưu ghi chú');
      await reloadDetail(token);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Lưu thất bại');
    } finally {
      setSaving(false);
    }
  }

  async function onBackwardStage() {
    if (!user || !token || !backStage) return;
    const idx = STAGES.indexOf(stage);
    const targetIdx = STAGES.indexOf(backStage);
    if (targetIdx >= idx) {
      setError('Chỉ lùi stage — chọn giai đoạn trước hiện tại');
      return;
    }
    if (!window.confirm(`Lùi stage ${stage} → ${backStage}?`)) return;
    setSaving(true);
    try {
      await patchServiceLifecycle(token, lifecycleId, { stage: backStage, notes: notes.trim() });
      setStage(backStage);
      setMessage(`Đã lùi → ${backStage}`);
      await reloadDetail(token);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Lùi stage thất bại');
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
      {row && !loading && token ? (
        <>
          <div className="card" style={{ marginBottom: '1rem', padding: '1rem' }}>
            <h2 style={{ margin: 0, fontSize: '1.15rem' }}>
              #{lifecycleId} · {String(row.service_slug ?? '')}
            </h2>
            <p className="muted">
              Stage: {stage} · Status: {String(row.status ?? '')}
            </p>
            <form onSubmit={(e) => void onSaveNotes(e)} style={{ display: 'grid', gap: '0.65rem', marginTop: '0.75rem' }}>
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
              <button type="submit" className="btn btn-sm" disabled={saving || !hasCap(user, 'crm_board', 'edit')}>
                Lưu ghi chú
              </button>
            </form>
            {hasCap(user, 'crm_board', 'edit') ? (
              <div style={{ display: 'flex', gap: '0.5rem', alignItems: 'end', marginTop: '0.75rem', flexWrap: 'wrap' }}>
                <label style={{ display: 'grid', gap: '0.3rem' }}>
                  <span className="muted">Lùi stage (chỉ backward)</span>
                  <select
                    value={backStage}
                    onChange={(e) => setBackStage(e.target.value)}
                    style={{
                      background: 'var(--bg)',
                      border: '1px solid var(--border)',
                      borderRadius: 8,
                      padding: '0.45rem',
                      color: 'var(--text)',
                    }}
                  >
                    <option value="">— Chọn —</option>
                    {STAGES.filter((s) => STAGES.indexOf(s) < STAGES.indexOf(stage)).map((s) => (
                      <option key={s} value={s}>
                        {s}
                      </option>
                    ))}
                  </select>
                </label>
                <button type="button" className="btn btn-sm btn-secondary" disabled={!backStage || saving} onClick={() => void onBackwardStage()}>
                  Lùi stage
                </button>
              </div>
            ) : null}
          </div>

          <LifecycleHubLinksPanel token={token} lifecycleId={lifecycleId} />

          <LifecycleStaffPicker
            token={token}
            user={user}
            lifecycleId={lifecycleId}
            assignedAm={row.assigned_am != null ? Number(row.assigned_am) : null}
            assignedSp={row.assigned_sp != null ? Number(row.assigned_sp) : null}
            context={context as { lead?: { owner_id?: number; owner_name?: string }; presales?: { assigned_sp?: number; assigned_sp_name?: string } }}
            onSaved={() => void reloadDetail(token)}
            onError={setError}
          />

          <div style={{ display: 'flex', gap: '0.35rem', marginBottom: '0.75rem' }}>
            <button
              type="button"
              className={detailTab === 'workflow' ? 'btn btn-sm' : 'btn btn-sm btn-ghost'}
              onClick={() => setDetailTab('workflow')}
            >
              Workflow
            </button>
            <button
              type="button"
              className={detailTab === 'tmmt' ? 'btn btn-sm' : 'btn btn-sm btn-ghost'}
              onClick={() => setDetailTab('tmmt')}
            >
              TMMT chính thức
            </button>
            <button
              type="button"
              className={detailTab === 'finance' ? 'btn btn-sm' : 'btn btn-sm btn-ghost'}
              onClick={() => setDetailTab('finance')}
            >
              Tài chính
            </button>
          </div>

          {detailTab === 'workflow' ? (
            <ServiceDeliveryWorkflowPanel
              token={token}
              user={user}
              lifecycleId={lifecycleId}
              initialStage={stage}
              onStageChanged={setStage}
              onFinanceRefresh={() => void reloadDetail(token)}
              onOpenTmmtTab={() => setDetailTab('tmmt')}
              onOpenFinanceTab={() => setDetailTab('finance')}
            />
          ) : detailTab === 'tmmt' ? (
            <LifecycleTmmtPanel
              token={token}
              user={user}
              lifecycleId={lifecycleId}
              stage={stage}
              onSaved={() => void reloadDetail(token)}
            />
          ) : (
            <LifecycleFinancePanel
              token={token}
              user={user}
              lifecycleId={lifecycleId}
              onSaved={() => void reloadDetail(token)}
            />
          )}

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
