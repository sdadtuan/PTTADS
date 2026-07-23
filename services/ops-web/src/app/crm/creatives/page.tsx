'use client';

import { Suspense } from 'react';
import { CrmCreativesContent } from './CrmCreativesContent';

export default function CrmCreativesPage() {
  return (
    <Suspense
      fallback={
        <main style={{ padding: '2rem' }}>
          <p className="muted">Đang tải…</p>
        </main>
      }
    >
      <CrmCreativesContent />
    </Suspense>
  );
}
