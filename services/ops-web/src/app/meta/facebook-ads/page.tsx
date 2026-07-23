'use client';

import { Suspense } from 'react';
import { MetaFacebookAdsContent } from './MetaFacebookAdsContent';

export default function MetaFacebookAdsPage() {
  return (
    <Suspense
      fallback={
        <main style={{ padding: '2rem' }}>
          <p className="muted">Đang tải…</p>
        </main>
      }
    >
      <MetaFacebookAdsContent />
    </Suspense>
  );
}
