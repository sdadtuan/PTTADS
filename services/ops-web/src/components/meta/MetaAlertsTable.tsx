'use client';

import Link from 'next/link';
import { MetaEditAdLink } from '@/components/meta/MetaEditAdLink';
import { parseDisapprovedAdId } from '@/lib/meta/ads-ops-url';
import { fmtDateTime } from '@/lib/meta/format';
import type { MetaAlertRow } from '@/lib/meta/types';

interface MetaAlertsTableProps {
  alerts: MetaAlertRow[];
  loading: boolean;
  ackBusyId: string | null;
  onAck: (alertId: string) => void;
}

function alertTypeLabel(type: string): string {
  const map: Record<string, string> = {
    cpl_high: 'CPL cao',
    unmapped_spend_high: 'Chi tiêu chưa map',
    sync_failed: 'Sync lỗi',
    meta_account_disabled: 'Tài khoản Meta bị vô hiệu',
    ad_disapproved: 'Ad bị từ chối',
  };
  return map[type] ?? type;
}

function severityClass(severity: string): string {
  if (severity === 'danger' || severity === 'error') return 'error';
  if (severity === 'warning' || severity === 'warn') return 'muted';
  return '';
}

export function MetaAlertsTable({ alerts, loading, ackBusyId, onAck }: MetaAlertsTableProps) {
  return (
    <div className="card" id="alerts-table">
      <h2 style={{ marginTop: 0, fontSize: '1.1rem' }}>Meta alerts (PG)</h2>
      <p className="muted" style={{ marginTop: 0 }}>
        Deduped alerts từ <code>meta_alerts</code> · inline summary alerts vẫn hiển thị phía trên.
      </p>
      <div style={{ overflowX: 'auto' }}>
        <table className="perf-table">
          <thead>
            <tr>
              <th>Loại</th>
              <th>Client</th>
              <th>Campaign</th>
              <th>Severity</th>
              <th>Ngày</th>
              <th>Message</th>
              <th>Action</th>
              <th>Ack</th>
            </tr>
          </thead>
          <tbody>
            {alerts.map((alert) => {
              const disapprovedAdId = parseDisapprovedAdId(alert);
              return (
              <tr key={alert.id}>
                <td>{alertTypeLabel(alert.alert_type)}</td>
                <td>
                  <Link href={`/agency/clients/${alert.client_id}`} className="nav-link">
                    {alert.client_code || alert.client_name || alert.client_id.slice(0, 8)}
                  </Link>
                </td>
                <td>{alert.external_campaign_id ?? '—'}</td>
                <td className={severityClass(alert.severity)}>{alert.severity}</td>
                <td>{alert.performance_date ?? fmtDateTime(alert.created_at).slice(0, 10)}</td>
                <td>{alert.message}</td>
                <td>
                  {disapprovedAdId ? (
                    <MetaEditAdLink
                      clientId={alert.client_id}
                      externalAdId={disapprovedAdId}
                      disapproved
                    />
                  ) : (
                    <span className="muted">—</span>
                  )}
                </td>
                <td>
                  <button
                    type="button"
                    className="btn btn-sm btn-secondary"
                    disabled={ackBusyId === alert.id}
                    onClick={() => onAck(alert.id)}
                  >
                    {ackBusyId === alert.id ? '…' : 'Ack'}
                  </button>
                </td>
              </tr>
            );
            })}
            {!loading && alerts.length === 0 ? (
              <tr>
                <td colSpan={8} className="muted">
                  Không có alert mở · bật <code>PTT_META_ALERTS_ENABLED=1</code> trên backend để eval
                </td>
              </tr>
            ) : null}
          </tbody>
        </table>
      </div>
    </div>
  );
}
