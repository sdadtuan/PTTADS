'use client';

import Link from 'next/link';
import { emailJourneysEnabled } from '@/lib/email-flags';

const TABS = [
  { id: 'overview', label: 'Tổng quan', href: (id: string) => `/email/clients/${id}` },
  { id: 'contacts', label: 'Danh bạ', href: (id: string) => `/email/contacts?client_id=${id}` },
  { id: 'consent', label: 'Consent', href: (id: string) => `/email/consent?client_id=${id}` },
  { id: 'segments', label: 'Phân khúc', href: (id: string) => `/email/segments?client_id=${id}` },
  { id: 'campaigns', label: 'Chiến dịch', href: (id: string) => `/email/campaigns?client_id=${id}` },
  { id: 'deliverability', label: 'Deliverability', href: (id: string) => `/email/deliverability?client_id=${id}` },
  { id: 'reports', label: 'Báo cáo', href: (id: string) => `/email/reports?client_id=${id}` },
  { id: 'settings', label: 'Cài đặt', href: (id: string) => `/email/clients/${id}?tab=settings` },
] as const;

export function EmailClientWorkspaceTabs({
  clientId,
  active,
}: {
  clientId: string;
  active: string;
}) {
  return (
    <nav className="email-workspace-tabs" aria-label="Client workspace">
      {TABS.map((tab) => (
        <Link
          key={tab.id}
          href={tab.href(clientId)}
          className={active === tab.id ? 'active' : undefined}
        >
          {tab.label}
        </Link>
      ))}
      {emailJourneysEnabled() ? (
        <Link href={`/email/journeys?client_id=${clientId}`} className={active === 'journeys' ? 'active' : undefined}>
          Journeys
        </Link>
      ) : null}
    </nav>
  );
}
