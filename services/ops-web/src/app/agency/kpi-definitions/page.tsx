'use client';

import Link from 'next/link';
import { useCallback, useEffect, useState } from 'react';
import { useRouter } from 'next/navigation';
import { OpsNav } from '@/components/OpsNav';
import { AgencyReadOnlyBadge, canAgencyWrite } from '@/components/AgencyReadOnlyBadge';
import {
  createKpiDefinition,
  deleteKpiDefinition,
  fetchKpiDefinitions,
  staffMe,
  staffRefresh,
  updateKpiDefinition,
} from '@/lib/api';
import type { KpiDefinition } from '@/lib/api';
import {
  clearSession,
  getAccessToken,
  getRefreshToken,
  hasCap,
  updateAccessToken,
  updateStoredUser,
  type StoredStaffUser,
} from '@/lib/auth';

export default function AgencyKpiDefinitionsPage() {
  const router = useRouter();
  const [user, setUser] = useState<StoredStaffUser | null>(null);
  const [rows, setRows] = useState<KpiDefinition[]>([]);
  const [error, setError] = useState('');
  const [msg, setMsg] = useState('');
  const [busy, setBusy] = useState(false);
  const [form, setForm] = useState({
    code: '',
    name: '',
    formula: '',
    granularity: 'daily',
    description: '',
  });
  const [editCode, setEditCode] = useState<string | null>(null);
  const [editForm, setEditForm] = useState({
    name: '',
    formula: '',
    granularity: '',
    description: '',
  });

  const canWrite = canAgencyWrite(user);

  const ensureAuth = useCallback(async (): Promise<string | null> => {
    let access = getAccessToken();
    if (!access) {
      router.replace('/login');
      return null;
    }
    try {
      const me = await staffMe(access);
      setUser(me);
      updateStoredUser(me);
      if (!hasCap(me, 'crm_agency', 'view')) return null;
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
      return out.access_token;
    }
  }, [router]);

  const reload = useCallback(async (access: string) => {
    const data = await fetchKpiDefinitions(access);
    setRows(data.definitions);
  }, []);

  useEffect(() => {
    void (async () => {
      const access = await ensureAuth();
      if (!access) return;
      try {
        await reload(access);
      } catch (err) {
        setError(err instanceof Error ? err.message : 'Tải KPI definitions thất bại');
      }
    })();
  }, [ensureAuth, reload]);

  async function handleCreate(e: React.FormEvent) {
    e.preventDefault();
    const access = getAccessToken();
    if (!access || !canWrite) return;
    setBusy(true);
    setError('');
    setMsg('');
    try {
      await createKpiDefinition(access, form);
      setForm({ code: '', name: '', formula: '', granularity: 'daily', description: '' });
      await reload(access);
      setMsg('Đã tạo KPI definition');
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Tạo KPI thất bại');
    } finally {
      setBusy(false);
    }
  }

  function startEdit(row: KpiDefinition) {
    setEditCode(row.code);
    setEditForm({
      name: row.name ?? '',
      formula: row.formula ?? '',
      granularity: row.granularity ?? '',
      description: row.description ?? '',
    });
  }

  async function handleUpdate(e: React.FormEvent) {
    e.preventDefault();
    const access = getAccessToken();
    if (!access || !canWrite || !editCode) return;
    setBusy(true);
    setError('');
    setMsg('');
    try {
      await updateKpiDefinition(access, editCode, editForm);
      setEditCode(null);
      await reload(access);
      setMsg('Đã cập nhật KPI');
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Cập nhật KPI thất bại');
    } finally {
      setBusy(false);
    }
  }

  async function handleDelete(code: string) {
    const access = getAccessToken();
    if (!access || !canWrite) return;
    if (!window.confirm(`Xóa KPI ${code}?`)) return;
    setBusy(true);
    setError('');
    setMsg('');
    try {
      await deleteKpiDefinition(access, code);
      if (editCode === code) setEditCode(null);
      await reload(access);
      setMsg('Đã xóa KPI');
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Xóa KPI thất bại');
    } finally {
      setBusy(false);
    }
  }

  if (!user) {
    return (
      <main style={{ padding: '2rem' }}>
        <p className="muted">Đang tải…</p>
      </main>
    );
  }

  return (
    <main style={{ maxWidth: 1100, margin: '0 auto', padding: '1.5rem' }}>
      <OpsNav user={user} onLogout={() => { clearSession(); router.push('/login'); }} />
      <p style={{ margin: '0 0 1rem' }}>
        <Link href="/agency" className="nav-link">
          ← Agency
        </Link>
      </p>

      <div className="card">
        <div style={{ display: 'flex', flexWrap: 'wrap', gap: '0.75rem', alignItems: 'center', marginBottom: '0.5rem' }}>
          <h2 style={{ margin: 0, flex: '1 1 auto' }}>Định nghĩa KPI</h2>
          <AgencyReadOnlyBadge user={user} />
        </div>
        <p className="muted">Dictionary KPI · admin có thể thêm/sửa/xóa definition</p>
        {error ? <p className="error">{error}</p> : null}
        {msg ? <p className="muted">{msg}</p> : null}

        {canWrite ? (
          <form
            onSubmit={(e) => void handleCreate(e)}
            style={{ display: 'grid', gap: '0.75rem', maxWidth: 640, marginBottom: '1.5rem' }}
          >
            <h3 style={{ fontSize: '1rem', margin: 0 }}>Thêm KPI</h3>
            <input
              placeholder="code (snake_case)"
              value={form.code}
              onChange={(e) => setForm({ ...form, code: e.target.value })}
              required
              style={{ padding: '0.5rem' }}
            />
            <input
              placeholder="Tên"
              value={form.name}
              onChange={(e) => setForm({ ...form, name: e.target.value })}
              required
              style={{ padding: '0.5rem' }}
            />
            <input
              placeholder="Công thức"
              value={form.formula}
              onChange={(e) => setForm({ ...form, formula: e.target.value })}
              required
              style={{ padding: '0.5rem' }}
            />
            <input
              placeholder="Granularity"
              value={form.granularity}
              onChange={(e) => setForm({ ...form, granularity: e.target.value })}
              style={{ padding: '0.5rem' }}
            />
            <textarea
              placeholder="Mô tả"
              value={form.description}
              onChange={(e) => setForm({ ...form, description: e.target.value })}
              rows={2}
              style={{ padding: '0.5rem' }}
            />
            <button type="submit" className="btn btn-sm" disabled={busy}>
              Tạo KPI
            </button>
          </form>
        ) : null}

        {editCode && canWrite ? (
          <form
            onSubmit={(e) => void handleUpdate(e)}
            style={{ display: 'grid', gap: '0.75rem', maxWidth: 640, marginBottom: '1.5rem' }}
          >
            <h3 style={{ fontSize: '1rem', margin: 0 }}>Sửa KPI: {editCode}</h3>
            <input
              placeholder="Tên"
              value={editForm.name}
              onChange={(e) => setEditForm({ ...editForm, name: e.target.value })}
              required
              style={{ padding: '0.5rem' }}
            />
            <input
              placeholder="Công thức"
              value={editForm.formula}
              onChange={(e) => setEditForm({ ...editForm, formula: e.target.value })}
              required
              style={{ padding: '0.5rem' }}
            />
            <input
              placeholder="Granularity"
              value={editForm.granularity}
              onChange={(e) => setEditForm({ ...editForm, granularity: e.target.value })}
              style={{ padding: '0.5rem' }}
            />
            <textarea
              placeholder="Mô tả"
              value={editForm.description}
              onChange={(e) => setEditForm({ ...editForm, description: e.target.value })}
              rows={2}
              style={{ padding: '0.5rem' }}
            />
            <div style={{ display: 'flex', gap: '0.5rem' }}>
              <button type="submit" className="btn btn-sm" disabled={busy}>
                Lưu
              </button>
              <button type="button" className="btn btn-secondary btn-sm" onClick={() => setEditCode(null)}>
                Hủy
              </button>
            </div>
          </form>
        ) : null}

        <div style={{ overflowX: 'auto' }}>
          <table className="perf-table">
            <thead>
              <tr>
                <th>Code</th>
                <th>Tên</th>
                <th>Công thức</th>
                <th>Granularity</th>
                <th>Mô tả</th>
                {canWrite ? <th /> : null}
              </tr>
            </thead>
            <tbody>
              {rows.map((r) => (
                <tr key={r.code}>
                  <td><code>{r.code}</code></td>
                  <td>{r.name}</td>
                  <td><code>{r.formula}</code></td>
                  <td>{r.granularity ?? '—'}</td>
                  <td>{r.description ?? '—'}</td>
                  {canWrite ? (
                    <td style={{ whiteSpace: 'nowrap' }}>
                      <button type="button" className="btn btn-secondary btn-sm" disabled={busy} onClick={() => startEdit(r)}>
                        Sửa
                      </button>{' '}
                      <button type="button" className="btn btn-secondary btn-sm" disabled={busy} onClick={() => void handleDelete(r.code)}>
                        Xóa
                      </button>
                    </td>
                  ) : null}
                </tr>
              ))}
              {rows.length === 0 ? (
                <tr>
                  <td colSpan={canWrite ? 6 : 5} className="muted">
                    Chưa seed kpi_definitions — chạy ./scripts/seed_kpi_definitions.sh
                  </td>
                </tr>
              ) : null}
            </tbody>
          </table>
        </div>
      </div>
    </main>
  );
}
