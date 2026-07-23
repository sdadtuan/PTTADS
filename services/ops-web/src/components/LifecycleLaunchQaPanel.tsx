'use client';

import { useCallback, useEffect, useState } from 'react';
import {
  fetchServiceLifecycleBudgetBrief,
  fetchServiceLifecycleCreativeBrief,
  fetchServiceLifecycleLaunchQa,
  patchServiceLifecycleLaunchQaChecklist,
  postServiceLifecycleBudgetSubmit,
  postServiceLifecycleCreativeSubmit,
  postServiceLifecycleLaunchQaStart,
} from '@/lib/api';
import { hasCap, type StoredStaffUser } from '@/lib/auth';

type ChecklistEntry = {
  label?: string;
  completed?: boolean;
  completed_by?: string;
  note?: string;
};

type LaunchQaPayload = {
  lifecycle_id: number;
  auto_start_enabled: boolean;
  has_context: boolean;
  client_id?: string;
  external_campaign_id?: string;
  campaign_name?: string;
  run: {
    id: string;
    status: string;
    launch_ready: boolean;
    checklist: Record<string, ChecklistEntry>;
    started_at: string;
    completed_at: string | null;
  } | null;
  progress: { total: number; completed: number; percent: number };
  gate: {
    ok: boolean;
    launch_ready: boolean;
    progress_percent: number;
    messages: string[];
  };
  message?: string | null;
};

type CreativeBriefPayload = {
  suggested_brief: { title: string; description: string; from_tmmt: boolean };
  creatives: Array<{
    id: string;
    title: string;
    status: string;
    version: number;
    submitted_at: string;
  }>;
  has_approved_creative: boolean;
  pending_creative?: { id: string; title: string; status: string; version: number } | null;
  latest_rejected?: { id: string; title: string; review_note: string | null; version: number } | null;
  portal_hint?: string | null;
  message?: string | null;
};

type BudgetBriefPayload = {
  suggested_budget_vnd: number | null;
  from_tmmt: boolean;
  has_executed_budget: boolean;
  pending_write?: {
    id: string;
    status: string;
    new_value: Record<string, unknown>;
    created_at: string;
  } | null;
  latest_execution_failed?: { id: string; execution_error: string | null } | null;
  pilot_check?: { warning?: string | null; stub_mode?: boolean } | null;
  hint?: string | null;
  message?: string | null;
};

interface Props {
  token: string;
  user: StoredStaffUser;
  lifecycleId: number;
}

const STATUS_LABEL: Record<string, string> = {
  pending_client: 'Chờ client duyệt',
  approved: 'Đã duyệt',
  rejected: 'Từ chối',
  withdrawn: 'Thu hồi',
};

export function LifecycleLaunchQaPanel({ token, user, lifecycleId }: Props) {
  const canEdit = hasCap(user, 'crm_board', 'edit');
  const [data, setData] = useState<LaunchQaPayload | null>(null);
  const [brief, setBrief] = useState<CreativeBriefPayload | null>(null);
  const [budgetBrief, setBudgetBrief] = useState<BudgetBriefPayload | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [message, setMessage] = useState('');
  const [saving, setSaving] = useState(false);
  const [creativeTitle, setCreativeTitle] = useState('');
  const [creativeDesc, setCreativeDesc] = useState('');
  const [assetUrl, setAssetUrl] = useState('');
  const [budgetVnd, setBudgetVnd] = useState('');

  const reload = useCallback(async () => {
    setLoading(true);
    setError('');
    try {
      const [qa, br, bb] = await Promise.all([
        fetchServiceLifecycleLaunchQa(token, lifecycleId),
        fetchServiceLifecycleCreativeBrief(token, lifecycleId),
        fetchServiceLifecycleBudgetBrief(token, lifecycleId),
      ]);
      setData(qa);
      setBrief(br);
      setBudgetBrief(bb);
      if (!creativeTitle && br.suggested_brief?.title) {
        setCreativeTitle(br.suggested_brief.title);
      }
      if (!creativeDesc && br.suggested_brief?.description) {
        setCreativeDesc(br.suggested_brief.description);
      }
      if (!budgetVnd && bb.suggested_budget_vnd != null) {
        setBudgetVnd(String(bb.suggested_budget_vnd));
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Tải Launch QA thất bại');
    } finally {
      setLoading(false);
    }
  }, [token, lifecycleId]);

  useEffect(() => {
    void reload();
  }, [reload]);

  async function onStart() {
    if (!canEdit) return;
    setSaving(true);
    setMessage('');
    try {
      await postServiceLifecycleLaunchQaStart(token, lifecycleId);
      setMessage('Đã khởi tạo Launch QA run');
      await reload();
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Khởi tạo thất bại');
    } finally {
      setSaving(false);
    }
  }

  async function toggleItem(key: string, completed: boolean) {
    if (!canEdit) return;
    setSaving(true);
    try {
      await patchServiceLifecycleLaunchQaChecklist(token, lifecycleId, key, { completed });
      await reload();
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Cập nhật checklist thất bại');
    } finally {
      setSaving(false);
    }
  }

  async function onSubmitCreative(e: React.FormEvent, resubmit = false) {
    e.preventDefault();
    if (!canEdit) return;
    setSaving(true);
    setMessage('');
    try {
      await postServiceLifecycleCreativeSubmit(token, lifecycleId, {
        title: creativeTitle.trim(),
        description: creativeDesc.trim(),
        asset_url: assetUrl.trim() || undefined,
        resubmit,
      });
      setMessage(resubmit ? 'Đã gửi creative v mới — chờ client duyệt' : 'Đã gửi creative — chờ client duyệt portal');
      await reload();
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Gửi creative thất bại');
    } finally {
      setSaving(false);
    }
  }

  async function onSubmitBudget(e: React.FormEvent) {
    e.preventDefault();
    if (!canEdit) return;
    const budget = Number(budgetVnd);
    if (!Number.isFinite(budget) || budget < 0) return;
    setSaving(true);
    setMessage('');
    setError('');
    try {
      const out = (await postServiceLifecycleBudgetSubmit(token, lifecycleId, budget)) as {
        pilot_check?: { warning?: string | null };
      };
      const warn = out.pilot_check?.warning;
      setMessage(
        warn
          ? `Đã gửi đổi budget — ${warn}`
          : 'Đã gửi đổi budget — chờ GDKD duyệt trên Campaign Write Hub',
      );
      await reload();
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Gửi budget thất bại');
    } finally {
      setSaving(false);
    }
  }

  if (loading) return <p className="muted">Đang tải Launch QA…</p>;
  if (error) return <p className="error">{error}</p>;
  if (!data) return null;

  const run = data.run;
  const checklist = run?.checklist ?? {};
  const entries = Object.entries(checklist);

  return (
    <div style={{ display: 'grid', gap: '1rem' }}>
      {message ? <p style={{ color: 'var(--accent)' }}>{message}</p> : null}

      <div className="card" style={{ padding: '1rem', display: 'grid', gap: '0.85rem' }}>
        <div>
          <h3 style={{ margin: 0, fontSize: '1rem' }}>Launch QA</h3>
          <p className="muted" style={{ margin: '0.35rem 0 0', fontSize: '0.85rem' }}>
            {data.auto_start_enabled ? 'Auto-start bật khi vào Deliver' : 'Auto-start tắt'}
            {data.external_campaign_id ? ` · Campaign ${data.external_campaign_id}` : ''}
            {' · '}
            <a href="/crm/launch-qa" className="nav-link">
              Launch board
            </a>
            {' · '}
            <a href="/crm/creatives" className="nav-link">
              Creative Hub
            </a>
            {' · '}
            <a href="/crm/campaign-writes" className="nav-link">
              Campaign Write
            </a>
          </p>
        </div>

        {!data.has_context ? (
          <p className="muted" style={{ margin: 0 }}>
            {data.message ?? 'Thiếu agency client hoặc campaign trên HĐ.'}
          </p>
        ) : !run ? (
          <>
            <p className="muted" style={{ margin: 0 }}>
              {data.message ?? 'Chưa có Launch QA run.'}
            </p>
            {canEdit ? (
              <button type="button" className="btn btn-sm" disabled={saving} onClick={() => void onStart()}>
                Khởi tạo Launch QA
              </button>
            ) : null}
          </>
        ) : (
          <>
            <div
              style={{
                display: 'grid',
                gridTemplateColumns: 'repeat(auto-fit, minmax(120px, 1fr))',
                gap: '0.5rem',
              }}
            >
              <div>
                <div className="muted" style={{ fontSize: '0.75rem' }}>
                  Run
                </div>
                <div style={{ fontWeight: 600 }}>
                  #{run.id.slice(0, 8)} · {run.status}
                </div>
              </div>
              <div>
                <div className="muted" style={{ fontSize: '0.75rem' }}>
                  Tiến độ
                </div>
                <div style={{ fontWeight: 600 }}>
                  {data.progress.completed}/{data.progress.total} · {data.progress.percent}%
                </div>
              </div>
              <div>
                <div className="muted" style={{ fontSize: '0.75rem' }}>
                  Launch ready
                </div>
                <div style={{ fontWeight: 600, color: run.launch_ready ? 'var(--accent)' : 'var(--danger)' }}>
                  {run.launch_ready ? '✓ Sẵn sàng' : 'Chưa'}
                </div>
              </div>
            </div>

            {!data.gate.ok && data.gate.messages.length > 0 ? (
              <p
                style={{
                  margin: 0,
                  padding: '0.5rem 0.65rem',
                  borderRadius: 8,
                  fontSize: '0.85rem',
                  border: '1px solid #c90',
                  background: 'rgba(255, 200, 0, 0.04)',
                  color: '#c90',
                }}
              >
                {data.gate.messages[0]}
              </p>
            ) : null}

            <ul style={{ margin: 0, padding: 0, listStyle: 'none', display: 'grid', gap: '0.4rem' }}>
              {entries.map(([key, item]) => (
                <li
                  key={key}
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
                    checked={Boolean(item.completed)}
                    disabled={!canEdit || saving || run.status !== 'in_progress'}
                    onChange={(e) => void toggleItem(key, e.target.checked)}
                  />
                  <div>
                    <strong>{item.label ?? key}</strong>
                    {item.note ? (
                      <p className="muted" style={{ margin: '0.2rem 0 0' }}>
                        {item.note}
                      </p>
                    ) : null}
                  </div>
                </li>
              ))}
            </ul>
          </>
        )}
      </div>

      <div className="card" style={{ padding: '1rem', display: 'grid', gap: '0.75rem' }}>
        <h3 style={{ margin: 0, fontSize: '1rem' }}>Meta budget write</h3>
        {budgetBrief?.message ? <p className="muted" style={{ margin: 0 }}>{budgetBrief.message}</p> : null}
        {budgetBrief?.hint ? (
          <p className="muted" style={{ margin: 0, fontSize: '0.85rem' }}>
            {budgetBrief.hint}
          </p>
        ) : null}
        {budgetBrief?.pilot_check?.warning ? (
          <p style={{ margin: 0, fontSize: '0.85rem', color: '#c90' }}>
            Pilot: {budgetBrief.pilot_check.warning}
          </p>
        ) : null}
        {budgetBrief?.pending_write ? (
          <p
            style={{
              margin: 0,
              padding: '0.5rem 0.65rem',
              borderRadius: 8,
              border: '1px solid #c90',
              fontSize: '0.85rem',
            }}
          >
            Chờ GDKD duyệt budget{' '}
            {Number(budgetBrief.pending_write.new_value?.daily_budget_vnd ?? 0).toLocaleString('vi-VN')} VND
          </p>
        ) : null}
        {budgetBrief?.latest_execution_failed && !budgetBrief.pending_write ? (
          <p
            style={{
              margin: 0,
              padding: '0.5rem 0.65rem',
              borderRadius: 8,
              border: '1px solid var(--danger, #c53030)',
              fontSize: '0.85rem',
            }}
          >
            Execution failed
            {budgetBrief.latest_execution_failed.execution_error
              ? `: ${budgetBrief.latest_execution_failed.execution_error}`
              : ''}
          </p>
        ) : null}
        {budgetBrief?.has_executed_budget ? (
          <p style={{ margin: 0, color: 'var(--accent)', fontSize: '0.85rem' }}>
            Đã có budget write executed — checklist budget_confirmed có thể đã auto-tick.
          </p>
        ) : null}
        {canEdit && data.has_context ? (
          <form onSubmit={(e) => void onSubmitBudget(e)} style={{ display: 'grid', gap: '0.5rem' }}>
            <label style={{ display: 'grid', gap: '0.3rem' }}>
              <span className="muted">
                Daily budget VND
                {budgetBrief?.from_tmmt ? ' (gợi ý từ TMMT)' : ''}
              </span>
              <input
                type="number"
                min={0}
                value={budgetVnd}
                onChange={(e) => setBudgetVnd(e.target.value)}
                disabled={saving}
                style={{
                  background: 'var(--bg)',
                  border: '1px solid var(--border)',
                  borderRadius: 8,
                  padding: '0.45rem 0.65rem',
                  color: 'var(--text)',
                }}
              />
            </label>
            <button type="submit" className="btn btn-sm" disabled={saving}>
              Gửi đổi budget Meta
            </button>
          </form>
        ) : null}
      </div>

      <div className="card" style={{ padding: '1rem', display: 'grid', gap: '0.75rem' }}>
        <h3 style={{ margin: 0, fontSize: '1rem' }}>Creative brief</h3>
        {brief?.message ? <p className="muted" style={{ margin: 0 }}>{brief.message}</p> : null}
        {brief?.portal_hint ? (
          <p className="muted" style={{ margin: 0, fontSize: '0.85rem' }}>
            {brief.portal_hint}
          </p>
        ) : null}

        {brief?.pending_creative ? (
          <p
            style={{
              margin: 0,
              padding: '0.5rem 0.65rem',
              borderRadius: 8,
              border: '1px solid #c90',
              fontSize: '0.85rem',
            }}
          >
            Đang chờ client duyệt: <strong>{brief.pending_creative.title}</strong> (v
            {brief.pending_creative.version})
          </p>
        ) : null}

        {brief?.latest_rejected && !brief.pending_creative ? (
          <div
            style={{
              margin: 0,
              padding: '0.5rem 0.65rem',
              borderRadius: 8,
              border: '1px solid var(--danger, #c53030)',
              fontSize: '0.85rem',
            }}
          >
            <p style={{ margin: '0 0 0.35rem' }}>
              Client từ chối v{brief.latest_rejected.version}
              {brief.latest_rejected.review_note ? `: ${brief.latest_rejected.review_note}` : ''}
            </p>
            {canEdit ? (
              <button
                type="button"
                className="btn btn-sm btn-secondary"
                disabled={saving}
                onClick={() => void onSubmitCreative({ preventDefault: () => {} } as React.FormEvent, true)}
              >
                Gửi lại creative (v+1)
              </button>
            ) : null}
          </div>
        ) : null}

        {brief?.creatives && brief.creatives.length > 0 ? (
          <div style={{ overflowX: 'auto' }}>
            <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: '0.85rem' }}>
              <thead>
                <tr className="muted">
                  <th style={{ textAlign: 'left', padding: '0.35rem' }}>Creative</th>
                  <th style={{ textAlign: 'left', padding: '0.35rem' }}>v</th>
                  <th style={{ textAlign: 'left', padding: '0.35rem' }}>Trạng thái</th>
                  <th style={{ textAlign: 'left', padding: '0.35rem' }}>Gửi lúc</th>
                </tr>
              </thead>
              <tbody>
                {brief.creatives.map((c) => (
                  <tr key={c.id} style={{ borderTop: '1px solid var(--border)' }}>
                    <td style={{ padding: '0.35rem' }}>{c.title}</td>
                    <td style={{ padding: '0.35rem' }}>{c.version}</td>
                    <td style={{ padding: '0.35rem' }}>{STATUS_LABEL[c.status] ?? c.status}</td>
                    <td style={{ padding: '0.35rem' }}>{c.submitted_at?.slice(0, 10) ?? '—'}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        ) : (
          <p className="muted" style={{ margin: 0 }}>
            Chưa có creative cho campaign này.
          </p>
        )}

        {canEdit && data.has_context ? (
          <form onSubmit={(e) => void onSubmitCreative(e, false)} style={{ display: 'grid', gap: '0.5rem' }}>
            <label style={{ display: 'grid', gap: '0.3rem' }}>
              <span className="muted">Tiêu đề</span>
              <input
                value={creativeTitle}
                onChange={(e) => setCreativeTitle(e.target.value)}
                disabled={saving}
                style={{
                  background: 'var(--bg)',
                  border: '1px solid var(--border)',
                  borderRadius: 8,
                  padding: '0.45rem 0.65rem',
                  color: 'var(--text)',
                }}
              />
            </label>
            <label style={{ display: 'grid', gap: '0.3rem' }}>
              <span className="muted">Mô tả / brief</span>
              <textarea
                value={creativeDesc}
                onChange={(e) => setCreativeDesc(e.target.value)}
                rows={3}
                disabled={saving}
                style={{
                  background: 'var(--bg)',
                  border: '1px solid var(--border)',
                  borderRadius: 8,
                  padding: '0.45rem 0.65rem',
                  color: 'var(--text)',
                }}
              />
            </label>
            <label style={{ display: 'grid', gap: '0.3rem' }}>
              <span className="muted">Asset URL (tuỳ chọn)</span>
              <input
                value={assetUrl}
                onChange={(e) => setAssetUrl(e.target.value)}
                disabled={saving}
                placeholder="https://..."
                style={{
                  background: 'var(--bg)',
                  border: '1px solid var(--border)',
                  borderRadius: 8,
                  padding: '0.45rem 0.65rem',
                  color: 'var(--text)',
                }}
              />
            </label>
            {brief?.suggested_brief?.from_tmmt ? (
              <p className="muted" style={{ margin: 0, fontSize: '0.8rem' }}>
                Gợi ý từ TMMT chính thức
              </p>
            ) : null}
            <button type="submit" className="btn btn-sm" disabled={saving || !creativeTitle.trim()}>
              Gửi creative (portal)
            </button>
          </form>
        ) : null}
      </div>
    </div>
  );
}
