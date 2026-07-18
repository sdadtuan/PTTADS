'use client';

import { useCallback, useEffect, useState } from 'react';
import { useRouter } from 'next/navigation';
import { CreativeInbox } from '@/components/CreativeInbox';
import { PortalNav } from '@/components/PortalNav';
import {
  approveCreative,
  fetchPendingCreatives,
  portalMe,
  rejectCreative,
  type CreativeRow,
} from '@/lib/api';
import { clearSession, getStoredUser, getToken, type StoredUser } from '@/lib/auth';

export default function CreativesPage() {
  const router = useRouter();
  const [user, setUser] = useState<StoredUser | null>(null);
  const [rows, setRows] = useState<CreativeRow[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');

  const loadCreatives = useCallback(async (token: string) => {
    setLoading(true);
    setError('');
    try {
      const data = await fetchPendingCreatives(token);
      setRows(data.rows);
    } catch (err) {
      setRows([]);
      setError(err instanceof Error ? err.message : 'Không tải được danh sách creative');
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    const token = getToken();
    const cached = getStoredUser();
    if (!token) {
      router.replace('/login');
      return;
    }
    if (cached) {
      setUser(cached);
    }
    portalMe(token)
      .then((me) => {
        setUser(me);
        return loadCreatives(token);
      })
      .catch(() => {
        clearSession();
        router.replace('/login');
      });
  }, [router, loadCreatives]);

  function logout() {
    clearSession();
    router.push('/login');
  }

  async function handleApprove(id: string) {
    const token = getToken();
    if (!token) return;
    await approveCreative(token, id);
    await loadCreatives(token);
  }

  async function handleReject(id: string, note: string) {
    const token = getToken();
    if (!token) return;
    await rejectCreative(token, id, note);
    await loadCreatives(token);
  }

  if (!user && !error) {
    return (
      <main style={{ padding: '2rem' }}>
        <p className="muted">Đang tải…</p>
      </main>
    );
  }

  return (
    <main style={{ maxWidth: 900, margin: '0 auto', padding: '1.5rem' }}>
      <PortalNav user={user} onLogout={logout} />

      <section className="card">
        {!user || user.role !== 'approver' ? (
          <p className="muted" style={{ marginTop: 0 }}>
            Bạn đang xem ở chế độ viewer — chỉ user <strong>approver</strong> mới duyệt/từ chối.
          </p>
        ) : null}
        {error && <p className="error">{error}</p>}
        {loading ? (
          <p className="muted">Đang tải inbox…</p>
        ) : (
          <CreativeInbox
            rows={rows}
            canApprove={user?.role === 'approver'}
            onApprove={handleApprove}
            onReject={handleReject}
          />
        )}
      </section>
    </main>
  );
}
