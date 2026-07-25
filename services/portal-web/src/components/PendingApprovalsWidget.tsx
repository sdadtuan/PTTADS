'use client';

import Link from 'next/link';
import type { PortalNotificationSummaryResponse } from '@/lib/api';

interface PendingApprovalsWidgetProps {
  summary: PortalNotificationSummaryResponse | null;
  seoPending?: number;
  emailPending?: number;
}

export function PendingApprovalsWidget({
  summary,
  seoPending = 0,
  emailPending = 0,
}: PendingApprovalsWidgetProps) {
  const creativePending = summary?.pending_creatives ?? 0;
  const unread = summary?.unread ?? 0;
  const totalPending = creativePending + emailPending + seoPending;

  if (totalPending === 0 && unread === 0) {
    return (
      <section className="card" style={{ marginBottom: '1.5rem', padding: '1rem 1.25rem' }}>
        <h2 style={{ margin: '0 0 0.35rem', fontSize: '1.05rem' }}>Thông báo &amp; duyệt</h2>
        <p className="muted" style={{ margin: 0 }}>
          Không có mục chờ duyệt.{' '}
          <Link href="/notifications">Xem trung tâm thông báo</Link>
        </p>
      </section>
    );
  }

  return (
    <section className="card" style={{ marginBottom: '1.5rem', padding: '1rem 1.25rem' }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', gap: '1rem' }}>
        <div>
          <h2 style={{ margin: '0 0 0.35rem', fontSize: '1.05rem' }}>Thông báo &amp; duyệt</h2>
          <p className="muted" style={{ margin: 0 }}>
            {unread > 0 ? `${unread} thông báo chưa đọc` : 'Có mục cần xử lý'}
          </p>
        </div>
        <Link href="/notifications" className="btn btn-secondary">
          Trung tâm thông báo{unread > 0 ? ` (${unread})` : ''}
        </Link>
      </div>
      <ul style={{ margin: '1rem 0 0', paddingLeft: '1.25rem' }}>
        {creativePending > 0 ? (
          <li>
            <Link href="/creatives">Creative inbox — {creativePending} chờ duyệt</Link>
          </li>
        ) : null}
        {emailPending > 0 ? (
          <li>
            <Link href="/email/approvals">Email approvals — {emailPending} chờ duyệt</Link>
          </li>
        ) : null}
        {seoPending > 0 ? (
          <li>
            <Link href="/seo/content">SEO content review — {seoPending} chờ review</Link>
          </li>
        ) : null}
      </ul>
    </section>
  );
}
