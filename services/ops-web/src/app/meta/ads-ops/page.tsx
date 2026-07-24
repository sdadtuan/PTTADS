'use client';

import { Suspense } from 'react';
import { MetaAdsOpsContent } from './MetaAdsOpsContent';

export default function MetaAdsOpsPage() {
  return (
    <Suspense
      fallback={
        <main style={{ padding: '2rem' }}>
          <p className="muted">Đang tải Meta Ads Ops…</p>
        </main>
      }
    >
      <MetaAdsOpsContent />
    </Suspense>
  );
}
