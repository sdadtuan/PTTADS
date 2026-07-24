'use client';

import Link from 'next/link';
import { useCallback, useEffect, useMemo, useState } from 'react';
import { useRouter, useSearchParams } from 'next/navigation';
import { MetaCapiEventsTable } from '@/components/meta/MetaCapiEventsTable';
import { MetaConversionRulesTable } from '@/components/meta/MetaConversionRulesTable';
import { MetaPageShell } from '@/components/meta/MetaPageShell';
import {
  MetaPreflightChecklist,
  preflightFromHealthAccounts,
} from '@/components/meta/MetaPreflightChecklist';
import { MetaTrackingAccountTable } from '@/components/meta/MetaTrackingAccountTable';
import { MetaTrackingKpiGrid } from '@/components/meta/MetaTrackingKpiGrid';
import { useMetaCapiEvents } from '@/hooks/meta/useMetaCapiEvents';
import { useMetaConversionRules } from '@/hooks/meta/useMetaConversionRules';
import { useMetaTracking } from '@/hooks/meta/useMetaTracking';
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
import { canConfigureMetaTracking, canViewMetaTracking } from '@/lib/meta/caps';
import { metaTrackingEnabled } from '@/lib/meta/flags';

export function MetaTrackingContent() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const [user, setUser] = useState<StoredStaffUser | null>(null);
  const [token, setToken] = useState<string | null>(null);
  const [clientOptions, setClientOptions] = useState<AgencyClient[]>([]);
  const [clientId, setClientId] = useState(searchParams.get('client_id') ?? '');
  const [eventStatus, setEventStatus] = useState('');
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
      if (!canViewMetaTracking(me)) {
        setAuthError('Không có quyền Meta Tracking');
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
      .then((out) => setClientOptions(out.clients ?? []))
      .catch(() => setClientOptions([]));
  }, [token]);

  const tracking = useMetaTracking(token, clientId || undefined, 7);
  const capiEvents = useMetaCapiEvents(token, {
    client_id: clientId || undefined,
    status: eventStatus || undefined,
    limit: 50,
  });
  const rules = useMetaConversionRules(token, clientId || undefined);

  const canConfigure = canConfigureMetaTracking(user);
  const preflightItems = useMemo(
    () => preflightFromHealthAccounts(tracking.data?.accounts ?? []),
    [tracking.data?.accounts],
  );

  function logout() {
    clearSession();
    router.replace('/login');
  }

  function applyClientFilter(nextClientId: string) {
    setClientId(nextClientId);
    const qs = new URLSearchParams();
    if (nextClientId) qs.set('client_id', nextClientId);
    router.replace(qs.toString() ? `/meta/tracking?${qs.toString()}` : '/meta/tracking');
  }

  if (!metaTrackingEnabled()) {
    return (
      <main style={{ maxWidth: 720, margin: '2rem auto', padding: '1.5rem' }}>
        <p className="muted">
          Meta Tracking UI đang tắt — đặt <code>NEXT_PUBLIC_PTT_META_TRACKING_ENABLED=1</code>.
        </p>
      </main>
    );
  }

  if (authError) {
    return (
      <main style={{ maxWidth: 720, margin: '2rem auto', padding: '1.5rem' }}>
        <p className="error">{authError}</p>
      </main>
    );
  }

  if (!user || !token) {
    return (
      <main style={{ padding: '2rem' }}>
        <p className="muted">Đang tải…</p>
      </main>
    );
  }

  return (
    <MetaPageShell user={user} onLogout={logout}>
      <div className="card meta-tracking-header">
        <div>
          <h1 style={{ margin: 0, fontSize: '1.25rem' }}>Meta Tracking</h1>
          <p className="muted" style={{ margin: '0.35rem 0 0' }}>
            CAPI health · conversion rules · event log · Launch preflight
          </p>
        </div>
        <div className="meta-tracking-header-actions">
          <Link href="/meta/facebook-ads" className="btn btn-sm btn-secondary">
            Meta Ads hub
          </Link>
          <label className="muted meta-tracking-filter">
            Client
            <select value={clientId} onChange={(e) => applyClientFilter(e.target.value)}>
              <option value="">Tất cả clients</option>
              {clientOptions.map((c) => (
                <option key={c.id} value={c.id}>
                  {c.code || c.name || c.id}
                </option>
              ))}
            </select>
          </label>
          <button type="button" className="btn btn-sm" onClick={() => void tracking.reload()}>
            Làm mới
          </button>
        </div>
      </div>

      {tracking.error ? <p className="error">{tracking.error}</p> : null}
      {capiEvents.error ? <p className="error">{capiEvents.error}</p> : null}
      {rules.error ? <p className="error">{rules.error}</p> : null}

      {tracking.data ? (
        <MetaTrackingKpiGrid
          global={tracking.data.global}
          windowDays={tracking.data.window_days}
          disabled={tracking.data.disabled}
        />
      ) : null}

      <MetaPreflightChecklist
        items={preflightItems}
        clientId={clientId || undefined}
        onRefresh={() => void tracking.reload()}
        refreshing={tracking.loading}
      />

      <MetaTrackingAccountTable
        token={token}
        accounts={tracking.data?.accounts ?? []}
        canConfigure={canConfigure}
        onTestComplete={() => void tracking.reload()}
      />

      <MetaConversionRulesTable
        rules={rules.rules}
        canConfigure={canConfigure}
        saving={rules.saving}
        onToggle={(id, enabled) => void rules.toggleRule(id, enabled)}
        onCreate={(body) => void rules.saveRule(body)}
      />

      <div className="meta-tracking-events-toolbar">
        <label className="muted">
          Event status
          <select value={eventStatus} onChange={(e) => setEventStatus(e.target.value)}>
            <option value="">Tất cả</option>
            <option value="sent">sent</option>
            <option value="failed">failed</option>
            <option value="pending">pending</option>
            <option value="skipped">skipped</option>
          </select>
        </label>
      </div>

      <MetaCapiEventsTable
        events={capiEvents.events}
        loading={capiEvents.loading}
        canConfigure={canConfigure}
        retryingId={capiEvents.retryingId}
        onRetry={(id) => void capiEvents.retry(id)}
      />
    </MetaPageShell>
  );
}
