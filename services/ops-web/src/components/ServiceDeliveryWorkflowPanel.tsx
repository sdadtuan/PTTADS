'use client';

import { useCallback, useEffect, useState } from 'react';
import {
  fetchServiceLifecycleAdvanceInfo,
  fetchServiceLifecycleFinanceSummary,
  fetchServiceLifecycleMarketingPlan,
  fetchServiceLifecyclePresalesSummary,
  fetchServiceLifecycleProgress,
  fetchServiceLifecycleTasks,
  patchServiceLifecycle,
  patchServiceLifecycleMarketingPlan,
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
};

export function ServiceDeliveryWorkflowPanel({
  token,
  user,
  lifecycleId,
  initialStage,
  onStageChanged,
}: Props) {
  const canEdit = hasCap(user, 'crm_board', 'edit');
  const [tab, setTab] = useState(initialStage);
  const [tasks, setTasks] = useState<Record<string, TaskRow[]>>({});
  const [progress, setProgress] = useState<Record<string, { total: number; done: number; pct: number }>>({});
  const [advance, setAdvance] = useState<Record<string, unknown>>({});
  const [tmmt, setTmmt] = useState<{ plan: Record<string, unknown> | null; validation: { ok: boolean; messages: string[] } } | null>(null);
  const [finance, setFinance] = useState<Record<string, unknown> | null>(null);
  const [presales, setPresales] = useState<Record<string, unknown> | null>(null);
  const [error, setError] = useState('');
  const [message, setMessage] = useState('');
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);

  const reload = useCallback(async () => {
    setLoading(true);
    setError('');
    try {
      const [taskOut, progOut, advOut, finOut, psOut] = await Promise.all([
        fetchServiceLifecycleTasks(token, lifecycleId),
        fetchServiceLifecycleProgress(token, lifecycleId),
        fetchServiceLifecycleAdvanceInfo(token, lifecycleId),
        fetchServiceLifecycleFinanceSummary(token, lifecycleId),
        fetchServiceLifecyclePresalesSummary(token, lifecycleId),
      ]);
      setTasks(taskOut.tasks as Record<string, TaskRow[]>);
      setProgress(progOut.progress);
      setAdvance(advOut);
      setFinance(finOut);
      setPresales(psOut);
      if (tab === 'onboard' || tab === 'deliver') {
        const mp = await fetchServiceLifecycleMarketingPlan(token, lifecycleId);
        setTmmt(mp);
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

  async function advanceForward() {
    const nxt = String(advance.next_stage ?? '');
    if (!nxt || !canEdit) return;
    setSaving(true);
    setMessage('');
    setError('');
    try {
      await patchServiceLifecycle(token, lifecycleId, { stage: nxt });
      setTab(nxt);
      onStageChanged?.(nxt);
      setMessage(`Đã chuyển → ${STAGE_LABELS[nxt] ?? nxt}`);
      await reload();
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Chuyển stage thất bại');
    } finally {
      setSaving(false);
    }
  }

  async function saveTmmtSummary(value: string) {
    if (!tmmt?.plan || !canEdit) return;
    setSaving(true);
    try {
      const sf = JSON.parse(String(tmmt.plan.strategy_framework_json ?? '{}')) as Record<string, string>;
      sf.target_market = value;
      const out = await patchServiceLifecycleMarketingPlan(token, lifecycleId, {
        strategy_framework_json: JSON.stringify(sf),
      });
      setTmmt(out);
      await reload();
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Lưu TMMT thất bại');
    } finally {
      setSaving(false);
    }
  }

  const tabTasks = tasks[tab] ?? [];
  const tabProg = progress[tab] ?? { total: 0, done: 0, pct: 100 };

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

      <div className="card" style={{ padding: '1rem' }}>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', gap: '0.5rem' }}>
          <h3 style={{ margin: 0, fontSize: '1rem' }}>{STAGE_LABELS[tab] ?? tab}</h3>
          <span className="muted">{tabProg.done}/{tabProg.total} task · {tabProg.pct}%</span>
        </div>

        {Boolean(advance.block_reason) && tab === String(advance.current_stage ?? '') ? (
          <p className="error" style={{ marginTop: '0.5rem' }}>
            {String(advance.block_reason)}
          </p>
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

        {canEdit && Boolean(advance.can_advance_forward) && tab === String(advance.current_stage ?? '') ? (
          <button type="button" className="btn btn-sm" style={{ marginTop: '0.75rem' }} disabled={saving} onClick={() => void advanceForward()}>
            Chuyển → {STAGE_LABELS[String(advance.next_stage)] ?? String(advance.next_stage)}
          </button>
        ) : null}
      </div>

      {(tab === 'onboard' || tab === 'deliver') && tmmt ? (
        <div className="card" style={{ padding: '1rem' }}>
          <h3 style={{ margin: '0 0 0.5rem', fontSize: '1rem' }}>TMMT chính thức</h3>
          {!tmmt.validation.ok ? (
            <ul className="error" style={{ margin: '0 0 0.5rem', paddingLeft: '1.1rem' }}>
              {tmmt.validation.messages.map((m) => (
                <li key={m}>{m}</li>
              ))}
            </ul>
          ) : (
            <p style={{ color: 'var(--accent)', margin: '0 0 0.5rem' }}>Gate TMMT ✓ — có thể chuyển Deliver</p>
          )}
          <label style={{ display: 'grid', gap: '0.35rem' }}>
            <span className="muted">TMMT tóm tắt (target_market)</span>
            <textarea
              rows={2}
              disabled={!canEdit || saving}
              defaultValue={(() => {
                try {
                  const sf = JSON.parse(String(tmmt.plan?.strategy_framework_json ?? '{}')) as Record<string, string>;
                  return sf.target_market ?? '';
                } catch {
                  return '';
                }
              })()}
              onBlur={(e) => void saveTmmtSummary(e.target.value)}
              style={{
                background: 'var(--bg)',
                border: '1px solid var(--border)',
                borderRadius: 8,
                padding: '0.55rem 0.75rem',
                color: 'var(--text)',
              }}
            />
          </label>
        </div>
      ) : null}

      <div className="card" style={{ padding: '1rem' }}>
        <h3 style={{ margin: '0 0 0.5rem', fontSize: '1rem' }}>Tài chính</h3>
        {finance ? (
          <p className="muted" style={{ margin: 0 }}>
            Nhận: {Number(finance.received_revenue ?? 0).toLocaleString('vi-VN')} · Chi delivery:{' '}
            {Number(finance.delivery_expenses ?? 0).toLocaleString('vi-VN')} · Pre-sales:{' '}
            {Number(finance.presales_expenses ?? 0).toLocaleString('vi-VN')} · Lợi nhuận:{' '}
            {Number(finance.profit_vnd ?? 0).toLocaleString('vi-VN')}
          </p>
        ) : null}
        {presales && Array.isArray(presales.presales_expenses) && presales.presales_expenses.length > 0 ? (
          <p className="muted" style={{ margin: '0.5rem 0 0' }}>
            {presales.presales_expenses.length} khoản chi pre-sales đã link lifecycle
          </p>
        ) : null}
      </div>
    </div>
  );
}
