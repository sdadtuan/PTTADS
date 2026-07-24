'use client';

import { Suspense } from 'react';
import { MetaTrackingContent } from './MetaTrackingContent';

export default function MetaTrackingPage() {
  return (
    <Suspense
      fallback={
        <main style={{ padding: '2rem' }}>
          <p className="muted">Đang tải Meta Tracking…</p>
        </main>
      }
    >
      <MetaTrackingContent />
    </Suspense>
  );
}
