'use client';

import { useCallback, useEffect, useState } from 'react';
import { useRouter } from 'next/navigation';
import { OpsNav } from '@/components/OpsNav';
import {
  createSopRun,
  fetchSopRuns,
  fetchSopTemplates,
  staffMe,
  staffRefresh,
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
    const [tpl, runRows] = await Promise.all([fetchSopTemplates(access), fetchSopRuns(access, 'all')]);
    setTemplates(tpl);
    setRuns(runRows);
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
      <div className="card" style={{ marginBottom: '1rem' }}>
        <h2 style={{ marginTop: 0, fontSize: '1.15rem' }}>SOP Templates</h2>
        {loading ? <p className="muted">Đang tải…</p> : null}
        {error ? <p className="error">{error}</p> : null}
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
