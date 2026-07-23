'use client';

import Link from 'next/link';
import { useCallback, useEffect, useState } from 'react';
import { useRouter } from 'next/navigation';
import { OpsNav } from '@/components/OpsNav';
import {
  createSopRun,
  fetchSopOverdueTasks,
  fetchSopRuns,
  fetchSopTemplates,
  staffMe,
  staffRefresh,
  type SopOverdueTaskRow,
  type SopRunRow,
  type SopTemplateRow,
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

export default function CrmSopPage() {
  const router = useRouter();
  const [user, setUser] = useState<StoredStaffUser | null>(null);
  const [templates, setTemplates] = useState<SopTemplateRow[]>([]);
  const [runs, setRuns] = useState<SopRunRow[]>([]);
  const [overdue, setOverdue] = useState<SopOverdueTaskRow[]>([]);
  const [overdueEnabled, setOverdueEnabled] = useState(false);
  const [runName, setRunName] = useState('');
  const [templateId, setTemplateId] = useState('');
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(false);
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
        setError('Không có quyền SOP');
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

  const load = useCallback(async (access: string) => {
    const [tpl, runRows, od] = await Promise.all([
      fetchSopTemplates(access),
      fetchSopRuns(access, 'all'),
      fetchSopOverdueTasks(access, 100),
    ]);
    setTemplates(tpl);
    setRuns(runRows);
    setOverdue(od.tasks ?? []);
    setOverdueEnabled(Boolean(od.overdue_enabled));
  }, []);

  useEffect(() => {
    void (async () => {
      const access = await ensureAuth();
      if (!access) return;
      setLoading(true);
      setError('');
      try {
        await load(access);
      } catch (err) {
        setError(err instanceof Error ? err.message : 'Tải SOP thất bại');
      } finally {
        setLoading(false);
      }
    })();
  }, [ensureAuth, load]);

  async function onCreateRun(e: React.FormEvent) {
    e.preventDefault();
    if (!user || !runName.trim()) return;
    const access = getAccessToken();
    if (!access) return;
    setSaving(true);
    setError('');
    try {
      await createSopRun(access, {
        name: runName.trim(),
        template_id: templateId ? Number(templateId) : undefined,
      });
      setRunName('');
      await load(access);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Tạo run thất bại');
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
    <main style={{ maxWidth: 960, margin: '0 auto', padding: '1.5rem' }}>
      <OpsNav user={user} onLogout={logout} />
      <h1 style={{ margin: '0 0 0.35rem', fontSize: '1.25rem' }}>SOP Hub</h1>
      <p className="muted" style={{ margin: '0 0 1rem', fontSize: '0.9rem' }}>
        Launch checklist · template MKT-LAUNCH-14D · liên kết lifecycle qua tab SOP Launch
      </p>

      {loading ? <p className="muted">Đang tải…</p> : null}
      {error ? <p className="error">{error}</p> : null}

      {overdue.length > 0 ? (
        <div
          className="card"
          style={{
            marginBottom: '1rem',
            padding: '1rem',
            border: '1px solid var(--danger, #c53030)',
            background: 'rgba(197, 48, 48, 0.08)',
          }}
        >
          <h2 style={{ margin: '0 0 0.35rem', fontSize: '1rem', color: 'var(--danger, #c53030)' }}>
            {overdue.length} task SOP quá hạn
          </h2>
          <p className="muted" style={{ margin: '0 0 0.75rem', fontSize: '0.85rem' }}>
            Escalate ops (FR-SD-03)
            {overdueEnabled ? ' · PTT_SOP_OVERDUE_ESCALATE=1' : ' · bật PTT_SOP_OVERDUE_ESCALATE trên prod'}
          </p>
          <div style={{ overflowX: 'auto' }}>
            <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: '0.85rem' }}>
              <thead>
                <tr className="muted">
                  <th style={{ textAlign: 'left', padding: '0.35rem' }}>Run</th>
                  <th style={{ textAlign: 'left', padding: '0.35rem' }}>Task</th>
                  <th style={{ textAlign: 'left', padding: '0.35rem' }}>Hạn</th>
                  <th style={{ textAlign: 'left', padding: '0.35rem' }}>Quá</th>
                  <th style={{ textAlign: 'left', padding: '0.35rem' }}>Lifecycle</th>
                </tr>
              </thead>
              <tbody>
                {overdue.map((t) => (
                  <tr key={t.id} style={{ borderTop: '1px solid var(--border)' }}>
                    <td style={{ padding: '0.35rem' }}>
                      #{t.run_id} · {t.run_name}
                    </td>
                    <td style={{ padding: '0.35rem' }}>{t.title}</td>
                    <td style={{ padding: '0.35rem' }}>{t.due_date}</td>
                    <td style={{ padding: '0.35rem' }}>{t.days_overdue} ngày</td>
                    <td style={{ padding: '0.35rem' }}>
                      {t.lifecycle_id ? (
                        <Link href={`/crm/service-delivery/${t.lifecycle_id}?tab=sop`} className="nav-link">
                          #{t.lifecycle_id}
                        </Link>
                      ) : (
                        '—'
                      )}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      ) : !loading ? (
        <p className="muted" style={{ marginBottom: '1rem' }}>
          Không có task SOP quá hạn.
        </p>
      ) : null}

      <div className="card" style={{ marginBottom: '1rem' }}>
        <h2 style={{ marginTop: 0, fontSize: '1.15rem' }}>SOP Templates</h2>
        {templates.length === 0 && !loading ? <p className="muted">Chưa có template.</p> : null}
        <ul style={{ margin: 0, paddingLeft: '1.1rem' }}>
          {templates.map((t) => (
            <li key={t.id}>
              #{t.id} · {t.name} ({t.channel})
            </li>
          ))}
        </ul>
      </div>
      <div className="card">
        <h2 style={{ marginTop: 0, fontSize: '1.15rem' }}>SOP Runs</h2>
        {runs.length === 0 && !loading ? <p className="muted">Chưa có run.</p> : null}
        <ul style={{ margin: '0 0 1rem', paddingLeft: '1.1rem' }}>
          {runs.map((r) => (
            <li key={r.id}>
              #{r.id} · {r.name} — {r.status}
              {r.template_name ? ` · ${r.template_name}` : ''}
              {(r.stats?.overdue ?? 0) > 0 ? (
                <span style={{ color: 'var(--danger)', marginLeft: '0.35rem' }}>
                  ({r.stats?.overdue} quá hạn)
                </span>
              ) : null}
            </li>
          ))}
        </ul>
        {hasCap(user, 'crm_board', 'edit') ? (
          <form onSubmit={(e) => void onCreateRun(e)} style={{ display: 'grid', gap: '0.5rem' }}>
            <input
              value={runName}
              onChange={(e) => setRunName(e.target.value)}
              placeholder="Tên SOP run mới"
              disabled={saving}
              style={{
                background: 'var(--bg)',
                border: '1px solid var(--border)',
                borderRadius: 8,
                padding: '0.55rem 0.75rem',
                color: 'var(--text)',
              }}
            />
            <select
              value={templateId}
              onChange={(e) => setTemplateId(e.target.value)}
              disabled={saving}
              style={{
                background: 'var(--bg)',
                border: '1px solid var(--border)',
                borderRadius: 8,
                padding: '0.55rem 0.75rem',
                color: 'var(--text)',
              }}
            >
              <option value="">— Không dùng template —</option>
              {templates.map((t) => (
                <option key={t.id} value={String(t.id)}>
                  {t.name}
                </option>
              ))}
            </select>
            <button type="submit" className="btn btn-secondary btn-sm" disabled={saving || !runName.trim()}>
              + Tạo run
            </button>
          </form>
        ) : null}
      </div>
    </main>
  );
}
