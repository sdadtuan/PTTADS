'use client';

import Link from 'next/link';
import type { AgencyClient, OnboardingItem, OnboardingSummaryResponse } from '@/lib/api';

type Props = {
  client: AgencyClient;
  summary: OnboardingSummaryResponse;
  canWrite: boolean;
  busy: boolean;
  onToggleItem: (item: OnboardingItem) => void;
  onActivate: (force: boolean) => void;
  onNudgeWorkflow: () => void;
  onStartWorkflow: () => void;
};

function workflowLabel(status: string, found: boolean, temporalEnabled: boolean): string {
  if (!temporalEnabled) return 'Temporal tắt (dev/stub)';
  if (!found || status === 'NOT_FOUND') return 'Chưa khởi tạo';
  if (status === 'RUNNING') return 'Đang chạy';
  if (status === 'COMPLETED') return 'Hoàn tất';
  if (status === 'FAILED' || status === 'TERMINATED') return 'Lỗi / dừng';
  return status;
}

function workflowBadgeClass(status: string, found: boolean, temporalEnabled: boolean): string {
  if (!temporalEnabled) return 'onboarding-wf-badge is-stub';
  if (!found || status === 'NOT_FOUND') return 'onboarding-wf-badge is-idle';
  if (status === 'RUNNING') return 'onboarding-wf-badge is-running';
  if (status === 'COMPLETED') return 'onboarding-wf-badge is-done';
  return 'onboarding-wf-badge is-warn';
}

export function ClientOnboardingWidget({
  client,
  summary,
  canWrite,
  busy,
  onToggleItem,
  onActivate,
  onNudgeWorkflow,
  onStartWorkflow,
}: Props) {
  const { progress, workflow, linked_lifecycles: lifecycles, strict_onboarding: strictOnboarding } = summary;
  const activateDisabled =
    !canWrite || client.status === 'active' || (progress.percent < 100 && strictOnboarding);
  const wfLabel = workflowLabel(workflow.status, workflow.found, workflow.temporal_enabled);
  const stepWorkflowDone = workflow.found && workflow.status === 'COMPLETED';
  const stepChecklistDone = progress.percent >= 100;
  const stepActiveDone = client.status === 'active';

  return (
    <div className="onboarding-widget">
      <div className="onboarding-widget-header">
        <div>
          <h3 style={{ margin: 0, fontSize: '1rem' }}>Client onboarding</h3>
          <p className="muted" style={{ margin: '0.25rem 0 0' }}>
            Checklist agency + Temporal auto-activate khi đạt 100%
          </p>
        </div>
        <span className={workflowBadgeClass(workflow.status, workflow.found, workflow.temporal_enabled)}>
          {wfLabel}
        </span>
      </div>

      <div className="onboarding-timeline" aria-label="Tiến trình onboarding">
        <div className={`onboarding-step ${workflow.found ? 'is-done' : workflow.temporal_enabled ? 'is-current' : ''}`}>
          <span className="onboarding-step-dot" />
          <div>
            <strong>Workflow</strong>
            <p className="muted" style={{ margin: '0.15rem 0 0' }}>
              {workflow.workflow_id || '—'}
              {workflow.run_id ? ` · run ${workflow.run_id.slice(0, 8)}…` : ''}
            </p>
          </div>
        </div>
        <div className={`onboarding-step ${stepChecklistDone ? 'is-done' : 'is-current'}`}>
          <span className="onboarding-step-dot" />
          <div>
            <strong>Checklist</strong>
            <p className="muted" style={{ margin: '0.15rem 0 0' }}>
              {progress.completed}/{progress.total} mục · {progress.percent}%
            </p>
          </div>
        </div>
        <div className={`onboarding-step ${stepActiveDone ? 'is-done' : stepChecklistDone ? 'is-current' : ''}`}>
          <span className="onboarding-step-dot" />
          <div>
            <strong>Kích hoạt client</strong>
            <p className="muted" style={{ margin: '0.15rem 0 0' }}>
              {stepActiveDone ? 'Đã active' : stepWorkflowDone ? 'Workflow đã xong — chờ AM confirm' : 'Tự động khi checklist 100%'}
            </p>
          </div>
        </div>
      </div>

      <div className="onboarding-progress" aria-label="Tiến độ checklist" style={{ marginTop: '1rem' }}>
        <div className="onboarding-progress-bar" style={{ width: `${progress.percent}%` }} />
      </div>

      {lifecycles.length > 0 ? (
        <div className="onboarding-links" style={{ marginTop: '1rem' }}>
          <p style={{ margin: '0 0 0.35rem', fontWeight: 600, fontSize: '0.9rem' }}>Lifecycle liên kết</p>
          <ul className="onboarding-link-list">
            {lifecycles.map((lc) => (
              <li key={lc.lifecycle_id}>
                <Link href={lc.service_delivery_url} className="nav-link">
                  #{lc.lifecycle_id} · {lc.stage} · {lc.contract_title || lc.service_slug}
                </Link>
              </li>
            ))}
          </ul>
        </div>
      ) : (
        <p className="muted" style={{ marginTop: '1rem' }}>
          Chưa có lifecycle — liên kết qua hợp đồng có <code>agency_client_id</code>.
        </p>
      )}

      <ul className="onboarding-list">
        {summary.items.map((item) => (
          <li key={item.id} className="onboarding-item">
            <label>
              <input
                type="checkbox"
                checked={item.completed}
                disabled={!canWrite || busy}
                onChange={() => onToggleItem(item)}
              />
              <span>{item.label}</span>
            </label>
            {item.note ? <span className="muted"> · {item.note}</span> : null}
            {item.completed_by ? (
              <span className="muted" style={{ display: 'block', fontSize: '0.85rem' }}>
                {item.completed_by}
                {item.completed_at ? ` · ${item.completed_at.slice(0, 10)}` : ''}
              </span>
            ) : null}
          </li>
        ))}
      </ul>

      <div className="onboarding-widget-actions">
        {canWrite && workflow.temporal_enabled ? (
          <>
            {!workflow.found || workflow.status === 'NOT_FOUND' ? (
              <button type="button" className="btn btn-secondary btn-sm" disabled={busy} onClick={onStartWorkflow}>
                Khởi tạo workflow
              </button>
            ) : (
              <button type="button" className="btn btn-secondary btn-sm" disabled={busy} onClick={onNudgeWorkflow}>
                Nudge workflow
              </button>
            )}
          </>
        ) : null}

        {client.status === 'active' ? (
          <p className="muted" style={{ margin: 0 }}>
            Client đã <strong>active</strong>.{' '}
            <Link href="/agency/jobs" className="nav-link">
              Xem jobs
            </Link>
          </p>
        ) : (
          <>
            <button
              type="button"
              className="btn btn-sm"
              disabled={activateDisabled || busy}
              onClick={() => onActivate(false)}
            >
              Kích hoạt client
            </button>
            {canWrite && progress.percent < 100 ? (
              <button
                type="button"
                className="btn btn-secondary btn-sm"
                disabled={busy}
                onClick={() => {
                  if (window.confirm('Bỏ qua checklist và kích hoạt (force)?')) {
                    onActivate(true);
                  }
                }}
              >
                Force activate
              </button>
            ) : null}
          </>
        )}
      </div>

      {activateDisabled && client.status !== 'active' && !canWrite ? (
        <p className="muted">Chế độ chỉ xem — không thể sửa checklist hoặc kích hoạt.</p>
      ) : null}
      {activateDisabled && client.status !== 'active' && canWrite && strictOnboarding ? (
        <p className="muted">Hoàn thành checklist trước khi kích hoạt (PTT_CLIENT_STRICT_ONBOARDING).</p>
      ) : null}
    </div>
  );
}
