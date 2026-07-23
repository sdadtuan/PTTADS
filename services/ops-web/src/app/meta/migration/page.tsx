'use client';

import { Suspense } from 'react';
import { MetaMigrationPageContent } from './MetaMigrationPageContent';

export default function MetaMigrationPage() {
  return (
    <Suspense
      fallback={
        <main style={{ padding: '2rem' }}>
          <p className="muted">Đang tải…</p>
        </main>
      }
    >
      <MetaMigrationPageContent />
    </Suspense>
  );
}
