'use client';

import Link from 'next/link';
import { useCallback, useEffect, useState } from 'react';
import { useParams, useRouter } from 'next/navigation';
import { PortalNav } from '@/components/PortalNav';
import { portalEmailCampaignStats, portalMe, type PortalEmailCampaignStats } from '@/lib/api';
import { clearSession, getStoredUser, getToken, type StoredUser } from '@/lib/auth';

export default function PortalEmailCampaignStatsPage() {
  const router = useRouter();
  const params = useParams();
  const campaignId = String(params.id ?? '');
  const [user, setUser] = useState<StoredUser | null>(null);
  const [stats, setStats] = useState<PortalEmailCampaignStats | null>(null);
  const [error, setError] = useState('');

  const load = useCallback(
    async (token: string) => {
      setError('');
      try {
        setStats(await portalEmailCampaignStats(token, campaignId));
      } catch (err) {
        setError(err instanceof Error ? err.message : 'Tải stats thất bại');
      }
    },
    [campaignId],
  );

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
    <main style={{ maxWidth: 900, margin: '0 auto', padding: '1.5rem' }}>
      <PortalNav user={user} onLogout={logout} />
      <div className="card" style={{ marginBottom: '1rem' }}>
        <p className="muted" style={{ marginTop: 0 }}>EM-4 P-EMAIL-03 — Campaign performance</p>
        <Link href="/email" className="btn btn-secondary btn-sm">← Email dashboard</Link>
      </div>
      {error ? <p className="error">{error}</p> : null}
      {stats ? (
        <div className="card">
          <h2 style={{ marginTop: 0 }}>{stats.campaign_name}</h2>
          <p className="muted">Status: {stats.status}</p>
          <div
            style={{
              display: 'grid',
              gridTemplateColumns: 'repeat(auto-fill, minmax(120px, 1fr))',
              gap: '1rem',
              marginTop: '1rem',
            }}
          >
            <div><p className="muted" style={{ margin: 0 }}>Audience</p><strong>{stats.audience_count ?? '—'}</strong></div>
            <div><p className="muted" style={{ margin: 0 }}>Sent</p><strong>{stats.sent}</strong></div>
            <div><p className="muted" style={{ margin: 0 }}>Opens</p><strong>{stats.opens}</strong></div>
            <div><p className="muted" style={{ margin: 0 }}>Clicks</p><strong>{stats.clicks}</strong></div>
            <div><p className="muted" style={{ margin: 0 }}>Open rate</p><strong>{stats.open_rate_pct}%</strong></div>
            <div><p className="muted" style={{ margin: 0 }}>Click rate</p><strong>{stats.click_rate_pct}%</strong></div>
            <div><p className="muted" style={{ margin: 0 }}>Revenue</p><strong>{stats.revenue_attrib}</strong></div>
          </div>
        </div>
      ) : null}
    </main>
  );
}
