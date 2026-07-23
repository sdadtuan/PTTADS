'use client';

import { Suspense } from 'react';
import { GoogleGoogleAdsContent } from './GoogleGoogleAdsContent';

export default function GoogleGoogleAdsPage() {
  return (
    <Suspense
      fallback={
        <main style={{ padding: '2rem' }}>
          <p className="muted">Đang tải…</p>
        </main>
      }
    >
      <GoogleGoogleAdsContent />
    </Suspense>
  );
}
