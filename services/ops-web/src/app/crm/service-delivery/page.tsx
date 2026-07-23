'use client';

import { useCallback, useEffect, useState } from 'react';
import { useRouter } from 'next/navigation';
import { OpsNav } from '@/components/OpsNav';
import { ServiceDeliveryKanban } from '@/components/ServiceDeliveryKanban';
import { fetchServiceLifecycles, staffMe, staffRefresh, type ServiceLifecycleRow } from '@/lib/api';
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

export default function CrmServiceDeliveryPage() {
  const router = useRouter();
  const [user, setUser] = useState<StoredStaffUser | null>(null);
  const [rows, setRows] = useState<ServiceLifecycleRow[]>([]);
  const [funnelStats, setFunnelStats] = useState<Record<string, number>>({});
  const [filterSlug, setFilterSlug] = useState('');
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(false);

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
        setError('Không có quyền service delivery');
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

  const load = useCallback(async () => {
    const access = await ensureAuth();
    if (!access) return;
    setLoading(true);
    setError('');
    try {
      const data = await fetchServiceLifecycles(access, {
        include_draft: true,
        service_slug: filterSlug || undefined,
      });
      setRows(data.lifecycles ?? []);
      setFunnelStats(data.funnel_stats ?? {});
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Tải lifecycle thất bại');
    } finally {
      setLoading(false);
    }
  }, [ensureAuth, filterSlug]);

  useEffect(() => {
    void load();
  }, [load]);

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
    <main style={{ maxWidth: 1200, margin: '0 auto', padding: '1.5rem' }}>
      <OpsNav user={user} onLogout={logout} />
      <div className="card">
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', gap: '0.75rem', flexWrap: 'wrap' }}>
          <h2 style={{ margin: 0, fontSize: '1.15rem' }}>Service Delivery — Kanban</h2>
          <input
            placeholder="Lọc service_slug…"
            value={filterSlug}
            onChange={(e) => setFilterSlug(e.target.value)}
            onBlur={() => void load()}
            style={{
              background: 'var(--bg)',
              border: '1px solid var(--border)',
              borderRadius: 8,
              padding: '0.45rem 0.65rem',
              color: 'var(--text)',
              minWidth: 200,
            }}
          />
        </div>
        {loading ? <p className="muted">Đang tải…</p> : null}
        {error ? <p className="error">{error}</p> : null}
        {!loading && rows.length === 0 ? <p className="muted">Chưa có lifecycle.</p> : null}
        {!loading && rows.length > 0 ? <ServiceDeliveryKanban rows={rows} funnelStats={funnelStats} /> : null}
      </div>
    </main>
  );
}
