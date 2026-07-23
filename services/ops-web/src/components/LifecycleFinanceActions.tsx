'use client';

import { useState } from 'react';
import { createServiceLifecycleExpense, createSvcPayment } from '@/lib/api';
import { hasCap, type StoredStaffUser } from '@/lib/auth';

type Props = {
  token: string;
  user: StoredStaffUser;
  lifecycleId: number;
  onSaved?: () => void;
  onError?: (msg: string) => void;
};

export function LifecycleFinanceActions({ token, user, lifecycleId, onSaved, onError }: Props) {
  const canEdit = hasCap(user, 'crm_board', 'edit');
  const [expTitle, setExpTitle] = useState('');
  const [expAmount, setExpAmount] = useState('');
  const [payAmount, setPayAmount] = useState('');
  const [payDate, setPayDate] = useState(() => new Date().toISOString().slice(0, 10));
  const [busy, setBusy] = useState(false);

  async function addExpense(e: React.FormEvent) {
    e.preventDefault();
    if (!canEdit) return;
    setBusy(true);
    try {
      await createServiceLifecycleExpense(token, lifecycleId, {
        title: expTitle.trim() || 'Chi phí delivery',
        category: 'khac',
        amount_vnd: Number(expAmount) || 0,
        expense_on: new Date().toISOString().slice(0, 10),
      });
      setExpTitle('');
      setExpAmount('');
      onSaved?.();
    } catch (err) {
      onError?.(err instanceof Error ? err.message : 'Ghi chi thất bại');
    } finally {
      setBusy(false);
    }
  }

  async function addPayment(e: React.FormEvent) {
    e.preventDefault();
    if (!canEdit) return;
    setBusy(true);
    try {
      await createSvcPayment(token, {
        lifecycle_id: lifecycleId,
        amount_vnd: Number(payAmount) || 0,
        received_on: payDate,
        status: 'received',
        notes: 'Ghi từ workflow SD',
      });
      setPayAmount('');
      onSaved?.();
    } catch (err) {
      onError?.(err instanceof Error ? err.message : 'Ghi thu thất bại');
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="card" style={{ padding: '1rem' }}>
      <h3 style={{ margin: '0 0 0.65rem', fontSize: '1rem' }}>Ghi chi / thu</h3>
      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '1rem' }}>
        <form onSubmit={(e) => void addExpense(e)} style={{ display: 'grid', gap: '0.4rem' }}>
          <span className="muted" style={{ fontSize: '0.85rem' }}>
            Chi delivery
          </span>
          <input
            placeholder="Mô tả"
            value={expTitle}
            onChange={(e) => setExpTitle(e.target.value)}
            disabled={!canEdit || busy}
            style={{ padding: '0.45rem', borderRadius: 8, border: '1px solid var(--border)' }}
          />
          <input
            type="number"
            placeholder="Số tiền VND"
            value={expAmount}
            onChange={(e) => setExpAmount(e.target.value)}
            disabled={!canEdit || busy}
            style={{ padding: '0.45rem', borderRadius: 8, border: '1px solid var(--border)' }}
          />
          <button type="submit" className="btn btn-sm" disabled={!canEdit || busy}>
            Ghi chi
          </button>
        </form>
        <form onSubmit={(e) => void addPayment(e)} style={{ display: 'grid', gap: '0.4rem' }}>
          <span className="muted" style={{ fontSize: '0.85rem' }}>
            Thu (AR)
          </span>
          <input
            type="number"
            placeholder="Số tiền VND"
            value={payAmount}
            onChange={(e) => setPayAmount(e.target.value)}
            disabled={!canEdit || busy}
            style={{ padding: '0.45rem', borderRadius: 8, border: '1px solid var(--border)' }}
          />
          <input
            type="date"
            value={payDate}
            onChange={(e) => setPayDate(e.target.value)}
            disabled={!canEdit || busy}
            style={{ padding: '0.45rem', borderRadius: 8, border: '1px solid var(--border)' }}
          />
          <button type="submit" className="btn btn-sm" disabled={!canEdit || busy}>
            Ghi thu
          </button>
        </form>
      </div>
    </div>
  );
}
