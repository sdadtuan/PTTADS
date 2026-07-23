'use client';

import { useEffect, useState } from 'react';
import type { CreativeRow } from '@/lib/api';
import { fmtDate } from '@/lib/format';

interface CreativeInboxProps {
  rows: CreativeRow[];
  canApprove: boolean;
  onApprove: (id: string) => Promise<void>;
  onReject: (id: string, note: string) => Promise<void>;
}

function CreativeAssetPreview({ row }: { row: CreativeRow }) {
  if (!row.asset_url) {
    return null;
  }
  const isImage = row.asset_type === 'image' || /\.(png|jpe?g|gif|webp)(\?|$)/i.test(row.asset_url);
  if (isImage) {
    return (
      // eslint-disable-next-line @next/next/no-img-element
      <img
        src={row.asset_url}
        alt={row.title}
        style={{ maxWidth: '100%', maxHeight: 220, borderRadius: 8, marginTop: '0.75rem' }}
      />
    );
  }
  return (
    <p className="muted" style={{ margin: '0.75rem 0 0' }}>
      Asset:{' '}
      <a href={row.asset_url} target="_blank" rel="noreferrer">
        mở preview ({row.asset_type || 'file'})
      </a>
    </p>
  );
}

export function CreativeInbox({ rows, canApprove, onApprove, onReject }: CreativeInboxProps) {
  const [busyId, setBusyId] = useState<string | null>(null);
  const [rejectId, setRejectId] = useState<string | null>(null);
  const [confirmId, setConfirmId] = useState<string | null>(null);
  const [rejectNote, setRejectNote] = useState('');
  const [error, setError] = useState('');

  if (rows.length === 0) {
    return (
      <div className="card" style={{ padding: '1.25rem', textAlign: 'center' }}>
        <p style={{ margin: 0, fontWeight: 600 }}>Không có creative đang chờ duyệt</p>
        <p className="muted" style={{ margin: '0.5rem 0 0' }}>
          AM sẽ gửi creative mới qua workflow Launch QA khi sẵn sàng.
        </p>
      </div>
    );
  }

  async function handleApprove(id: string) {
    setBusyId(id);
    setError('');
    try {
      await onApprove(id);
      setConfirmId(null);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Duyệt thất bại');
    } finally {
      setBusyId(null);
    }
  }

  async function handleReject(id: string) {
    setBusyId(id);
    setError('');
    try {
      await onReject(id, rejectNote);
      setRejectId(null);
      setRejectNote('');
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Từ chối thất bại');
    } finally {
      setBusyId(null);
    }
  }

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '1rem' }}>
      {error && <p className="error">{error}</p>}
      {rows.map((row) => (
        <article key={row.id} className="creative-card">
          <div style={{ display: 'flex', justifyContent: 'space-between', gap: '1rem', flexWrap: 'wrap' }}>
            <div style={{ flex: 1, minWidth: 240 }}>
              <h3 style={{ margin: '0 0 0.35rem', fontSize: '1rem' }}>{row.title}</h3>
              <p className="muted" style={{ margin: 0 }}>
                v{row.version}
                {row.external_campaign_name ? ` · ${row.external_campaign_name}` : ''}
                {' · '}
                gửi {fmtDate(row.submitted_at.slice(0, 10))}
              </p>
              {row.description && (
                <p style={{ margin: '0.5rem 0 0', fontSize: '0.9rem' }}>{row.description}</p>
              )}
              <CreativeAssetPreview row={row} />
            </div>
            {canApprove && row.status === 'pending_client' && (
              <div style={{ display: 'flex', gap: '0.5rem', alignItems: 'flex-start' }}>
                <button
                  type="button"
                  className="btn"
                  disabled={busyId === row.id}
                  onClick={() => setConfirmId(row.id)}
                >
                  Duyệt
                </button>
                <button
                  type="button"
                  className="btn btn-secondary"
                  disabled={busyId === row.id}
                  onClick={() => {
                    setRejectId(row.id);
                    setRejectNote('');
                  }}
                >
                  Từ chối
                </button>
              </div>
            )}
          </div>
          {confirmId === row.id && (
            <div className="card" style={{ marginTop: '0.75rem', padding: '0.75rem' }}>
              <p style={{ margin: '0 0 0.5rem' }}>Xác nhận duyệt creative này? Hành động sẽ đồng bộ Launch QA.</p>
              <div style={{ display: 'flex', gap: '0.5rem' }}>
                <button type="button" className="btn" disabled={busyId === row.id} onClick={() => void handleApprove(row.id)}>
                  Xác nhận duyệt
                </button>
                <button type="button" className="btn btn-secondary" onClick={() => setConfirmId(null)}>
                  Huỷ
                </button>
              </div>
            </div>
          )}
          {rejectId === row.id && (
            <div className="card" style={{ marginTop: '0.75rem', padding: '0.75rem' }}>
              <label htmlFor={`reject-${row.id}`}>Lý do từ chối (tuỳ chọn)</label>
              <textarea
                id={`reject-${row.id}`}
                rows={3}
                value={rejectNote}
                onChange={(e) => setRejectNote(e.target.value)}
                style={{ width: '100%', marginTop: '0.35rem' }}
              />
              <div style={{ display: 'flex', gap: '0.5rem', marginTop: '0.5rem' }}>
                <button type="button" className="btn btn-secondary" disabled={busyId === row.id} onClick={() => void handleReject(row.id)}>
                  Gửi từ chối
                </button>
                <button type="button" className="btn btn-secondary" onClick={() => setRejectId(null)}>
                  Huỷ
                </button>
              </div>
            </div>
          )}
        </article>
      ))}
    </div>
  );
}
