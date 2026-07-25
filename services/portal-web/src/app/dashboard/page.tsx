'use client';

import { useEffect, useState } from 'react';
import Link from 'next/link';
import { PendingApprovalsWidget } from '@/components/PendingApprovalsWidget';
import { PerformancePanel } from '@/components/PerformancePanel';
import { PortalPageShell } from '@/components/PortalPageShell';
import {
  fetchPortalNotificationSummary,
  portalSeoStatus,
  type PortalNotificationSummaryResponse,
} from '@/lib/api';
import { usePortalEmailNav } from '@/hooks/usePortalEmailNav';
import { usePortalSeoNav } from '@/hooks/usePortalSeoNav';

export default function DashboardPage() {
  return (
    <PortalPageShell>
      {({ token }) => <DashboardContent token={token} />}
    </PortalPageShell>
  );
}

function DashboardContent({ token }: { token: string }) {
  const seoEnabled = usePortalSeoNav(token);
  const { pendingEmail } = usePortalEmailNav(token);
  const [summary, setSummary] = useState<PortalNotificationSummaryResponse | null>(null);
  const [seoPending, setSeoPending] = useState(0);

  useEffect(() => {
    void fetchPortalNotificationSummary(token)
      .then(setSummary)
      .catch(() => setSummary(null));
  }, [token]);

  useEffect(() => {
    if (!seoEnabled) {
      setSeoPending(0);
      return;
    }
    void portalSeoStatus(token)
      .then((status) => setSeoPending(Number(status.pending_client_review ?? 0)))
      .catch(() => setSeoPending(0));
  }, [token, seoEnabled]);

  return (
    <>
      <PendingApprovalsWidget summary={summary} seoPending={seoPending} emailPending={pendingEmail} />
      <PerformancePanel token={token} title="Performance Meta + Google + Zalo" subtitle="Tất cả kênh" />
      <p className="muted" style={{ marginTop: '1rem' }}>
        <Link href="/notifications">Trung tâm thông báo</Link> ·{' '}
        <Link href="/creatives">Creative inbox</Link>
      </p>
    </>
  );
}
