'use client';

import Link from 'next/link';
import { useCallback, useEffect, useState } from 'react';
import { useRouter, useSearchParams } from 'next/navigation';
import { OpsNav } from '@/components/OpsNav';
import { AgencyReadOnlyBadge, canAgencyWrite } from '@/components/AgencyReadOnlyBadge';
import { HubCampaignMapsPanel } from '@/components/HubCampaignMapsPanel';
import { ContractApprovalsPanel } from '@/components/ContractApprovalsPanel';
import { staffMe, staffRefresh } from '@/lib/api';
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

type HubTab = 'campaigns' | 'contracts';

export function CrmHubContent() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const clientFilter = searchParams.get('client_id') ?? '';
  const campaignFilter = searchParams.get('campaign_id') ?? '';
  const tabParam = searchParams.get('hub_tab');
  const [hubTab, setHubTab] = useState<HubTab>(tabParam === 'contracts' ? 'contracts' : 'campaigns');

  const [user, setUser] = useState<StoredStaffUser | null>(null);
  const [error, setError] = useState('');
  const [msg, setMsg] = useState('');
  const [accessToken, setAccessToken] = useState('');

  const canWrite = canAgencyWrite(user);

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
      if (!hasCap(me, 'crm_agency', 'view') && !hasCap(me, 'crm_leads', 'assign')) {
        setError('Không có quyền Hub');
        return null;
      }
      setAccessToken(access);
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
      setAccessToken(out.access_token);
      return out.access_token;
    }
  }, [router]);

  useEffect(() => {
    void ensureAuth();
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
    <main style={{ maxWidth: 1200, margin: '0 auto', padding: '1.5rem' }}>
      <OpsNav user={user} onLogout={logout} />
      <div className="card">
        <div style={{ display: 'flex', flexWrap: 'wrap', gap: '0.75rem', alignItems: 'center', marginBottom: '0.5rem' }}>
          <h2 style={{ margin: 0, flex: '1 1 auto', fontSize: '1.25rem' }}>Hub · Agency</h2>
          <AgencyReadOnlyBadge user={user} />
        </div>

        <div className="agency-tabs" role="tablist" style={{ marginBottom: '1rem' }}>
          <button
            type="button"
            role="tab"
            className={`agency-tab${hubTab === 'campaigns' ? ' is-active' : ''}`}
            onClick={() => setHubTab('campaigns')}
          >
            Campaign map
          </button>
          <button
            type="button"
            role="tab"
            className={`agency-tab${hubTab === 'contracts' ? ' is-active' : ''}`}
            onClick={() => setHubTab('contracts')}
          >
            HĐ chờ duyệt
          </button>
        </div>

        {clientFilter ? (
          <p className="muted" style={{ marginTop: 0 }}>
            Lọc client:{' '}
            <Link href={`/agency/clients/${clientFilter}?tab=campaigns`} className="nav-link">
              {clientFilter.slice(0, 8)}…
            </Link>{' '}
            ·{' '}
            <Link href="/crm/hub" className="nav-link">
              Bỏ lọc
            </Link>
          </p>
        ) : null}
        {error ? <p className="error">{error}</p> : null}
        {msg ? <p className="muted">{msg}</p> : null}

        {hubTab === 'campaigns' && accessToken ? (
          <>
            {campaignFilter ? <p className="muted">Lọc hub_campaign_id={campaignFilter}</p> : null}
            <HubCampaignMapsPanel
              token={accessToken}
              canWrite={canWrite}
              showClientColumn
              filterClientId={clientFilter || undefined}
              filterCampaignId={campaignFilter || undefined}
              onFeedback={setMsg}
              onError={setError}
            />
          </>
        ) : null}

        {hubTab === 'contracts' && accessToken ? (
          <ContractApprovalsPanel
            token={accessToken}
            user={user}
            onMessage={setMsg}
            onError={setError}
          />
        ) : null}
      </div>
    </main>
  );
}
