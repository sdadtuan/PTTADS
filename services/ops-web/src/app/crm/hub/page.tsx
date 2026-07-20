'use client';

import { Suspense } from 'react';
import { CrmHubContent } from './CrmHubContent';

export default function CrmHubPage() {
  return (
    <Suspense
      fallback={
        <main style={{ padding: '2rem' }}>
          <p className="muted">Đang tải…</p>
        </main>
      }
    >
      <CrmHubContent />
    </Suspense>
  );
}
