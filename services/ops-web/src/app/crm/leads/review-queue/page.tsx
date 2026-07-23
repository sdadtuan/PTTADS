'use client';

import Link from 'next/link';
import { useCallback, useEffect, useState } from 'react';
import { useRouter } from 'next/navigation';
import { OpsNav } from '@/components/OpsNav';
import {
  fetchCrmStaffList,
  fetchReviewQueueLeads,
  releaseLeadReviewQueue,
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

type ReviewRow = {
  id: number;
  full_name: string;
  phone: string;
  review_queue: { message?: string };
};

export default function CrmReviewQueuePage() {
  const router = useRouter();
  const [user, setUser] = useState<StoredStaffUser | null>(null);
  const [rows, setRows] = useState<ReviewRow[]>([]);
  const [staffList, setStaffList] = useState<CrmStaffRow[]>([]);
  const [error, setError] = useState('');
  const [message, setMessage] = useState('');
  const [loading, setLoading] = useState(true);
  const [releaseLeadId, setReleaseLeadId] = useState<number | null>(null);
  const [releaseMode, setReleaseMode] = useState<'auto' | 'manual'>('auto');
  const [releaseOwnerId, setReleaseOwnerId] = useState('');
  const [releaseNote, setReleaseNote] = useState('GDKD release ops-web');
  const [releasing, setReleasing] = useState(false);

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
    const [queueOut, staffOut] = await Promise.all([
      fetchReviewQueueLeads(access),
      fetchCrmStaffList(access),
    ]);
    setRows(queueOut.leads ?? []);
    setStaffList(staffOut.staff ?? []);
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

  function openReleaseModal(leadId: number) {
    setReleaseLeadId(leadId);
    setReleaseMode('auto');
    setReleaseOwnerId('');
    setReleaseNote('GDKD release ops-web');
    setError('');
  }

  function closeReleaseModal() {
    setReleaseLeadId(null);
  }

  async function submitRelease() {
    const access = getAccessToken();
    if (!access || releaseLeadId == null) return;
    setReleasing(true);
    setError('');
    setMessage('');
    try {
      const body: { mode: 'auto' | 'manual'; owner_id?: number; note?: string } = {
        mode: releaseMode,
        note: releaseNote.trim() || undefined,
      };
      if (releaseMode === 'manual') {
        const ownerId = Number(releaseOwnerId);
        if (!Number.isFinite(ownerId) || ownerId <= 0) {
          setError('Chọn AM để gán lại (manual).');
          return;
        }
        body.owner_id = ownerId;
      }
      await releaseLeadReviewQueue(access, releaseLeadId, body);
      setMessage(`Đã release lead #${releaseLeadId}`);
      closeReleaseModal();
      await reload(access);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Release thất bại');
    } finally {
      setReleasing(false);
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
                    <button type="button" className="btn btn-sm" onClick={() => openReleaseModal(row.id)}>
                      Release…
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}

        {releaseLeadId != null && (
          <div
            className="email-modal-backdrop"
            role="dialog"
            aria-modal="true"
            style={{ position: 'fixed', inset: 0, background: 'rgba(0,0,0,0.45)', zIndex: 50 }}
          >
            <div className="card stack-gap" style={{ maxWidth: 420, margin: '2rem auto', padding: '1.25rem' }}>
              <h2 style={{ margin: 0, fontSize: '1.1rem' }}>Release lead #{releaseLeadId}</h2>
              <label>
                Chế độ
                <select
                  value={releaseMode}
                  onChange={(e) => setReleaseMode(e.target.value as 'auto' | 'manual')}
                  style={{ display: 'block', width: '100%', marginTop: '0.25rem' }}
                >
                  <option value="auto">Auto — gán lại AM trước đó</option>
                  <option value="manual">Manual — chọn AM</option>
                </select>
              </label>
              {releaseMode === 'manual' && (
                <label>
                  AM mới
                  <select
                    value={releaseOwnerId}
                    onChange={(e) => setReleaseOwnerId(e.target.value)}
                    style={{ display: 'block', width: '100%', marginTop: '0.25rem' }}
                  >
                    <option value="">— Chọn AM —</option>
                    {staffList.map((s) => (
                      <option key={s.id} value={String(s.id)}>
                        {s.name || s.internal_code || `#${s.id}`}
                      </option>
                    ))}
                  </select>
                </label>
              )}
              <label>
                Ghi chú
                <input
                  type="text"
                  value={releaseNote}
                  onChange={(e) => setReleaseNote(e.target.value)}
                  style={{ width: '100%', marginTop: '0.25rem' }}
                />
              </label>
              <div style={{ display: 'flex', gap: '0.5rem', justifyContent: 'flex-end' }}>
                <button type="button" className="btn btn-sm" disabled={releasing} onClick={closeReleaseModal}>
                  Huỷ
                </button>
                <button type="button" className="btn btn-primary btn-sm" disabled={releasing} onClick={() => void submitRelease()}>
                  Release
                </button>
              </div>
            </div>
          </div>
        )}
      </main>
    </>
  );
}
