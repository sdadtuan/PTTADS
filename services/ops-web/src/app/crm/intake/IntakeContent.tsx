'use client';

import Link from 'next/link';
import { useCallback, useEffect, useMemo, useState } from 'react';
import { useRouter, useSearchParams } from 'next/navigation';
import { OpsNav } from '@/components/OpsNav';
import {
  completeIntakeSession,
  createIntakeSession,
  fetchIntakeDefinitions,
  fetchIntakeSessions,
  fetchIntakeStats,
  generateIntakeAiSummary,
  patchIntakeSession,
  reopenIntakeSession,
  staffMe,
  staffRefresh,
  type IntakeSessionRow,
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

const BANT_KEYS = ['budget', 'authority', 'need', 'timeline', 'fit', 'history'] as const;
const DECISIONS = [
  { value: '', label: '— Chọn —' },
  { value: 'go', label: 'Go' },
  { value: 'nurture', label: 'Nurture' },
  { value: 'no_go', label: 'No-Go' },
];

export function IntakeContent() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const leadId = Number(searchParams.get('lead_id') || 0);
  const lifecycleId = Number(searchParams.get('lifecycle_id') || 0);

  const [user, setUser] = useState<StoredStaffUser | null>(null);
  const [sessions, setSessions] = useState<IntakeSessionRow[]>([]);
  const [active, setActive] = useState<IntakeSessionRow | null>(null);
  const [bant, setBant] = useState<Record<string, number>>({});
  const [decision, setDecision] = useState('');
  const [decisionReason, setDecisionReason] = useState('');
  const [contactName, setContactName] = useState('');
  const [need, setNeed] = useState('');
  const [error, setError] = useState('');
  const [message, setMessage] = useState('');
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [stats, setStats] = useState<Record<string, unknown> | null>(null);

  const contextOk = useMemo(
    () => (Number.isFinite(leadId) && leadId > 0) || (Number.isFinite(lifecycleId) && lifecycleId > 0),
    [leadId, lifecycleId],
  );

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
      if (!hasCap(me, 'crm_leads', 'view')) {
        setError('Không có quyền intake');
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

  const loadSessions = useCallback(
    async (access: string) => {
      const rows = await fetchIntakeSessions(access, {
        lead_id: leadId > 0 ? leadId : undefined,
        lifecycle_id: lifecycleId > 0 ? lifecycleId : undefined,
      });
      setSessions(rows);
      const draft = rows.find((s) => s.status === 'draft') ?? rows[0] ?? null;
      setActive(draft);
      if (draft) {
        setBant({ ...(draft.bant_json || {}) });
        setDecision(draft.decision || '');
        setDecisionReason(draft.decision_reason || '');
        setContactName(draft.contact_name || '');
        const crm = (draft.answers_json?.crm_fields || {}) as Record<string, string>;
        setNeed(String(crm.need || ''));
      }
    },
    [leadId, lifecycleId],
  );

  useEffect(() => {
    if (!contextOk) {
      setError('Cần lead_id hoặc lifecycle_id trong URL');
      setLoading(false);
      return;
    }
    void (async () => {
      const access = await ensureAuth();
      if (!access) return;
      setLoading(true);
      setError('');
      try {
        await fetchIntakeDefinitions(access);
        const statsOut = await fetchIntakeStats(access);
        setStats(statsOut);
        await loadSessions(access);
      } catch (err) {
        setError(err instanceof Error ? err.message : 'Tải intake thất bại');
      } finally {
        setLoading(false);
      }
    })();
  }, [contextOk, ensureAuth, loadSessions]);

  async function onCreate(mode: 'phone' | 'in_person') {
    const access = getAccessToken();
    if (!access || !user) return;
    if (!hasCap(user, 'crm_leads', 'edit')) {
      setError('Không có quyền tạo phiên');
      return;
    }
    setSaving(true);
    setError('');
    try {
      const created = await createIntakeSession(access, {
        lead_id: leadId > 0 ? leadId : undefined,
        lifecycle_id: lifecycleId > 0 ? lifecycleId : undefined,
        mode,
        service_slug: '_common',
      });
      setActive(created);
      await loadSessions(access);
      setMessage(`Đã tạo phiên #${created.id}`);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Tạo phiên thất bại');
    } finally {
      setSaving(false);
    }
  }

  async function onSave() {
    if (!active || !user) return;
    const access = getAccessToken();
    if (!access) return;
    setSaving(true);
    setError('');
    setMessage('');
    try {
      const updated = await patchIntakeSession(access, active.id, {
        bant_json: bant,
        decision,
        decision_reason: decisionReason,
        contact_name: contactName,
        answers_json: {
          ...(active.answers_json || {}),
          crm_fields: { need },
        },
      });
      setActive(updated);
      setMessage('Đã lưu phiên');
      await loadSessions(access);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Lưu thất bại');
    } finally {
      setSaving(false);
    }
  }

  async function onComplete() {
    if (!active || !user) return;
    const access = getAccessToken();
    if (!access) return;
    setSaving(true);
    setError('');
    try {
      await onSave();
      const updated = await completeIntakeSession(access, active.id);
      setActive(updated);
      setMessage('Đã hoàn thành intake');
      await loadSessions(access);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Hoàn thành thất bại');
    } finally {
      setSaving(false);
    }
  }

  async function onReopen() {
    if (!active || !user) return;
    const access = getAccessToken();
    if (!access) return;
    setSaving(true);
    setError('');
    setMessage('');
    try {
      const updated = await reopenIntakeSession(access, active.id);
      setActive(updated);
      setMessage('Đã mở lại phiên');
      await loadSessions(access);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Mở lại thất bại');
    } finally {
      setSaving(false);
    }
  }

  async function onAiSummary() {
    if (!active || !user) return;
    const access = getAccessToken();
    if (!access) return;
    setSaving(true);
    setError('');
    setMessage('');
    try {
      await generateIntakeAiSummary(access, active.id);
      setMessage('Đã tạo AI summary (stub hoặc Claude)');
      await loadSessions(access);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'AI summary thất bại');
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

  return (
    <main style={{ maxWidth: 900, margin: '0 auto', padding: '1.5rem' }}>
      <OpsNav user={user} onLogout={logout} />
      <p style={{ margin: '0 0 1rem' }}>
        {leadId > 0 ? (
          <Link href={`/crm/leads/${leadId}`} className="nav-link">
            ← Lead #{leadId}
          </Link>
        ) : (
          <span className="muted">Lifecycle #{lifecycleId}</span>
        )}
      </p>

      <div className="card">
        <h2 style={{ marginTop: 0, fontSize: '1.15rem' }}>Lead Intake</h2>
        {loading ? <p className="muted">Đang tải…</p> : null}
        {error ? <p className="error">{error}</p> : null}
        {message ? <p style={{ color: 'var(--accent)' }}>{message}</p> : null}

        {!loading && contextOk ? (
          <>
            <div style={{ display: 'flex', gap: '0.5rem', flexWrap: 'wrap', marginBottom: '1rem' }}>
              <button type="button" className="btn btn-sm" disabled={saving} onClick={() => void onCreate('phone')}>
                + Phiên gọi điện
              </button>
              <button
                type="button"
                className="btn btn-secondary btn-sm"
                disabled={saving}
                onClick={() => void onCreate('in_person')}
              >
                + Phiên gặp trực tiếp
              </button>
            </div>

            {sessions.length > 0 ? (
              <p className="muted">
                {sessions.length} phiên · BANT {active?.bant_total ?? 0}/30
                {stats && typeof stats.total_sessions === 'number'
                  ? ` · Tổng hệ thống ${stats.total_sessions}`
                  : ''}
              </p>
            ) : null}

            {active ? (
              <div style={{ display: 'grid', gap: '0.75rem' }}>
                <p>
                  Phiên #{active.id} · {active.mode} · {active.status}
                </p>
                <label style={{ display: 'grid', gap: '0.35rem' }}>
                  <span className="muted">Liên hệ</span>
                  <input
                    value={contactName}
                    onChange={(e) => setContactName(e.target.value)}
                    disabled={active.status === 'completed' || saving}
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
                  <span className="muted">Nhu cầu / pain</span>
                  <textarea
                    value={need}
                    onChange={(e) => setNeed(e.target.value)}
                    rows={3}
                    disabled={active.status === 'completed' || saving}
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
                <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(120px, 1fr))', gap: '0.5rem' }}>
                  {BANT_KEYS.map((key) => (
                    <label key={key} style={{ display: 'grid', gap: '0.25rem' }}>
                      <span className="muted">{key}</span>
                      <input
                        type="number"
                        min={0}
                        max={5}
                        value={bant[key] ?? ''}
                        onChange={(e) =>
                          setBant((prev) => ({ ...prev, [key]: Number(e.target.value) || 0 }))
                        }
                        disabled={active.status === 'completed' || saving}
                        style={{
                          background: 'var(--bg)',
                          border: '1px solid var(--border)',
                          borderRadius: 8,
                          padding: '0.45rem',
                          color: 'var(--text)',
                        }}
                      />
                    </label>
                  ))}
                </div>
                <label style={{ display: 'grid', gap: '0.35rem' }}>
                  <span className="muted">Quyết định</span>
                  <select
                    value={decision}
                    onChange={(e) => setDecision(e.target.value)}
                    disabled={active.status === 'completed' || saving}
                    style={{
                      background: 'var(--bg)',
                      border: '1px solid var(--border)',
                      borderRadius: 8,
                      padding: '0.55rem 0.75rem',
                      color: 'var(--text)',
                    }}
                  >
                    {DECISIONS.map((d) => (
                      <option key={d.value || 'empty'} value={d.value}>
                        {d.label}
                      </option>
                    ))}
                  </select>
                </label>
                <label style={{ display: 'grid', gap: '0.35rem' }}>
                  <span className="muted">Lý do</span>
                  <input
                    value={decisionReason}
                    onChange={(e) => setDecisionReason(e.target.value)}
                    disabled={active.status === 'completed' || saving}
                    style={{
                      background: 'var(--bg)',
                      border: '1px solid var(--border)',
                      borderRadius: 8,
                      padding: '0.55rem 0.75rem',
                      color: 'var(--text)',
                    }}
                  />
                </label>
                {active.status !== 'completed' ? (
                  <div style={{ display: 'flex', gap: '0.5rem', flexWrap: 'wrap' }}>
                    <button type="button" className="btn btn-sm" disabled={saving} onClick={() => void onSave()}>
                      Lưu nháp
                    </button>
                    <button type="button" className="btn btn-sm" disabled={saving} onClick={() => void onComplete()}>
                      Hoàn thành
                    </button>
                    <button
                      type="button"
                      className="btn btn-secondary btn-sm"
                      disabled={saving}
                      onClick={() => void onAiSummary()}
                    >
                      AI summary
                    </button>
                  </div>
                ) : (
                  <button
                    type="button"
                    className="btn btn-secondary btn-sm"
                    disabled={saving}
                    onClick={() => void onReopen()}
                  >
                    Mở lại phiên
                  </button>
                )}
              </div>
            ) : (
              <p className="muted">Chưa có phiên — tạo phiên mới ở trên.</p>
            )}
          </>
        ) : null}
      </div>
    </main>
  );
}
