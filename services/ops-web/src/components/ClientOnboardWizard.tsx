'use client';

import Link from 'next/link';
import { useMemo, useState } from 'react';
import type { OnboardOrchestratorResponse, OnboardOrchestratorStep } from '@/lib/api';
import { ClientOnboardOrchestrator } from '@/components/ClientOnboardOrchestrator';
import { ONBOARD_WIZARD_PHASES, OnboardWizardStepper } from '@/components/OnboardWizardStepper';

type Props = {
  data: OnboardOrchestratorResponse;
  canWrite?: boolean;
  busy?: boolean;
  clientActive?: boolean;
  onSync?: () => void;
  onActivate?: () => void;
  embed?: {
    channels?: React.ReactNode;
    portal?: React.ReactNode;
    launch_qa?: React.ReactNode;
  };
};

function stepsForPhase(steps: OnboardOrchestratorStep[], modules: string[]): OnboardOrchestratorStep[] {
  return steps.filter((s) => modules.includes(s.module));
}

function phaseDone(steps: OnboardOrchestratorStep[], modules: string[]): boolean {
  const filtered = stepsForPhase(steps, modules).filter((s) => s.status !== 'optional');
  if (!filtered.length) return true;
  return filtered.every((s) => s.status === 'done');
}

export function ClientOnboardWizard({
  data,
  canWrite = false,
  busy = false,
  clientActive = false,
  onSync,
  onActivate,
  embed,
}: Props) {
  const [phase, setPhase] = useState(0);
  const phases = ONBOARD_WIZARD_PHASES;
  const current = phases[phase] ?? phases[0];

  const phaseSteps = useMemo(
    () => stepsForPhase(data.steps, current.modules),
    [data.steps, current.modules],
  );

  const filteredData: OnboardOrchestratorResponse = useMemo(
    () => ({
      ...data,
      steps: phaseSteps,
      progress: data.progress,
    }),
    [data, phaseSteps],
  );

  const completeFlags = useMemo(
    () => phases.map((p) => phaseDone(data.steps, p.modules)),
    [data.steps, phases],
  );

  return (
    <div className="onboard-wizard">
      <OnboardWizardStepper
        phases={phases}
        currentPhase={phase}
        phaseComplete={(i) => completeFlags[i] ?? false}
        onSelectPhase={setPhase}
      />

      <div style={{ display: 'flex', justifyContent: 'space-between', gap: '0.5rem', marginBottom: '0.75rem' }}>
        <strong>{current.label}</strong>
        <span className="muted" style={{ fontSize: '0.85rem' }}>
          Tổng {data.progress.required_percent}% · {data.progress.required_completed}/{data.progress.required_total} bắt buộc
        </span>
      </div>

      <ClientOnboardOrchestrator
        data={filteredData}
        canWrite={canWrite}
        busy={busy}
        clientActive={clientActive}
        onSync={onSync}
        onActivate={onActivate}
      />

      {current.embed === 'channels' && embed?.channels ? (
        <div style={{ marginTop: '1rem' }}>{embed.channels}</div>
      ) : null}
      {current.embed === 'portal' && embed?.portal ? (
        <div style={{ marginTop: '1rem' }}>{embed.portal}</div>
      ) : null}
      {current.embed === 'launch_qa' && embed?.launch_qa ? (
        <div style={{ marginTop: '1rem' }}>{embed.launch_qa}</div>
      ) : null}
      {current.embed === 'launch_qa' && data.linked_lifecycle_url ? (
        <p style={{ marginTop: '0.75rem' }}>
          <Link href={`${data.linked_lifecycle_url.replace('?tab=workflow', '')}?tab=launch_qa`} className="nav-link">
            Mở Launch QA trên lifecycle →
          </Link>
        </p>
      ) : null}

      <div style={{ display: 'flex', gap: '0.5rem', marginTop: '1rem', flexWrap: 'wrap' }}>
        <button type="button" className="btn btn-sm btn-secondary" disabled={phase <= 0} onClick={() => setPhase((p) => Math.max(0, p - 1))}>
          ← Bước trước
        </button>
        <button
          type="button"
          className="btn btn-sm"
          disabled={phase >= phases.length - 1}
          onClick={() => setPhase((p) => Math.min(phases.length - 1, p + 1))}
        >
          Bước tiếp →
        </button>
      </div>
    </div>
  );
}
