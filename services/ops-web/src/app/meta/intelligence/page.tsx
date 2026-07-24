'use client';

import { Suspense } from 'react';
import { MetaIntelligenceContent } from './MetaIntelligenceContent';

export default function MetaIntelligencePage() {
  return (
    <Suspense
      fallback={
        <main style={{ padding: '2rem' }}>
          <p className="muted">Đang tải Meta Intelligence…</p>
        </main>
      }
    >
      <MetaIntelligenceContent />
    </Suspense>
  );
}
