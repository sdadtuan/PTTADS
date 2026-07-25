'use client';

import { Suspense } from 'react';
import { ZaloZaloAdsContent } from './ZaloZaloAdsContent';

export default function ZaloZaloAdsPage() {
  return (
    <Suspense
      fallback={
        <main style={{ padding: '2rem' }}>
          <p className="muted">Đang tải…</p>
        </main>
      }
    >
      <ZaloZaloAdsContent />
    </Suspense>
  );
}
