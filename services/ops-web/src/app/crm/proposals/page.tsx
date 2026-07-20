'use client';

import { Suspense } from 'react';
import { ProposalsContent } from './ProposalsContent';

export default function CrmProposalsPage() {
  return (
    <Suspense
      fallback={
        <main style={{ padding: '2rem' }}>
          <p className="muted">Đang tải…</p>
        </main>
      }
    >
      <ProposalsContent />
    </Suspense>
  );
}
