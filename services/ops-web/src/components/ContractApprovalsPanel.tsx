'use client';

import Link from 'next/link';
import { useCallback, useEffect, useState } from 'react';
import {
  approveContractApproval,
  fetchPendingContractApprovals,
  rejectContractApproval,
  type ContractApprovalRow,
} from '@/lib/api';
import { hasCap, type StoredStaffUser } from '@/lib/auth';

interface Props {
  token: string;
  user: StoredStaffUser | null;
  onMessage?: (msg: string) => void;
  onError?: (msg: string) => void;
}

export function ContractApprovalsPanel({ token, user, onMessage, onError }: Props) {
  const [rows, setRows] = useState<ContractApprovalRow[]>([]);
  const [loading, setLoading] = useState(true);
  const [busyId, setBusyId] = useState<number | null>(null);
  const [rejectNotes, setRejectNotes] = useState<Record<number, string>>({});
  const [lastLifecycleId, setLastLifecycleId] = useState<number | null>(null);

  const canApprove = hasCap(user, 'crm_leads', 'assign');

  const reload = useCallback(async () => {
    setLoading(true);
    try {
      const data = await fetchPendingContractApprovals(token);
      setRows(data.approvals);
    } catch (err) {
      onError?.(err instanceof Error ? err.message : 'Tải inbox HĐ thất bại');
    } finally {
      setLoading(false);
    }
  }, [token, onError]);

  useEffect(() => {
    void reload();
  }, [reload]);

  async function onApprove(id: number) {
    setBusyId(id);
    try {
      const out = await approveContractApproval(token, id);
      onMessage?.(`Đã duyệt — lifecycle #${out.lifecycle_id} Onboard`);
      setLastLifecycleId(out.lifecycle_id);
      await reload();
    } catch (err) {
      onError?.(err instanceof Error ? err.message : 'Duyệt thất bại');
    } finally {
      setBusyId(null);
    }
  }

  async function onReject(id: number) {
    setBusyId(id);
    try {
      await rejectContractApproval(token, id, { decision_notes: rejectNotes[id] ?? '' });
      onMessage?.('Đã từ chối yêu cầu');
      await reload();
    } catch (err) {
      onError?.(err instanceof Error ? err.message : 'Từ chối thất bại');
    } finally {
      setBusyId(null);
    }
  }

  if (loading) return <p className="muted">Đang tải inbox…</p>;
  if (!canApprove) return <p className="muted">Cần quyền GDKD (crm_leads assign) để duyệt HĐ.</p>;
  if (rows.length === 0) return <p className="muted">Không có HĐ chờ duyệt.</p>;

  return (
    <div style={{ display: 'grid', gap: '0.75rem' }}>
      {lastLifecycleId ? (
        <p style={{ color: 'var(--accent)', margin: 0 }}>
          Vừa promote lifecycle #{lastLifecycleId} —{' '}
          <Link href={`/crm/service-delivery/${lastLifecycleId}`} className="nav-link">
            Mở workflow →
          </Link>
        </p>
      ) : null}
      {rows.map((row) => (
        <div
          key={row.id}
          className="card"
          style={{ padding: '0.85rem', border: '1px solid var(--border)', borderRadius: 8 }}
        >
          <div style={{ fontWeight: 600 }}>{row.contract_title || `HĐ #${row.contract_id}`}</div>
          <div className="muted" style={{ fontSize: '0.85rem' }}>
            Lead:{' '}
            <Link href={`/crm/leads/${row.lead_id}`} className="nav-link">
              #{row.lead_id} {row.lead_name}
            </Link>
            · {row.amount_vnd.toLocaleString('vi-VN')} ₫ · AM: {row.requested_by}
          </div>
          {row.notes ? <p style={{ fontSize: '0.85rem', margin: '0.35rem 0' }}>{row.notes}</p> : null}
          <textarea
            placeholder="Lý do từ chối (nếu reject)"
            value={rejectNotes[row.id] ?? ''}
            onChange={(e) => setRejectNotes((prev) => ({ ...prev, [row.id]: e.target.value }))}
            rows={2}
            style={{
              width: '100%',
              marginTop: '0.5rem',
              padding: '0.4rem',
              borderRadius: 8,
              border: '1px solid var(--border)',
            }}
          />
          <div style={{ display: 'flex', gap: '0.5rem', marginTop: '0.5rem' }}>
            <button
              type="button"
              className="btn btn-sm btn-primary"
              disabled={busyId === row.id}
              onClick={() => void onApprove(row.id)}
            >
              Duyệt & ký Active
            </button>
            <button
              type="button"
              className="btn btn-sm btn-secondary"
              disabled={busyId === row.id}
              onClick={() => void onReject(row.id)}
            >
              Từ chối
            </button>
          </div>
        </div>
      ))}
    </div>
  );
}
