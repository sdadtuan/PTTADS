'use client';

import { PerformancePanel } from '@/components/PerformancePanel';
import { PortalPageShell } from '@/components/PortalPageShell';

export default function GooglePerformancePage() {
  return (
    <PortalPageShell>
      {({ token }) => (
        <PerformancePanel
          token={token}
          channel="google"
          title="Google Ads Performance"
          hideChannelColumn
        />
      )}
    </PortalPageShell>
  );
}
