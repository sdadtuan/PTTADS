'use client';

import { PerformancePanel } from '@/components/PerformancePanel';
import { PortalPageShell } from '@/components/PortalPageShell';

export default function MetaPerformancePage() {
  return (
    <PortalPageShell>
      {({ token }) => (
        <PerformancePanel
          token={token}
          channel="meta"
          title="Meta Performance (Facebook / Instagram)"
          hideChannelColumn
        />
      )}
    </PortalPageShell>
  );
}
