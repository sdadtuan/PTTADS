'use client';

import Link from 'next/link';
import { useCallback, useEffect, useMemo, useState } from 'react';
import { useRouter, useSearchParams } from 'next/navigation';
import { MetaAnomaliesTable } from '@/components/meta/MetaAnomaliesTable';
import { MetaAttributionFooter } from '@/components/meta/MetaAttributionFooter';
import { MetaBudgetRecommendTable } from '@/components/meta/MetaBudgetRecommendTable';
import { MetaIntelligenceRoasKpi } from '@/components/meta/MetaIntelligenceRoasKpi';
import { MetaPageShell } from '@/components/meta/MetaPageShell';
import { useMetaIntelligence } from '@/hooks/meta/useMetaIntelligence';
import { fetchAgencyClients, staffMe, staffRefresh } from '@/lib/api';
import type { AgencyClient } from '@/lib/api';
import {
  clearSession,
  getAccessToken,
  getRefreshToken,
  getStoredUser,
  updateAccessToken,
  updateStoredUser,
  type StoredStaffUser,
} from '@/lib/auth';
import { canViewMetaIntelligence } from '@/lib/meta/caps';
import { metaIntelligenceEnabled } from '@/lib/meta/flags';

export function MetaIntelligenceContent() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const [user, setUser] = useState<StoredStaffUser | null>(null);
  const [token, setToken] = useState<string | null>(null);
  const [clientOptions, setClientOptions] = useState<AgencyClient[]>([]);
  const [clientId, setClientId] = useState(searchParams.get('client_id') ?? '');
  const [days, setDays] = useState(Number(searchParams.get('days') ?? '7') || 7);
  const [authError, setAuthError] = useState('');

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
      if (!canViewMetaIntelligence(me)) {
        setAuthError('Không có quyền Meta Intelligence hoặc feature flag đang tắt');
        return null;
      }
      setToken(access);
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
      setToken(access);
      return access;
    }
  }, [router]);

  useEffect(() => {
    void ensureAuth();
  }, [ensureAuth]);

  useEffect(() => {
    if (!token) return;
    void fetchAgencyClients(token)
      .then((res) => setClientOptions(res.clients ?? []))
      .catch(() => setClientOptions([]));
  }, [token]);

  const { anomalies, roas, recommendations, loading, error, reload, attribution } = useMetaIntelligence({
    token,
    clientId: clientId || undefined,
    days,
  });

  const headerLinks = useMemo(
    () => (
      <div style={{ display: 'flex', gap: '0.75rem', flexWrap: 'wrap', alignItems: 'center' }}>
        <Link href="/meta/facebook-ads" className="nav-link">
          Meta Ads Hub
        </Link>
        <Link href="/meta/tracking" className="nav-link">
          Meta Tracking
        </Link>
      </div>
    ),
    [],
  );

  if (authError) {
    return (
      <main style={{ maxWidth: 720, margin: '2rem auto', padding: '0 1.5rem' }}>
        <p className="error-text">{authError}</p>
      </main>
    );
  }

  if (!user || !token) {
    return (
      <main style={{ padding: '2rem' }}>
        <p className="muted">Đang tải Meta Intelligence…</p>
      </main>
    );
  }

  if (!metaIntelligenceEnabled()) {
    return (
      <MetaPageShell user={user} onLogout={() => { clearSession(); router.replace('/login'); }}>
        <h1 style={{ marginTop: 0 }}>Meta Intelligence</h1>
        <p className="meta-intelligence-disabled-banner">
          B10 Intelligence đang tắt — bật <code>NEXT_PUBLIC_PTT_META_ANOMALY_ENABLED</code> hoặc{' '}
          <code>NEXT_PUBLIC_PTT_META_ROAS_ENABLED</code>.
        </p>
      </MetaPageShell>
    );
  }

  return (
    <MetaPageShell
      user={user}
      onLogout={() => {
        clearSession();
        router.replace('/login');
      }}
      headerExtra={headerLinks}
    >
      <h1 style={{ marginTop: 0 }}>Meta Intelligence</h1>
      <p className="muted" style={{ marginTop: 0 }}>
        ROAS, anomaly median spike, budget recommendations (read-only).
      </p>

      <div className="meta-intelligence-filters">
        <label>
          Client
          <select value={clientId} onChange={(e) => setClientId(e.target.value)}>
            <option value="">Tất cả clients</option>
            {clientOptions.map((c) => (
              <option key={c.id} value={c.id}>
                {c.code ?? c.name ?? c.id}
              </option>
            ))}
          </select>
        </label>
        <label>
          Cửa sổ (ngày)
          <select value={days} onChange={(e) => setDays(Number(e.target.value) || 7)}>
            {[7, 14, 30].map((d) => (
              <option key={d} value={d}>
                {d} ngày
              </option>
            ))}
          </select>
        </label>
        <button type="button" className="btn-secondary" onClick={() => void reload()} disabled={loading}>
          {loading ? 'Đang tải…' : 'Làm mới'}
        </button>
      </div>

      <MetaAttributionFooter attribution={attribution} />
      {error ? <p className="error-text">{error}</p> : null}

      <MetaIntelligenceRoasKpi roas={roas} days={days} />
      <MetaAnomaliesTable data={anomalies} />
      <MetaBudgetRecommendTable data={recommendations} />
    </MetaPageShell>
  );
}
