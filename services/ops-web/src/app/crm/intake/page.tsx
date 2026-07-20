'use client';

import { Suspense } from 'react';
import { IntakeContent } from './IntakeContent';

export default function CrmIntakePage() {
  return (
    <Suspense
      fallback={
        <main style={{ padding: '2rem' }}>
          <p className="muted">Đang tải…</p>
        </main>
      }
    >
      <IntakeContent />
    </Suspense>
  );
}
