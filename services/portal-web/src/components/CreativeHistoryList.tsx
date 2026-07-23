'use client';

import type { CreativeRow } from '@/lib/api';
import { fmtDate } from '@/lib/format';

interface CreativeHistoryListProps {
  rows: CreativeRow[];
}

const STATUS_LABEL: Record<string, string> = {
  approved: 'Đã duyệt',
  rejected: 'Từ chối',
};

export function CreativeHistoryList({ rows }: CreativeHistoryListProps) {
  if (rows.length === 0) {
    return (
      <div className="card" style={{ padding: '1.25rem', textAlign: 'center' }}>
        <p style={{ margin: 0, fontWeight: 600 }}>Chưa có lịch sử duyệt trong 30 ngày</p>
      </div>
    );
  }

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '0.75rem' }}>
      {rows.map((row) => (
        <article key={row.id} className="creative-card">
          <div style={{ display: 'flex', justifyContent: 'space-between', gap: '1rem', flexWrap: 'wrap' }}>
            <div>
              <h3 style={{ margin: '0 0 0.35rem', fontSize: '1rem' }}>{row.title}</h3>
              <p className="muted" style={{ margin: 0 }}>
                v{row.version}
                {row.external_campaign_name ? ` · ${row.external_campaign_name}` : ''}
              </p>
              <p className="muted" style={{ margin: '0.35rem 0 0', fontSize: '0.85rem' }}>
                {row.reviewed_by ? `Bởi ${row.reviewed_by}` : ''}
                {row.reviewed_at ? ` · ${fmtDate(row.reviewed_at.slice(0, 10))}` : ''}
              </p>
              {row.review_note ? (
                <p style={{ margin: '0.5rem 0 0', fontSize: '0.9rem' }}>{row.review_note}</p>
              ) : null}
            </div>
            <span className={`badge${row.status === 'rejected' ? ' badge-warn' : ''}`}>
              {STATUS_LABEL[row.status] ?? row.status}
            </span>
          </div>
        </article>
      ))}
    </div>
  );
}
