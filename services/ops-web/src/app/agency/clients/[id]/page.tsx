import { Suspense } from 'react';
import { AgencyClientDetailContent } from './AgencyClientDetailContent';

export default function AgencyClientDetailPage() {
  return (
    <Suspense
      fallback={
        <main style={{ padding: '2rem' }}>
          <p className="muted">Đang tải…</p>
        </main>
      }
    >
      <AgencyClientDetailContent />
    </Suspense>
  );
}
