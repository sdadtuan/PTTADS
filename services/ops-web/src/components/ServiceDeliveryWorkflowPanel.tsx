'use client';

import { useCallback, useEffect, useState } from 'react';
import { ConsultBriefPanel } from '@/components/ConsultBriefPanel';
import {
  fetchServiceLifecycleAdvanceInfo,
  fetchServiceLifecycleMarketingPlan,
  fetchServiceLifecycleProgress,
  fetchServiceLifecycleTasks,
  patchServiceLifecycle,
  patchServiceLifecycleTask,
} from '@/lib/api';
import { hasCap, type StoredStaffUser } from '@/lib/auth';

const STAGES = ['lead', 'consult', 'proposal', 'onboard', 'deliver', 'handover', 'retain'] as const;
const STAGE_LABELS: Record<string, string> = {
  lead: 'Lead',
  consult: 'Tư vấn',
  proposal: 'Báo giá',
  onboard: 'Onboard',
  deliver: 'Triển khai',
  handover: 'Bàn giao',
  retain: 'Giữ chân',
};

type PaymentGate = {
  ok?: boolean;
  requires_confirm?: boolean;
  outstanding_vnd?: number;
  messages?: string[];
};

type LaunchQaGate = {
  ok?: boolean;
  warn_only?: boolean;
  launch_ready?: boolean;
  progress_percent?: number;
  progress_completed?: number;
  progress_total?: number;
  requires_confirm?: boolean;
  messages?: string[];
};

type TaskRow = {
  id: number;
  title: string;
  description: string;
  is_done: boolean;
  notes: string;
};

type Props = {
  token: string;
  user: StoredStaffUser;
  lifecycleId: number;
  initialStage: string;
  onStageChanged?: (stage: string) => void;
  onFinanceRefresh?: () => void;
  onOpenTmmtTab?: () => void;
  onOpenFinanceTab?: () => void;
  onOpenLaunchQaTab?: () => void;
};

export function ServiceDeliveryWorkflowPanel({
  token,
  user,
  lifecycleId,
  initialStage,
  onStageChanged,
  onFinanceRefresh,
  onOpenTmmtTab,
  onOpenFinanceTab,
  onOpenLaunchQaTab,
}: Props) {
  const canEdit = hasCap(user, 'crm_board', 'edit');
  const [tab, setTab] = useState(initialStage);
  const [tasks, setTasks] = useState<Record<string, TaskRow[]>>({});
  const [progress, setProgress] = useState<Record<string, { total: number; done: number; pct: number }>>({});
  const [advance, setAdvance] = useState<Record<string, unknown>>({});
  const [tmmtValidation, setTmmtValidation] = useState<{ ok: boolean; messages: string[] } | null>(null);
  const [financeConfirm, setFinanceConfirm] = useState(false);
  const [launchQaConfirm, setLaunchQaConfirm] = useState(false);
  const [error, setError] = useState('');
  const [message, setMessage] = useState('');
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);

  useEffect(() => {
    setTab(initialStage);
  }, [initialStage]);

  const reload = useCallback(async () => {
    setLoading(true);
    setError('');
    try {
      const [taskOut, progOut, advOut] = await Promise.all([
        fetchServiceLifecycleTasks(token, lifecycleId),
        fetchServiceLifecycleProgress(token, lifecycleId),
        fetchServiceLifecycleAdvanceInfo(token, lifecycleId),
      ]);
      setTasks(taskOut.tasks as Record<string, TaskRow[]>);
      setProgress(progOut.progress);
      setAdvance(advOut);
      if (tab === 'onboard') {
        const mp = await fetchServiceLifecycleMarketingPlan(token, lifecycleId);
        setTmmtValidation(mp.validation);
      } else {
        setTmmtValidation(null);
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Tải workflow thất bại');
    } finally {
      setLoading(false);
    }
  }, [token, lifecycleId, tab]);

  useEffect(() => {
    void reload();
  }, [reload]);

  async function toggleTask(task: TaskRow) {
    if (!canEdit) return;
    setSaving(true);
    try {
      await patchServiceLifecycleTask(token, lifecycleId, task.id, { is_done: !task.is_done });
      await reload();
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Cập nhật task thất bại');
    } finally {
      setSaving(false);
    }
  }

  const paymentGate = advance.payment_gate as PaymentGate | undefined;
  const launchQaGate = advance.launch_qa_gate as LaunchQaGate | undefined;
  const showPaymentGate =
    tab === 'handover' &&
    String(advance.current_stage ?? '') === 'handover' &&
    String(advance.next_stage ?? '') === 'retain' &&
    Boolean(paymentGate?.requires_confirm);

  const showLaunchQaGate =
    tab === 'deliver' &&
    String(advance.current_stage ?? '') === 'deliver' &&
    String(advance.next_stage ?? '') === 'handover' &&
    Boolean(launchQaGate?.requires_confirm);

  async function advanceForward() {
    const nxt = String(advance.next_stage ?? '');
    if (!nxt || !canEdit) return;
    if (showPaymentGate && !financeConfirm) return;
    if (showLaunchQaGate && !launchQaConfirm) return;
    setSaving(true);
    setMessage('');
    setError('');
    try {
      await patchServiceLifecycle(token, lifecycleId, {
        stage: nxt,
        finance_confirm: showPaymentGate && financeConfirm ? true : undefined,
        launch_qa_confirm: showLaunchQaGate && launchQaConfirm ? true : undefined,
      });
      setTab(nxt);
      setFinanceConfirm(false);
      setLaunchQaConfirm(false);
      onStageChanged?.(nxt);
      setMessage(`Đã chuyển → ${STAGE_LABELS[nxt] ?? nxt}`);
      onFinanceRefresh?.();
      await reload();
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Chuyển stage thất bại');
    } finally {
      setSaving(false);
    }
  }

  const tabTasks = tasks[tab] ?? [];
  const tabProg = progress[tab] ?? { total: 0, done: 0, pct: 100 };
  const showTmmtGate =
    tab === 'onboard' &&
    tmmtValidation &&
    String(advance.current_stage ?? '') === 'onboard' &&
    String(advance.next_stage ?? '') === 'deliver';

  const onCurrentTab = tab === String(advance.current_stage ?? '');
  const canShowAdvanceButton =
    canEdit &&
    onCurrentTab &&
    (Boolean(advance.can_advance_forward) ||
      (showPaymentGate && financeConfirm) ||
      (showLaunchQaGate && launchQaConfirm));

  const workflowCard = (
    <div className="card" style={{ padding: '1rem' }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', gap: '0.5rem' }}>
        <h3 style={{ margin: 0, fontSize: '1rem' }}>{STAGE_LABELS[tab] ?? tab}</h3>
        <span className="muted">{tabProg.done}/{tabProg.total} task · {tabProg.pct}%</span>
      </div>

      {Boolean(advance.block_reason) && onCurrentTab && !showPaymentGate && !showLaunchQaGate ? (
        <p className="error" style={{ marginTop: '0.5rem' }}>
          {String(advance.block_reason)}
        </p>
      ) : null}

      {showTmmtGate && !tmmtValidation.ok ? (
        <div
          style={{
            marginTop: '0.75rem',
            padding: '0.65rem 0.75rem',
            borderRadius: 8,
            border: '1px solid var(--accent)',
            background: 'rgba(255,255,255,0.02)',
          }}
        >
          <p className="error" style={{ margin: '0 0 0.35rem', fontWeight: 600 }}>Gate TMMT chưa pass</p>
          <ul className="error" style={{ margin: '0 0 0.5rem', paddingLeft: '1.1rem' }}>
            {tmmtValidation.messages.slice(0, 3).map((m) => (
              <li key={m}>{m}</li>
            ))}
          </ul>
          {onOpenTmmtTab ? (
            <button type="button" className="btn btn-sm btn-secondary" onClick={onOpenTmmtTab}>
              Mở tab TMMT chính thức
            </button>
          ) : null}
        </div>
      ) : null}

      {showTmmtGate && tmmtValidation.ok ? (
        <p style={{ color: 'var(--accent)', marginTop: '0.75rem' }}>Gate TMMT ✓ — có thể chuyển Deliver</p>
      ) : null}

      {showLaunchQaGate ? (
        <div
          style={{
            marginTop: '0.75rem',
            padding: '0.65rem 0.75rem',
            borderRadius: 8,
            border: '1px solid #c90',
            background: 'rgba(255, 200, 0, 0.04)',
          }}
        >
          <p style={{ margin: '0 0 0.35rem', fontWeight: 600, color: '#c90' }}>
            Gate Launch QA — chưa launch_ready
          </p>
          <p style={{ margin: '0 0 0.5rem', fontSize: '0.9rem' }}>
            {(launchQaGate?.messages ?? [])[0] ??
              `Checklist ${launchQaGate?.progress_completed ?? 0}/${launchQaGate?.progress_total ?? 0} — hoàn thiện trước bàn giao`}
          </p>
          {onOpenLaunchQaTab ? (
            <button type="button" className="btn btn-sm btn-secondary" style={{ marginBottom: '0.5rem' }} onClick={onOpenLaunchQaTab}>
              Mở tab Launch QA
            </button>
          ) : null}
          <label style={{ display: 'flex', gap: '0.4rem', alignItems: 'flex-start', fontSize: '0.9rem' }}>
            <input
              type="checkbox"
              checked={launchQaConfirm}
              onChange={(e) => setLaunchQaConfirm(e.target.checked)}
              disabled={!canEdit || saving}
            />
            <span>
              Xác nhận chuyển sang <strong>Bàn giao</strong> dù Launch QA chưa launch_ready (AM/QA chịu trách nhiệm)
            </span>
          </label>
        </div>
      ) : null}

      {showPaymentGate ? (
        <div
          style={{
            marginTop: '0.75rem',
            padding: '0.65rem 0.75rem',
            borderRadius: 8,
            border: '1px solid #c90',
            background: 'rgba(255, 200, 0, 0.04)',
          }}
        >
          <p style={{ margin: '0 0 0.35rem', fontWeight: 600, color: '#c90' }}>Gate Payment — còn công nợ HĐ</p>
          <p style={{ margin: '0 0 0.5rem', fontSize: '0.9rem' }}>
            {(paymentGate?.messages ?? [])[0] ??
              `Còn ${Number(paymentGate?.outstanding_vnd ?? 0).toLocaleString('vi-VN')} VND chưa thu`}
          </p>
          {onOpenFinanceTab ? (
            <button type="button" className="btn btn-sm btn-secondary" style={{ marginBottom: '0.5rem' }} onClick={onOpenFinanceTab}>
              Mở tab Tài chính
            </button>
          ) : null}
          <label style={{ display: 'flex', gap: '0.4rem', alignItems: 'flex-start', fontSize: '0.9rem' }}>
            <input
              type="checkbox"
              checked={financeConfirm}
              onChange={(e) => setFinanceConfirm(e.target.checked)}
              disabled={!canEdit || saving}
            />
            <span>
              Xác nhận chuyển sang <strong>Giữ chân</strong> dù còn công nợ (AM/SP chịu trách nhiệm thu hồi)
            </span>
          </label>
        </div>
      ) : null}

      <ul style={{ margin: '0.75rem 0 0', padding: 0, listStyle: 'none', display: 'grid', gap: '0.4rem' }}>
        {tabTasks.length === 0 ? <li className="muted">Không có task.</li> : null}
        {tabTasks.map((task) => (
          <li
            key={task.id}
            style={{
              display: 'flex',
              gap: '0.5rem',
              alignItems: 'flex-start',
              padding: '0.45rem',
              border: '1px solid var(--border)',
              borderRadius: 8,
            }}
          >
            <input
              type="checkbox"
              checked={task.is_done}
              disabled={!canEdit || saving}
              onChange={() => void toggleTask(task)}
            />
            <div>
              <strong>{task.title}</strong>
              {task.description ? <p className="muted" style={{ margin: '0.2rem 0 0' }}>{task.description}</p> : null}
            </div>
          </li>
        ))}
      </ul>

      {canShowAdvanceButton ? (
        <button type="button" className="btn btn-sm" style={{ marginTop: '0.75rem' }} disabled={saving} onClick={() => void advanceForward()}>
          Chuyển → {STAGE_LABELS[String(advance.next_stage)] ?? String(advance.next_stage)}
        </button>
      ) : null}
    </div>
  );

  return (
    <div style={{ display: 'grid', gap: '1rem' }}>
      {loading ? <p className="muted">Đang tải workflow…</p> : null}
      {error ? <p className="error">{error}</p> : null}
      {message ? <p style={{ color: 'var(--accent)' }}>{message}</p> : null}

      <div style={{ display: 'flex', flexWrap: 'wrap', gap: '0.35rem' }}>
        {STAGES.map((s) => (
          <button
            key={s}
            type="button"
            className={tab === s ? 'btn btn-sm' : 'btn btn-sm btn-ghost'}
            onClick={() => setTab(s)}
          >
            {STAGE_LABELS[s] ?? s} ({progress[s]?.done ?? 0}/{progress[s]?.total ?? 0})
          </button>
        ))}
      </div>

      {tab === 'consult' ? (
        <div style={{ display: 'grid', gridTemplateColumns: 'minmax(0, 1fr) min(320px, 38%)', gap: '1rem', alignItems: 'start' }}>
          {workflowCard}
          <ConsultBriefPanel token={token} user={user} lifecycleId={lifecycleId} onPrefilled={() => void reload()} />
        </div>
      ) : (
        workflowCard
      )}
    </div>
  );
}
