'use client';

import { PerformancePanel } from '@/components/PerformancePanel';
import { PortalPageShell } from '@/components/PortalPageShell';

export default function DashboardPage() {
  return (
    <PortalPageShell>
      {({ token }) => (
        <PerformancePanel token={token} title="Performance Meta + Google" subtitle="Tất cả kênh" />
      )}
    </PortalPageShell>
  );
}
