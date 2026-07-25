'use client';

import Link from 'next/link';
import type { OnboardOrchestratorResponse, OnboardOrchestratorStep } from '@/lib/api';

const MODULE_LABELS: Record<string, string> = {
  crm: 'CRM',
  agency: 'Agency',
  meta: 'Meta',
  seo: 'SEO',
  email: 'Email',
  portal: 'Portal',
};

function stepStatusLabel(step: OnboardOrchestratorStep): string {
  if (step.status === 'done') return step.auto_detected ? 'Auto ✓' : 'Done';
  if (step.status === 'optional') return 'Tuỳ chọn';
  if (step.status === 'skipped') return 'Bỏ qua';
  return 'Chưa xong';
}

function stepStatusClass(step: OnboardOrchestratorStep): string {
  if (step.status === 'done') return step.auto_detected ? 'is-auto' : 'is-done';
  if (step.status === 'optional') return 'is-optional';
  return 'is-pending';
}

type Props = {
  data: OnboardOrchestratorResponse;
  compact?: boolean;
  canWrite?: boolean;
  busy?: boolean;
  onSync?: () => void;
  onActivate?: () => void;
  clientActive?: boolean;
};

export function ClientOnboardOrchestrator({
  data,
  compact = false,
  canWrite = false,
  busy = false,
  onSync,
  onActivate,
  clientActive = false,
}: Props) {
  const { progress, steps } = data;

  return (
    <div className={`onboard-orchestrator${compact ? ' is-compact' : ''}`}>
      <div className="onboard-orchestrator-header">
        <div>
          <h3 style={{ margin: 0, fontSize: compact ? '0.95rem' : '1rem' }}>
            Onboard orchestrator
          </h3>
          {!compact ? (
            <p className="muted" style={{ margin: '0.35rem 0 0' }}>
              Một màn cross-module — deep-link từng bước, auto-detect tick checklist
            </p>
          ) : null}
        </div>
        <div style={{ textAlign: 'right' }}>
          <strong>{progress.required_percent}%</strong>
          <p className="muted" style={{ margin: '0.15rem 0 0', fontSize: '0.85rem' }}>
            {progress.required_completed}/{progress.required_total} bắt buộc
          </p>
        </div>
      </div>

      <div className="onboarding-progress" aria-label="Tiến độ orchestrator" style={{ marginTop: '0.75rem' }}>
        <div className="onboarding-progress-bar" style={{ width: `${progress.required_percent}%` }} />
      </div>

      <ol className="onboard-orchestrator-steps">
        {steps.map((step) => (
          <li key={step.key} className={`onboard-orchestrator-step ${stepStatusClass(step)}`}>
            <div className="onboard-orchestrator-step-main">
              <span className="onboard-orchestrator-module">{MODULE_LABELS[step.module] ?? step.module}</span>
              <div>
                <strong>{step.label}</strong>
                {step.detection_detail ? (
                  <p className="muted" style={{ margin: '0.15rem 0 0', fontSize: '0.85rem' }}>
                    {step.detection_detail}
                  </p>
                ) : null}
                {step.hint && step.status !== 'done' ? (
                  <p className="muted" style={{ margin: '0.15rem 0 0', fontSize: '0.8rem' }}>
                    {step.hint}
                  </p>
                ) : null}
              </div>
            </div>
            <div className="onboard-orchestrator-step-actions">
              <span className={`onboard-orchestrator-badge ${stepStatusClass(step)}`}>
                {stepStatusLabel(step)}
              </span>
              {step.href ? (
                <Link href={step.href} className="nav-link" style={{ fontSize: '0.85rem' }}>
                  Mở →
                </Link>
              ) : null}
            </div>
          </li>
        ))}
      </ol>

      {!compact ? (
        <div className="onboard-orchestrator-footer">
          <p className="muted" style={{ margin: 0, fontSize: '0.85rem' }}>
            Checklist agency: {data.checklist_progress.completed}/{data.checklist_progress.total} (
            {data.checklist_progress.percent}%)
            {data.synced_at ? ` · Sync ${new Date(data.synced_at).toLocaleString('vi-VN')}` : ''}
          </p>
          <div style={{ display: 'flex', gap: '0.5rem', flexWrap: 'wrap', marginTop: '0.75rem' }}>
            {canWrite && onSync ? (
              <button type="button" className="btn btn-sm" disabled={busy} onClick={() => onSync()}>
                Auto-sync checklist
              </button>
            ) : null}
            {data.linked_lifecycle_url ? (
              <Link href={data.linked_lifecycle_url} className="btn btn-sm btn-secondary">
                Lifecycle onboard
              </Link>
            ) : null}
            {canWrite && onActivate && !clientActive ? (
              <button type="button" className="btn btn-sm" disabled={busy} onClick={() => onActivate()}>
                Activate client
              </button>
            ) : null}
          </div>
        </div>
      ) : null}
    </div>
  );
}
