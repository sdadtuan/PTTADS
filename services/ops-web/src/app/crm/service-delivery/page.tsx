'use client';

import Link from 'next/link';
import { useCallback, useEffect, useState } from 'react';
import { useRouter } from 'next/navigation';
import { OpsNav } from '@/components/OpsNav';
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

  useEffect(() => {
    void (async () => {
      const access = await ensureAuth();
      if (!access) return;
      setLoading(true);
      setError('');
      try {
        const data = await fetchServiceLifecycles(access, { include_draft: true });
        setRows(data);
      } catch (err) {
        setError(err instanceof Error ? err.message : 'Tải lifecycle thất bại');
      } finally {
        setLoading(false);
      }
    })();
  }, [ensureAuth]);

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
        <h2 style={{ marginTop: 0, fontSize: '1.15rem' }}>Service Delivery</h2>
        {loading ? <p className="muted">Đang tải…</p> : null}
        {error ? <p className="error">{error}</p> : null}
        {rows.length === 0 && !loading ? <p className="muted">Chưa có lifecycle.</p> : null}
        <ul style={{ margin: 0, paddingLeft: '1.1rem' }}>
          {rows.map((lc) => (
            <li key={lc.id} style={{ marginBottom: '0.35rem' }}>
              <Link href={`/crm/service-delivery/${lc.id}`} className="nav-link">
                #{lc.id} · {lc.service_slug}
              </Link>{' '}
              <span className="muted">
                {lc.stage} / {lc.status}
                {lc.customer_id ? ` · KH #${lc.customer_id}` : ''}
                {lc.lead_id ? ` · Lead #${lc.lead_id}` : ''}
              </span>
            </li>
          ))}
        </ul>
      </div>
    </main>
  );
}
