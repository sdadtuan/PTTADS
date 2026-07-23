'use client';

import { useEffect, useState, type ReactNode } from 'react';
import { PortalNav } from '@/components/PortalNav';
import { fetchPendingCreativeCount, fetchPortalSettings, type PortalSettingsResponse } from '@/lib/api';
import { usePortalAuth } from '@/hooks/usePortalAuth';

interface PortalPageShellProps {
  children: (ctx: { token: string; user: NonNullable<ReturnType<typeof usePortalAuth>['user']> }) => ReactNode;
}

export function PortalPageShell({ children }: PortalPageShellProps) {
  const { user, token, loading, sessionWarning, logout } = usePortalAuth();
  const [pendingCount, setPendingCount] = useState(0);
  const [branding, setBranding] = useState<PortalSettingsResponse | null>(null);

  useEffect(() => {
    if (!token) return;
    void fetchPendingCreativeCount(token).then(setPendingCount).catch(() => setPendingCount(0));
    void fetchPortalSettings(token)
      .then(setBranding)
      .catch(() => setBranding(null));
  }, [token]);

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
        branding={branding}
        seoEnabled={false}
        emailEnabled={false}
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
