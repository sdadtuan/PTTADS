'use client';

import { useCallback, useEffect, useState } from 'react';
import { useRouter } from 'next/navigation';
import { OpsNav } from '@/components/OpsNav';
import {
  exportOwnerWeekly,
  fetchOwnerWeeklyConfig,
  fetchOwnerWeeklyDashboard,
  patchOwnerWeeklyConfig,
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

export default function CrmOwnerWeeklyPage() {
  const router = useRouter();
  const now = new Date();
  const [user, setUser] = useState<StoredStaffUser | null>(null);
  const [year, setYear] = useState(now.getFullYear());
  const [week, setWeek] = useState(1);
  const [dashboard, setDashboard] = useState<Record<string, unknown> | null>(null);
  const [config, setConfig] = useState<Record<string, unknown> | null>(null);
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
      if (!hasCap(me, 'crm_owner_weekly_dashboard', 'view')) {
        setError('Không có quyền Owner Weekly');
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

  const loadData = useCallback(
    async (access: string) => {
      setLoading(true);
      setError('');
      try {
        const dash = await fetchOwnerWeeklyDashboard(access, { year, week, trend_weeks: 8 });
        setDashboard(dash);
        const me = getStoredUser();
        if (me && hasCap(me, 'crm_owner_weekly_dashboard', 'configure')) {
          setConfig(await fetchOwnerWeeklyConfig(access));
        }
      } catch (err) {
        setError(err instanceof Error ? err.message : 'Tải owner weekly thất bại');
      } finally {
        setLoading(false);
      }
    },
    [year, week],
  );

  useEffect(() => {
    void (async () => {
      const access = await ensureAuth();
      if (!access) return;
      await loadData(access);
    })();
  }, [ensureAuth, loadData]);

  async function onExport() {
    const access = getAccessToken();
    if (!access) return;
    setError('');
    try {
      const bundle = await exportOwnerWeekly(access, { year, week });
      const blob = new Blob([JSON.stringify(bundle, null, 2)], { type: 'application/json' });
      const url = URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = `owner-weekly-${year}-W${String(week).padStart(2, '0')}.json`;
      a.click();
      URL.revokeObjectURL(url);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Export thất bại');
    }
  }

  async function onSaveConfig() {
    const access = getAccessToken();
    if (!access || !config) return;
    setSaving(true);
    setError('');
    try {
      const targets = (config.targets ?? {}) as Record<string, unknown>;
      const out = await patchOwnerWeeklyConfig(access, { targets });
      setConfig(out);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Lưu config thất bại');
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

  const blocks = (dashboard?.blocks ?? {}) as Record<string, Record<string, unknown>>;
  const canConfigure = hasCap(user, 'crm_owner_weekly_dashboard', 'configure');
  const canExport =
    hasCap(user, 'crm_owner_weekly_dashboard', 'export') ||
    hasCap(user, 'crm_owner_weekly_dashboard', 'view');

  const blockLabels: Record<string, string> = {
    cash: 'Tiền',
    business: 'Kinh doanh',
    efficiency: 'Hiệu quả',
    risk: 'Rủi ro',
  };

  return (
    <main style={{ maxWidth: 960, margin: '0 auto', padding: '1.5rem' }}>
      <OpsNav user={user} onLogout={logout} />
      <div className="card">
        <h2 style={{ marginTop: 0, fontSize: '1.15rem' }}>Owner Weekly</h2>
        <div style={{ display: 'flex', gap: '0.5rem', flexWrap: 'wrap', marginBottom: '1rem' }}>
          <input
            type="number"
            value={year}
            onChange={(e) => setYear(Number(e.target.value))}
            style={{
              width: 90,
              background: 'var(--bg)',
              border: '1px solid var(--border)',
              borderRadius: 8,
              padding: '0.55rem 0.75rem',
              color: 'var(--text)',
            }}
          />
          <input
            type="number"
            min={1}
            max={53}
            value={week}
            onChange={(e) => setWeek(Number(e.target.value))}
            style={{
              width: 70,
              background: 'var(--bg)',
              border: '1px solid var(--border)',
              borderRadius: 8,
              padding: '0.55rem 0.75rem',
              color: 'var(--text)',
            }}
          />
          {canExport ? (
            <button type="button" className="btn btn-sm btn-secondary" onClick={() => void onExport()}>
              Export JSON
            </button>
          ) : null}
        </div>

        {loading ? <p className="muted">Đang tải…</p> : null}
        {error ? <p className="error">{error}</p> : null}

        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(200px, 1fr))', gap: '0.75rem', marginBottom: '1rem' }}>
          {(['cash', 'business', 'efficiency', 'risk'] as const).map((key) => (
            <div key={key} className="card" style={{ padding: '0.75rem' }}>
              <p style={{ margin: 0, fontWeight: 600 }}>{blockLabels[key]}</p>
              <pre style={{ margin: '0.35rem 0 0', fontSize: '0.75rem', overflow: 'auto' }}>
                {JSON.stringify(blocks[key] ?? {}, null, 2)}
              </pre>
            </div>
          ))}
        </div>

        {dashboard?.rag ? (
          <p className="muted">RAG: {JSON.stringify(dashboard.rag)}</p>
        ) : null}

        {canConfigure && config ? (
          <>
            <h3 style={{ fontSize: '1rem' }}>Cấu hình target</h3>
            <pre
              style={{
                background: 'var(--bg)',
                border: '1px solid var(--border)',
                borderRadius: 8,
                padding: '0.75rem',
                overflow: 'auto',
                fontSize: '0.85rem',
              }}
            >
              {JSON.stringify(config, null, 2)}
            </pre>
            <button
              type="button"
              className="btn btn-sm"
              disabled={saving}
              onClick={() => void onSaveConfig()}
              style={{ marginTop: '0.5rem' }}
            >
              Lưu config
            </button>
          </>
        ) : null}
      </div>
    </main>
  );
}
