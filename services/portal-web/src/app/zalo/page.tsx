'use client';

import { PerformancePanel } from '@/components/PerformancePanel';
import { PortalPageShell } from '@/components/PortalPageShell';

export default function ZaloPerformancePage() {
  return (
    <PortalPageShell>
      {({ token }) => (
        <PerformancePanel
          token={token}
          channel="zalo"
          title="Zalo Ads Performance"
          hideChannelColumn
        />
      )}
    </PortalPageShell>
  );
}
