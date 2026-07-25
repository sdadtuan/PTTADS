'use client';

import { useEffect, useState, type ReactNode } from 'react';
import { PortalNav } from '@/components/PortalNav';
import {
  fetchPendingCreativeCount,
  fetchPortalNotificationSummary,
  fetchPortalSettings,
  portalSeoStatus,
  type PortalNotificationSummaryResponse,
  type PortalSettingsResponse,
} from '@/lib/api';
import { usePortalAuth } from '@/hooks/usePortalAuth';
import { usePortalEmailNav } from '@/hooks/usePortalEmailNav';
import { usePortalSeoNav } from '@/hooks/usePortalSeoNav';

interface PortalPageShellProps {
  children: (ctx: { token: string; user: NonNullable<ReturnType<typeof usePortalAuth>['user']> }) => ReactNode;
}

export function PortalPageShell({ children }: PortalPageShellProps) {
  const { user, token, loading, sessionWarning, logout } = usePortalAuth();
  const seoEnabled = usePortalSeoNav(token);
  const { emailEnabled, pendingEmail } = usePortalEmailNav(token);
  const [pendingCount, setPendingCount] = useState(0);
  const [seoPending, setSeoPending] = useState(0);
  const [notificationSummary, setNotificationSummary] = useState<PortalNotificationSummaryResponse | null>(
    null,
  );
  const [branding, setBranding] = useState<PortalSettingsResponse | null>(null);

  useEffect(() => {
    if (!token) return;
    void fetchPendingCreativeCount(token).then(setPendingCount).catch(() => setPendingCount(0));
    void fetchPortalSettings(token)
      .then(setBranding)
      .catch(() => setBranding(null));
    void fetchPortalNotificationSummary(token)
      .then(setNotificationSummary)
      .catch(() => setNotificationSummary(null));
    if (seoEnabled) {
      void portalSeoStatus(token)
        .then((status) => setSeoPending(Number(status.pending_client_review ?? 0)))
        .catch(() => setSeoPending(0));
    } else {
      setSeoPending(0);
    }
  }, [token, seoEnabled]);

  if (loading || !user || !token) {
    return (
      <main style={{ padding: '2rem' }}>
        <p className="muted">Đang tải…</p>
      </main>
    );
  }

  return (
    <main style={{ maxWidth: 1100, margin: '0 auto', padding: '1.5rem' }}>
      <PortalNav
        user={user}
        onLogout={logout}
        pendingCount={pendingCount}
        notificationUnread={notificationSummary?.unread ?? 0}
        emailPending={pendingEmail}
        seoPending={seoPending}
        branding={branding}
        seoEnabled={seoEnabled}
        emailEnabled={emailEnabled}
      />
      {sessionWarning ? (
        <p className="badge" style={{ marginBottom: '1rem' }}>
          {sessionWarning}
        </p>
      ) : null}
      {children({ token, user })}
    </main>
  );
}
