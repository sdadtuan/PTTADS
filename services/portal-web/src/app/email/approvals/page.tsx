'use client';

import { useCallback, useEffect, useState } from 'react';
import { useRouter } from 'next/navigation';
import { PortalNav } from '@/components/PortalNav';
import { EmailApprovalCard } from '@/components/email/EmailApprovalCard';
import {
  portalEmailApproveCampaign,
  portalEmailPendingApprovals,
  portalEmailRejectCampaign,
  portalMe,
  type PortalEmailApprovalRow,
} from '@/lib/api';
import { clearSession, getStoredUser, getToken, type StoredUser } from '@/lib/auth';

export default function PortalEmailApprovalsPage() {
  const router = useRouter();
  const [user, setUser] = useState<StoredUser | null>(null);
  const [items, setItems] = useState<PortalEmailApprovalRow[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');

  const load = useCallback(async (token: string) => {
    setLoading(true);
    setError('');
    try {
      const data = await portalEmailPendingApprovals(token);
      setItems(data.items);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Tải approvals thất bại');
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
    if (cached) setUser(cached);
    portalMe(token)
      .then((me) => {
        setUser(me);
        return load(token);
      })
      .catch(() => {
        clearSession();
        router.replace('/login');
      });
  }, [router, load]);

  async function approve(campaignId: string) {
    const token = getToken();
    if (!token) throw new Error('Unauthorized');
    await portalEmailApproveCampaign(token, campaignId);
    await load(token);
  }

  async function reject(campaignId: string, note: string) {
    const token = getToken();
    if (!token) throw new Error('Unauthorized');
    await portalEmailRejectCampaign(token, campaignId, note);
    await load(token);
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

  const isApprover = user.role === 'approver';

  return (
    <main style={{ maxWidth: 900, margin: '0 auto', padding: '1.5rem' }}>
      <PortalNav user={user} onLogout={logout} />
      <div className="card" style={{ marginBottom: '1rem' }}>
        <p className="muted" style={{ marginTop: 0 }}>EM-8b P-EMAIL-02 — Approval inbox</p>
        {!isApprover ? (
          <p className="muted">Chỉ role <strong>approver</strong> mới phê duyệt campaign.</p>
        ) : null}
      </div>
      {error ? <p className="error">{error}</p> : null}
      {loading ? (
        <p className="muted">Đang tải…</p>
      ) : items.length === 0 ? (
        <div className="card">
          <p className="muted">Không có campaign chờ duyệt.</p>
        </div>
      ) : (
        <div className="email-approval-list">
          {items.map((item) => (
            <EmailApprovalCard
              key={item.campaign_id}
              item={item}
              canAct={isApprover}
              onApprove={approve}
              onReject={reject}
            />
          ))}
        </div>
      )}
    </main>
  );
}
