'use client';

import type { CapiEventRow } from '@/lib/meta/types';
import { fmtRelativeTime } from '@/lib/meta/format';

interface Props {
  events: CapiEventRow[];
  loading: boolean;
  canConfigure: boolean;
  retryingId: string | null;
  onRetry: (logId: string) => void;
}

const STATUS_CLASS: Record<string, string> = {
  sent: 'meta-tracking-status--sent',
  failed: 'meta-tracking-status--failed',
  pending: 'meta-tracking-status--pending',
  skipped: 'meta-tracking-status--skipped',
};

export function MetaCapiEventsTable({
  events,
  loading,
  canConfigure,
  retryingId,
  onRetry,
}: Props) {
  return (
    <div className="card meta-tracking-section">
      <h2 className="meta-tracking-section-title">CAPI event log</h2>
      {loading ? <p className="muted">Đang tải events…</p> : null}
      <div style={{ overflowX: 'auto' }}>
        <table className="perf-table meta-tracking-table">
          <thead>
            <tr>
              <th>Thời gian</th>
              <th>Client</th>
              <th>Event</th>
              <th>Status</th>
              <th>Error</th>
              <th />
            </tr>
          </thead>
          <tbody>
            {events.map((event) => (
              <tr key={event.id}>
                <td>{fmtRelativeTime(event.created_at)}</td>
                <td>{event.client_code || event.client_name || event.client_id.slice(0, 8)}</td>
                <td>
                  {event.event_name}
                  <div className="muted meta-tracking-event-id">{event.event_id}</div>
                </td>
                <td>
                  <span className={`meta-tracking-status ${STATUS_CLASS[event.status] ?? ''}`}>
                    {event.status}
                  </span>
                </td>
                <td className="meta-tracking-error-cell">{event.error_message ?? '—'}</td>
                <td>
                  {canConfigure && ['failed', 'pending'].includes(event.status) ? (
                    <button
                      type="button"
                      className="btn btn-sm btn-secondary"
                      disabled={retryingId === event.id}
                      onClick={() => onRetry(event.id)}
                    >
                      {retryingId === event.id ? '…' : 'Retry'}
                    </button>
                  ) : null}
                </td>
              </tr>
            ))}
            {!loading && !events.length ? (
              <tr>
                <td colSpan={6} className="muted">
                  Không có CAPI events
                </td>
              </tr>
            ) : null}
          </tbody>
        </table>
      </div>
    </div>
  );
}
