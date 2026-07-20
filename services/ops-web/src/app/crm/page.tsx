'use client';

import Link from 'next/link';
import { useCallback, useEffect, useState } from 'react';
import { useRouter } from 'next/navigation';
import { OpsNav } from '@/components/OpsNav';
import { fetchCrmBoard, staffMe, staffRefresh, type CrmBoardModuleCard } from '@/lib/api';
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

export default function CrmBoardPage() {
  const router = useRouter();
  const [user, setUser] = useState<StoredStaffUser | null>(null);
  const [modules, setModules] = useState<CrmBoardModuleCard[]>([]);
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
      const allowed =
        hasCap(me, 'crm_board', 'view') ||
        hasCap(me, 'crm_leads', 'view') ||
        hasCap(me, 'crm_board_customers', 'view');
      if (!allowed) {
        setError('Không có quyền CRM Board');
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
        const board = await fetchCrmBoard(access);
        setModules(board.modules ?? []);
      } catch (err) {
        setError(err instanceof Error ? err.message : 'Không tải được CRM board');
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
    <main style={{ maxWidth: 1100, margin: '0 auto', padding: '1.5rem' }}>
      <OpsNav user={user} onLogout={logout} />
      <div className="card">
        <h2 style={{ marginTop: 0, fontSize: '1.1rem' }}>CRM Board</h2>
        <p className="muted" style={{ marginBottom: '1rem' }}>
          Hub điều hướng module CRM theo quyền của bạn (Wave 7 — thay Flask /crm).
        </p>
        {error ? <p className="error-text">{error}</p> : null}
        {loading ? <p className="muted">Đang tải module…</p> : null}
        {!loading && modules.length === 0 && !error ? (
          <p className="muted">Chưa có module nào khả dụng với quyền hiện tại.</p>
        ) : null}
        <div className="summary-grid">
          {modules.map((mod) => (
            <Link key={mod.id} href={mod.href} className="summary-card" style={{ textDecoration: 'none' }}>
              <span className="muted">{mod.description}</span>
              <strong>{mod.label}</strong>
            </Link>
          ))}
        </div>
      </div>
    </main>
  );
}
