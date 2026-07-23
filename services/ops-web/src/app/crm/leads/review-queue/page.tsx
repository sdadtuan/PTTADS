'use client';

import Link from 'next/link';
import { useCallback, useEffect, useState } from 'react';
import { useRouter } from 'next/navigation';
import { OpsNav } from '@/components/OpsNav';
import {
  fetchReviewQueueLeads,
  releaseLeadReviewQueue,
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

export default function CrmReviewQueuePage() {
  const router = useRouter();
  const [user, setUser] = useState<StoredStaffUser | null>(null);
  const [rows, setRows] = useState<
    Array<{ id: number; full_name: string; phone: string; review_queue: { message?: string } }>
  >([]);
  const [error, setError] = useState('');
  const [message, setMessage] = useState('');
  const [loading, setLoading] = useState(true);

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
      if (!hasCap(me, 'crm_leads', 'assign')) {
        setError('Chỉ GDKD / Sales Lead (cap assign) mới xem inbox Phải tra soát');
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

  const reload = useCallback(async (access: string) => {
    const out = await fetchReviewQueueLeads(access);
    setRows(out.leads ?? []);
  }, []);

  useEffect(() => {
    void (async () => {
      const access = await ensureAuth();
      if (!access) {
        setLoading(false);
        return;
      }
      try {
        await reload(access);
      } catch (err) {
        setError(err instanceof Error ? err.message : 'Tải inbox thất bại');
      } finally {
        setLoading(false);
      }
    })();
  }, [ensureAuth, reload]);

  function logout() {
    clearSession();
    router.replace('/login');
  }

  async function onRelease(leadId: number) {
    const access = getAccessToken();
    if (!access) return;
    setError('');
    setMessage('');
    try {
      await releaseLeadReviewQueue(access, leadId, { mode: 'auto', note: 'GDKD release ops-web' });
      setMessage(`Đã release lead #${leadId}`);
      await reload(access);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Release thất bại');
    }
  }

  return (
    <>
      <OpsNav user={user} onLogout={logout} />
      <main className="page">
        <h1>Inbox Phải tra soát (B2)</h1>
        <p className="muted">Lead quá hạn 24h chưa Liên hệ OK — FR-CRM-04</p>
        {error && <p className="error">{error}</p>}
        {message && <p className="success">{message}</p>}
        {loading ? (
          <p>Đang tải…</p>
        ) : rows.length === 0 ? (
          <p className="muted">Không có lead trong review queue.</p>
        ) : (
          <table className="data-table">
            <thead>
              <tr>
                <th>Lead</th>
                <th>Điện thoại</th>
                <th>Lý do</th>
                <th />
              </tr>
            </thead>
            <tbody>
              {rows.map((row) => (
                <tr key={row.id}>
                  <td>
                    <Link href={`/crm/leads/${row.id}`}>{row.full_name || `#${row.id}`}</Link>
                  </td>
                  <td>{row.phone || '—'}</td>
                  <td style={{ maxWidth: 320 }}>{row.review_queue.message || '—'}</td>
                  <td>
                    <button type="button" className="btn btn-sm" onClick={() => void onRelease(row.id)}>
                      Release
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </main>
    </>
  );
}
