'use client';

import Link from 'next/link';
import { useCallback, useEffect, useState } from 'react';
import { useRouter } from 'next/navigation';
import { OpsNav } from '@/components/OpsNav';
import {
  createMarketingPlan,
  fetchMarketingPlans,
  staffMe,
  staffRefresh,
  type MarketingPlanRow,
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

export default function CrmMarketingPlanPage() {
  const router = useRouter();
  const [user, setUser] = useState<StoredStaffUser | null>(null);
  const [rows, setRows] = useState<MarketingPlanRow[]>([]);
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
      if (!hasCap(me, 'crm_board', 'view')) {
        setError('Không có quyền xem kế hoạch marketing');
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

  const load = useCallback(
    async (access: string) => {
      const data = await fetchMarketingPlans(access, { q: query || undefined });
      setRows(data);
    },
    [query],
  );

  useEffect(() => {
    void (async () => {
      const access = await ensureAuth();
      if (!access) return;
      setLoading(true);
      setError('');
      try {
        await load(access);
      } catch (err) {
        setError(err instanceof Error ? err.message : 'Tải kế hoạch thất bại');
      } finally {
        setLoading(false);
      }
    })();
  }, [ensureAuth, load]);

  async function onCreate(e: React.FormEvent) {
    e.preventDefault();
    if (!user || !newName.trim()) return;
    const access = getAccessToken();
    if (!access) return;
    setSaving(true);
    setError('');
    try {
      await createMarketingPlan(access, { name: newName.trim() });
      setNewName('');
      await load(access);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Tạo kế hoạch thất bại');
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
        <h2 style={{ marginTop: 0, fontSize: '1.15rem' }}>Kế hoạch Marketing</h2>
        <form
          onSubmit={(e) => {
            e.preventDefault();
            setQuery(q.trim());
          }}
          style={{ display: 'flex', gap: '0.5rem', marginBottom: '1rem', flexWrap: 'wrap' }}
        >
          <input
            value={q}
            onChange={(e) => setQ(e.target.value)}
            placeholder="Tìm tên / mã / kỳ…"
            style={{
              flex: 1,
              minWidth: 180,
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
        {rows.length === 0 && !loading ? <p className="muted">Chưa có kế hoạch.</p> : null}
        <ul style={{ margin: 0, paddingLeft: '1.1rem' }}>
          {rows.map((p) => (
            <li key={p.id} style={{ marginBottom: '0.35rem' }}>
              <Link href={`/crm/marketing-plan/${p.id}`} className="nav-link">
                #{p.id} · {p.name}
              </Link>{' '}
              <span className="muted">
                {p.status} · FY{p.fiscal_year}
                {p.milestone_total != null ? ` · MS ${p.milestone_done ?? 0}/${p.milestone_total}` : ''}
              </span>
            </li>
          ))}
        </ul>
        {hasCap(user, 'crm_board', 'edit') ? (
          <form onSubmit={(e) => void onCreate(e)} style={{ display: 'flex', gap: '0.5rem', marginTop: '1rem' }}>
            <input
              value={newName}
              onChange={(e) => setNewName(e.target.value)}
              placeholder="Tên kế hoạch mới"
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
              + Tạo
            </button>
          </form>
        ) : null}
      </div>
    </main>
  );
}
