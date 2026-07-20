'use client';

import Link from 'next/link';
import { useCallback, useEffect, useState } from 'react';
import { useRouter } from 'next/navigation';
import { OpsNav } from '@/components/OpsNav';
import {
  fetchCrmStaffList,
  fetchStaffCompetency,
  fetchStaffLevels,
  importCrmStaff,
  saveStaffCompetency,
  saveStaffLevels,
  staffMe,
  staffRefresh,
  type CrmStaffRow,
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

type StaffTab = 'roster' | 'import' | 'levels' | 'competency';

export default function CrmStaffPage() {
  const router = useRouter();
  const [user, setUser] = useState<StoredStaffUser | null>(null);
  const [tab, setTab] = useState<StaffTab>('roster');
  const [rows, setRows] = useState<CrmStaffRow[]>([]);
  const [summary, setSummary] = useState<Record<string, number>>({});
  const [levelsJson, setLevelsJson] = useState('[]');
  const [competencyJson, setCompetencyJson] = useState('{}');
  const [importJson, setImportJson] = useState('[]');
  const [q, setQ] = useState('');
  const [query, setQuery] = useState('');
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
      if (!hasCap(me, 'crm_staff_roster', 'view')) {
        setError('Không có quyền nhân sự');
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

  const loadTab = useCallback(async (access: string, nextTab: StaffTab) => {
    setLoading(true);
    setError('');
    try {
      if (nextTab === 'roster') {
        const out = await fetchCrmStaffList(access, { q: query || undefined });
        setRows(out.staff ?? []);
        setSummary(out.summary ?? {});
      } else if (nextTab === 'levels') {
        const levels = await fetchStaffLevels(access);
        setLevelsJson(JSON.stringify(levels, null, 2));
      } else if (nextTab === 'competency') {
        const competency = await fetchStaffCompetency(access);
        setCompetencyJson(JSON.stringify(competency, null, 2));
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Tải nhân viên thất bại');
    } finally {
      setLoading(false);
    }
  }, [query]);

  useEffect(() => {
    void (async () => {
      const access = await ensureAuth();
      if (!access) return;
      await loadTab(access, tab);
    })();
  }, [ensureAuth, tab, loadTab]);

  async function onSaveLevels(e: React.FormEvent) {
    e.preventDefault();
    const access = getAccessToken();
    if (!access) return;
    setSaving(true);
    setError('');
    try {
      const parsed = JSON.parse(levelsJson) as Array<Record<string, unknown>>;
      await saveStaffLevels(access, parsed);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Lưu levels thất bại');
    } finally {
      setSaving(false);
    }
  }

  async function onSaveCompetency(e: React.FormEvent) {
    e.preventDefault();
    const access = getAccessToken();
    if (!access) return;
    setSaving(true);
    setError('');
    try {
      const parsed = JSON.parse(competencyJson) as Record<string, unknown>;
      await saveStaffCompetency(access, parsed);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Lưu competency thất bại');
    } finally {
      setSaving(false);
    }
  }

  async function onImport(e: React.FormEvent) {
    e.preventDefault();
    const access = getAccessToken();
    if (!access) return;
    setSaving(true);
    setError('');
    try {
      const parsed = JSON.parse(importJson) as Array<Record<string, unknown>>;
      const out = await importCrmStaff(access, parsed);
      setImportJson('[]');
      setError('');
      alert(`Import xong: ${JSON.stringify(out)}`);
      setTab('roster');
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Import thất bại');
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

  const canEdit = hasCap(user, 'crm_staff_roster', 'edit');

  return (
    <main style={{ maxWidth: 960, margin: '0 auto', padding: '1.5rem' }}>
      <OpsNav user={user} onLogout={logout} />
      <div className="card">
        <h2 style={{ marginTop: 0, fontSize: '1.15rem' }}>Nhân viên</h2>
        <div style={{ display: 'flex', gap: '0.35rem', flexWrap: 'wrap', marginBottom: '1rem' }}>
          {(
            [
              { id: 'roster', label: 'Roster' },
              { id: 'import', label: 'Import' },
              { id: 'levels', label: 'Levels' },
              { id: 'competency', label: 'Competency' },
            ] as const
          ).map((t) => (
            <button
              key={t.id}
              type="button"
              className={`btn btn-sm${tab === t.id ? '' : ' btn-secondary'}`}
              onClick={() => setTab(t.id)}
            >
              {t.label}
            </button>
          ))}
        </div>
        {loading ? <p className="muted">Đang tải…</p> : null}
        {error ? <p className="error">{error}</p> : null}

        {tab === 'roster' ? (
          <>
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
                placeholder="Tìm tên / mã…"
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
            <p className="muted">
              Tổng {summary.staff_total ?? rows.length} · Active {summary.staff_active ?? '—'}
            </p>
            <ul style={{ margin: 0, paddingLeft: '1.1rem' }}>
              {rows.map((s) => (
                <li key={s.id} style={{ marginBottom: '0.35rem' }}>
                  <Link href={`/crm/staff/${s.id}`} className="nav-link">
                    {s.name}
                  </Link>{' '}
                  <span className="muted">
                    {s.internal_code} · {s.job_title || s.department || '—'}
                    {!s.active ? ' · inactive' : ''}
                  </span>
                </li>
              ))}
            </ul>
          </>
        ) : null}

        {tab === 'import' && canEdit ? (
          <form onSubmit={(e) => void onImport(e)}>
            <p className="muted">JSON array of staff rows (name, internal_code, …)</p>
            <textarea
              value={importJson}
              onChange={(e) => setImportJson(e.target.value)}
              rows={8}
              disabled={saving}
              style={{
                width: '100%',
                background: 'var(--bg)',
                border: '1px solid var(--border)',
                borderRadius: 8,
                padding: '0.75rem',
                color: 'var(--text)',
                fontFamily: 'monospace',
                fontSize: '0.85rem',
              }}
            />
            <button type="submit" className="btn btn-secondary btn-sm" disabled={saving} style={{ marginTop: '0.5rem' }}>
              Import
            </button>
          </form>
        ) : null}

        {tab === 'levels' ? (
          <form onSubmit={(e) => void onSaveLevels(e)}>
            <textarea
              value={levelsJson}
              onChange={(e) => setLevelsJson(e.target.value)}
              rows={10}
              readOnly={!canEdit}
              style={{
                width: '100%',
                background: 'var(--bg)',
                border: '1px solid var(--border)',
                borderRadius: 8,
                padding: '0.75rem',
                color: 'var(--text)',
                fontFamily: 'monospace',
                fontSize: '0.85rem',
              }}
            />
            {canEdit ? (
              <button type="submit" className="btn btn-secondary btn-sm" disabled={saving} style={{ marginTop: '0.5rem' }}>
                Lưu levels
              </button>
            ) : null}
          </form>
        ) : null}

        {tab === 'competency' ? (
          <form onSubmit={(e) => void onSaveCompetency(e)}>
            <textarea
              value={competencyJson}
              onChange={(e) => setCompetencyJson(e.target.value)}
              rows={10}
              readOnly={!canEdit}
              style={{
                width: '100%',
                background: 'var(--bg)',
                border: '1px solid var(--border)',
                borderRadius: 8,
                padding: '0.75rem',
                color: 'var(--text)',
                fontFamily: 'monospace',
                fontSize: '0.85rem',
              }}
            />
            {canEdit ? (
              <button
                type="submit"
                className="btn btn-secondary btn-sm"
                disabled={saving}
                style={{ marginTop: '0.5rem' }}
              >
                Lưu competency
              </button>
            ) : null}
          </form>
        ) : null}
      </div>
    </main>
  );
}
