'use client';

import { useCallback, useEffect, useState } from 'react';
import { useRouter } from 'next/navigation';
import { OpsNav } from '@/components/OpsNav';
import { fetchCrmStaffList, fetchStaffKpiAutoMetrics, staffMe, staffRefresh } from '@/lib/api';
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

export default function CrmStaffKpiPage() {
  const router = useRouter();
  const [user, setUser] = useState<StoredStaffUser | null>(null);
  const [staffOptions, setStaffOptions] = useState<Array<{ id: number; name: string }>>([]);
  const [staffId, setStaffId] = useState('');
  const [role, setRole] = useState('am');
  const [metrics, setMetrics] = useState<Array<{ key: string; label: string; value: number; target?: number }>>([]);
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(false);

  const now = new Date();
  const year = now.getFullYear();
  const month = now.getMonth() + 1;

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
      if (!hasCap(me, 'crm_staff_kpi_am_sp', 'view')) {
        setError('Không có quyền KPI AM/SP');
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
      try {
        const out = await fetchCrmStaffList(access);
        const opts = (out.staff ?? []).map((s) => ({ id: s.id, name: s.name }));
        setStaffOptions(opts);
        if (opts[0]) setStaffId(String(opts[0].id));
      } catch (err) {
        setError(err instanceof Error ? err.message : 'Tải thất bại');
      } finally {
        setLoading(false);
      }
    })();
  }, [ensureAuth]);

  async function loadMetrics() {
    const access = getAccessToken();
    if (!access || !staffId) return;
    setLoading(true);
    setError('');
    try {
      const out = await fetchStaffKpiAutoMetrics(access, Number(staffId), { role, year, month });
      setMetrics((out.metrics as typeof metrics) ?? []);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Tải metrics thất bại');
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    if (staffId) void loadMetrics();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [staffId, role]);

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
        <h2 style={{ marginTop: 0, fontSize: '1.15rem' }}>KPI AM / SP</h2>
        {error ? <p className="error">{error}</p> : null}
        <div style={{ display: 'flex', gap: '0.5rem', flexWrap: 'wrap', marginBottom: '1rem' }}>
          <select
            value={staffId}
            onChange={(e) => setStaffId(e.target.value)}
            style={{
              background: 'var(--bg)',
              border: '1px solid var(--border)',
              borderRadius: 8,
              padding: '0.55rem 0.75rem',
              color: 'var(--text)',
            }}
          >
            {staffOptions.map((s) => (
              <option key={s.id} value={String(s.id)}>
                {s.name}
              </option>
            ))}
          </select>
          <select
            value={role}
            onChange={(e) => setRole(e.target.value)}
            style={{
              background: 'var(--bg)',
              border: '1px solid var(--border)',
              borderRadius: 8,
              padding: '0.55rem 0.75rem',
              color: 'var(--text)',
            }}
          >
            <option value="am">AM</option>
            <option value="sp">SP</option>
          </select>
          <span className="muted">
            {month}/{year}
          </span>
        </div>
        {loading ? <p className="muted">Đang tải…</p> : null}
        {metrics.length === 0 && !loading ? <p className="muted">Chưa có số liệu.</p> : null}
        <ul style={{ margin: 0, paddingLeft: '1.1rem' }}>
          {metrics.map((m) => (
            <li key={m.key}>
              {m.label}: {m.value}
              {m.target != null ? ` / ${m.target}` : ''}
            </li>
          ))}
        </ul>
      </div>
    </main>
  );
}
