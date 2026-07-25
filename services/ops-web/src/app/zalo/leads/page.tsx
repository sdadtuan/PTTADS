'use client';

import { Suspense } from 'react';
import { ZaloLeadsContent } from './ZaloLeadsContent';

export default function ZaloLeadsPage() {
  return (
    <Suspense
      fallback={
        <main style={{ padding: '2rem' }}>
          <p className="muted">Đang tải…</p>
        </main>
      }
    >
      <ZaloLeadsContent />
    </Suspense>
  );
}
