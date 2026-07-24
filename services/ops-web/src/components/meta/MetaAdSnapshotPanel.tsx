'use client';

import type { MetaAdsOpsEditSnapshot } from '@/lib/meta/types';

interface MetaAdSnapshotPanelProps {
  snapshot: MetaAdsOpsEditSnapshot | null;
  loading?: boolean;
}

export function MetaAdSnapshotPanel({ snapshot, loading }: MetaAdSnapshotPanelProps) {
  if (loading) return <div className="card muted">Đang tải snapshot ad…</div>;
  if (!snapshot) return null;

  return (
    <div className="card">
      <h3 style={{ marginTop: 0 }}>Snapshot hiện tại</h3>
      <p className="muted" style={{ marginTop: 0 }}>
        Ad <code>{snapshot.external_ad_id}</code> · status {snapshot.effective_status}
        {snapshot.stub ? ' · stub cache' : ''}
      </p>
      <dl style={{ display: 'grid', gridTemplateColumns: '140px 1fr', gap: '0.5rem 1rem', margin: 0 }}>
        <dt>Headline</dt>
        <dd style={{ margin: 0 }}>{snapshot.headline}</dd>
        <dt>Primary text</dt>
        <dd style={{ margin: 0 }}>{snapshot.primary_text}</dd>
        <dt>CTA</dt>
        <dd style={{ margin: 0 }}>{snapshot.call_to_action}</dd>
        <dt>Creative ID</dt>
        <dd style={{ margin: 0 }}>{snapshot.external_creative_id ?? '—'}</dd>
      </dl>
    </div>
  );
}
