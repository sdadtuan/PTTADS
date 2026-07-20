'use client';

import Link from 'next/link';
import { useCallback, useEffect, useState } from 'react';
import { useRouter } from 'next/navigation';
import { OpsNav } from '@/components/OpsNav';
import { createReProject, fetchReProjects, staffMe, staffRefresh, type ReProjectRow } from '@/lib/api';
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

export default function CrmReProjectsPage() {
  const router = useRouter();
  const [user, setUser] = useState<StoredStaffUser | null>(null);
  const [rows, setRows] = useState<ReProjectRow[]>([]);
  const [q, setQ] = useState('');
  const [query, setQuery] = useState('');
  const [newName, setNewName] = useState('');
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
      if (!hasCap(me, 'crm_re_projects', 'view') && !hasCap(me, 'crm_re_projects_products', 'view')) {
        setError('Không có quyền dự án BĐS');
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
    void (async () => {
      const access = await ensureAuth();
      if (!access) return;
      setLoading(true);
      setError('');
      try {
        setRows(await fetchReProjects(access, query || undefined));
      } catch (err) {
        setError(err instanceof Error ? err.message : 'Tải dự án thất bại');
      } finally {
        setLoading(false);
      }
    })();
  }, [ensureAuth, query]);

  async function onCreate(e: React.FormEvent) {
    e.preventDefault();
    if (!newName.trim()) return;
    const access = getAccessToken();
    if (!access) return;
    setSaving(true);
    try {
      await createReProject(access, { name: newName.trim(), project_type: 'can_ho' });
      setNewName('');
      setRows(await fetchReProjects(access, query || undefined));
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Tạo dự án thất bại');
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
      <div className="card">
        <h2 style={{ marginTop: 0, fontSize: '1.15rem' }}>Dự án BĐS</h2>
        <form
          onSubmit={(e) => {
            e.preventDefault();
            setQuery(q.trim());
          }}
          style={{ display: 'flex', gap: '0.5rem', marginBottom: '1rem' }}
        >
          <input
            value={q}
            onChange={(e) => setQ(e.target.value)}
            placeholder="Tìm tên / mã / quận…"
            style={{
              flex: 1,
              background: 'var(--bg)',
              border: '1px solid var(--border)',
              borderRadius: 8,
              padding: '0.55rem 0.75rem',
              color: 'var(--text)',
            }}
          />
          <button type="submit" className="btn btn-sm">
            Tìm
          </button>
        </form>
        {loading ? <p className="muted">Đang tải…</p> : null}
        {error ? <p className="error">{error}</p> : null}
        <ul style={{ margin: '0 0 1rem', paddingLeft: '1.1rem' }}>
          {rows.map((p) => (
            <li key={p.id} style={{ marginBottom: '0.35rem' }}>
              <Link href={`/crm/re-projects/${p.id}`} className="nav-link">
                {p.name}
              </Link>{' '}
              <span className="muted">
                {p.code || `#${p.id}`} · {p.project_type_label ?? p.project_type} · {p.status}
                {p.city ? ` · ${p.city}` : ''}
              </span>
            </li>
          ))}
        </ul>
        {rows.length === 0 && !loading ? <p className="muted">Chưa có dự án.</p> : null}
        {hasCap(user, 'crm_re_projects', 'create') ? (
          <form onSubmit={(e) => void onCreate(e)} style={{ display: 'flex', gap: '0.5rem' }}>
            <input
              value={newName}
              onChange={(e) => setNewName(e.target.value)}
              placeholder="Tên dự án mới"
              disabled={saving}
              style={{
                flex: 1,
                background: 'var(--bg)',
                border: '1px solid var(--border)',
                borderRadius: 8,
                padding: '0.55rem 0.75rem',
                color: 'var(--text)',
              }}
            />
            <button type="submit" className="btn btn-secondary btn-sm" disabled={saving || !newName.trim()}>
              + Dự án
            </button>
          </form>
        ) : null}
      </div>
    </main>
  );
}
