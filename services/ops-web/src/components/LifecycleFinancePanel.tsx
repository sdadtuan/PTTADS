'use client';

import { useCallback, useEffect, useState } from 'react';
import {
  createServiceLifecycleExpense,
  createSvcPayment,
  fetchServiceLifecycleFinanceSummary,
  fetchServiceLifecyclePayments,
  fetchServiceLifecyclePresalesSummary,
} from '@/lib/api';
import { hasCap, type StoredStaffUser } from '@/lib/auth';

type FinanceSummary = {
  expected_revenue?: number;
  received_revenue?: number;
  pending_revenue?: number;
  ar_pending_vnd?: number;
  ar_overdue_vnd?: number;
  outstanding_vnd?: number;
  delivery_expenses?: number;
  presales_expenses?: number;
  profit_vnd?: number;
  margin_pct?: number;
};

type ExpenseRow = {
  id?: number;
  title?: string;
  category?: string;
  amount_vnd?: number;
  expense_on?: string;
  cost_phase?: string;
};

type PaymentRow = {
  id: number;
  amount_vnd: number;
  received_on: string;
  status: string;
  notes: string;
};

interface Props {
  token: string;
  user: StoredStaffUser;
  lifecycleId: number;
  onSaved?: () => void;
}

function fmt(v: number | undefined): string {
  return Number(v ?? 0).toLocaleString('vi-VN');
}

export function LifecycleFinancePanel({ token, user, lifecycleId, onSaved }: Props) {
  const canEdit = hasCap(user, 'crm_board', 'edit');
  const [summary, setSummary] = useState<FinanceSummary | null>(null);
  const [presales, setPresales] = useState<{
    presales_expenses?: ExpenseRow[];
    delivery_expenses?: ExpenseRow[];
    presales_total_vnd?: number;
    delivery_total_vnd?: number;
  } | null>(null);
  const [payments, setPayments] = useState<PaymentRow[]>([]);
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  const [message, setMessage] = useState('');
  const [expTitle, setExpTitle] = useState('');
  const [expAmount, setExpAmount] = useState('');
  const [payAmount, setPayAmount] = useState('');
  const [payDate, setPayDate] = useState(() => new Date().toISOString().slice(0, 10));

  const reload = useCallback(async () => {
    setLoading(true);
    try {
      const [fin, ps, pay] = await Promise.all([
        fetchServiceLifecycleFinanceSummary(token, lifecycleId),
        fetchServiceLifecyclePresalesSummary(token, lifecycleId),
        fetchServiceLifecyclePayments(token, lifecycleId),
      ]);
      setSummary(fin as FinanceSummary);
      setPresales(ps as typeof presales);
      setPayments((pay.payments ?? []) as PaymentRow[]);
      setError('');
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Tải tài chính thất bại');
    } finally {
      setLoading(false);
    }
  }, [token, lifecycleId]);

  useEffect(() => {
    void reload();
  }, [reload]);

  async function addExpense(e: React.FormEvent) {
    e.preventDefault();
    if (!canEdit) return;
    setBusy(true);
    setMessage('');
    try {
      await createServiceLifecycleExpense(token, lifecycleId, {
        title: expTitle.trim() || 'Chi phí delivery',
        category: 'khac',
        amount_vnd: Number(expAmount) || 0,
        expense_on: new Date().toISOString().slice(0, 10),
      });
      setExpTitle('');
      setExpAmount('');
      setMessage('Đã ghi chi delivery');
      onSaved?.();
      await reload();
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Ghi chi thất bại');
    } finally {
      setBusy(false);
    }
  }

  async function addPayment(e: React.FormEvent) {
    e.preventDefault();
    if (!canEdit) return;
    setBusy(true);
    setMessage('');
    try {
      await createSvcPayment(token, {
        lifecycle_id: lifecycleId,
        amount_vnd: Number(payAmount) || 0,
        received_on: payDate,
        status: 'received',
        notes: 'Ghi từ tab Tài chính SD',
      });
      setPayAmount('');
      setMessage('Đã ghi thu AR');
      onSaved?.();
      await reload();
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Ghi thu thất bại');
    } finally {
      setBusy(false);
    }
  }

  const outstanding = Number(summary?.outstanding_vnd ?? 0);

  return (
    <div className="card" style={{ padding: '1rem', display: 'grid', gap: '1rem' }}>
      <div>
        <h3 style={{ margin: 0, fontSize: '1rem' }}>Tài chính lifecycle</h3>
        <p className="muted" style={{ margin: '0.35rem 0 0' }}>
          HĐ · thu · chi · lợi nhuận · công nợ (BC-09 Payment @ Handover→Retain)
        </p>
      </div>

      {loading ? <p className="muted">Đang tải…</p> : null}
      {error ? <p className="error">{error}</p> : null}
      {message ? <p style={{ color: 'var(--accent)' }}>{message}</p> : null}

      {summary ? (
        <div
          style={{
            display: 'grid',
            gridTemplateColumns: 'repeat(auto-fit, minmax(140px, 1fr))',
            gap: '0.65rem',
          }}
        >
          <Kpi label="Giá trị HĐ" value={`${fmt(summary.expected_revenue)} ₫`} />
          <Kpi label="Đã thu" value={`${fmt(summary.received_revenue)} ₫`} accent />
          <Kpi
            label="Công nợ HĐ"
            value={`${fmt(outstanding)} ₫`}
            warn={outstanding > 0}
          />
          <Kpi label="Chi delivery" value={`${fmt(summary.delivery_expenses)} ₫`} />
          <Kpi label="Chi pre-sales" value={`${fmt(summary.presales_expenses)} ₫`} />
          <Kpi label="Lợi nhuận" value={`${fmt(summary.profit_vnd)} ₫`} />
          <Kpi label="Margin" value={`${Number(summary.margin_pct ?? 0).toFixed(1)}%`} />
          <Kpi label="AR pending" value={`${fmt(summary.ar_pending_vnd)} ₫`} />
          <Kpi label="AR quá hạn" value={`${fmt(summary.ar_overdue_vnd)} ₫`} warn={Number(summary.ar_overdue_vnd) > 0} />
        </div>
      ) : null}

      {canEdit ? (
        <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '1rem' }}>
          <form onSubmit={(e) => void addExpense(e)} style={{ display: 'grid', gap: '0.4rem' }}>
            <span className="muted" style={{ fontSize: '0.85rem' }}>
              Ghi chi delivery
            </span>
            <input
              placeholder="Mô tả"
              value={expTitle}
              onChange={(e) => setExpTitle(e.target.value)}
              disabled={busy}
              style={{ padding: '0.45rem', borderRadius: 8, border: '1px solid var(--border)' }}
            />
            <input
              type="number"
              placeholder="Số tiền VND"
              value={expAmount}
              onChange={(e) => setExpAmount(e.target.value)}
              disabled={busy}
              style={{ padding: '0.45rem', borderRadius: 8, border: '1px solid var(--border)' }}
            />
            <button type="submit" className="btn btn-sm" disabled={busy}>
              Ghi chi
            </button>
          </form>
          <form onSubmit={(e) => void addPayment(e)} style={{ display: 'grid', gap: '0.4rem' }}>
            <span className="muted" style={{ fontSize: '0.85rem' }}>
              Ghi thu (AR received)
            </span>
            <input
              type="number"
              placeholder="Số tiền VND"
              value={payAmount}
              onChange={(e) => setPayAmount(e.target.value)}
              disabled={busy}
              style={{ padding: '0.45rem', borderRadius: 8, border: '1px solid var(--border)' }}
            />
            <input
              type="date"
              value={payDate}
              onChange={(e) => setPayDate(e.target.value)}
              disabled={busy}
              style={{ padding: '0.45rem', borderRadius: 8, border: '1px solid var(--border)' }}
            />
            <button type="submit" className="btn btn-sm" disabled={busy}>
              Ghi thu
            </button>
          </form>
        </div>
      ) : null}

      {(presales?.presales_expenses?.length ?? 0) > 0 ? (
        <ExpenseTable title="Chi phí pre-sales (cohort)" rows={presales!.presales_expenses!} />
      ) : null}

      {(presales?.delivery_expenses?.length ?? 0) > 0 ? (
        <ExpenseTable title="Chi phí delivery" rows={presales!.delivery_expenses!} />
      ) : null}

      {payments.length > 0 ? (
        <div>
          <h4 style={{ margin: '0 0 0.5rem', fontSize: '0.95rem' }}>Lịch sử thu</h4>
          <table style={{ width: '100%', fontSize: '0.9rem', borderCollapse: 'collapse' }}>
            <thead>
              <tr className="muted">
                <th style={{ textAlign: 'left', padding: '0.35rem' }}>Ngày</th>
                <th style={{ textAlign: 'right', padding: '0.35rem' }}>Số tiền</th>
                <th style={{ textAlign: 'left', padding: '0.35rem' }}>Trạng thái</th>
              </tr>
            </thead>
            <tbody>
              {payments.map((p) => (
                <tr key={p.id}>
                  <td style={{ padding: '0.35rem' }}>{p.received_on}</td>
                  <td style={{ padding: '0.35rem', textAlign: 'right' }}>{fmt(p.amount_vnd)} ₫</td>
                  <td style={{ padding: '0.35rem' }}>{p.status}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      ) : null}
    </div>
  );
}

function Kpi({
  label,
  value,
  accent,
  warn,
}: {
  label: string;
  value: string;
  accent?: boolean;
  warn?: boolean;
}) {
  return (
    <div
      style={{
        padding: '0.55rem 0.65rem',
        border: `1px solid ${warn ? 'var(--accent)' : 'var(--border)'}`,
        borderRadius: 8,
      }}
    >
      <div className="muted" style={{ fontSize: '0.78rem' }}>
        {label}
      </div>
      <div style={{ fontWeight: 600, color: accent ? 'var(--accent)' : warn ? 'var(--accent)' : undefined }}>
        {value}
      </div>
    </div>
  );
}

function ExpenseTable({ title, rows }: { title: string; rows: ExpenseRow[] }) {
  return (
    <div>
      <h4 style={{ margin: '0 0 0.5rem', fontSize: '0.95rem' }}>{title}</h4>
      <ul style={{ margin: 0, paddingLeft: '1.1rem', fontSize: '0.9rem' }}>
        {rows.map((r) => (
          <li key={String(r.id ?? r.title)}>
            {r.title ?? '—'} · {Number(r.amount_vnd ?? 0).toLocaleString('vi-VN')} ₫
            {r.expense_on ? ` · ${r.expense_on}` : ''}
          </li>
        ))}
      </ul>
    </div>
  );
}
