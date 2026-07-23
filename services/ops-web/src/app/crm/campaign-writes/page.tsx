'use client';

import { Suspense } from 'react';
import { CrmCampaignWritesContent } from './CrmCampaignWritesContent';

export default function CrmCampaignWritesPage() {
  return (
    <Suspense
      fallback={
        <main style={{ padding: '2rem' }}>
          <p className="muted">Đang tải…</p>
        </main>
      }
    >
      <CrmCampaignWritesContent />
    </Suspense>
  );
}
