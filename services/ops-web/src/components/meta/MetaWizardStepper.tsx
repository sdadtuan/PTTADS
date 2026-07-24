'use client';

import type { MetaWizardStep } from '@/lib/meta/types';

interface MetaWizardStepperProps {
  steps: MetaWizardStep[];
  currentStep: number;
}

export function MetaWizardStepper({ steps, currentStep }: MetaWizardStepperProps) {
  return (
    <ol className="meta-wizard-stepper" style={{ display: 'flex', gap: '0.75rem', flexWrap: 'wrap', padding: 0, listStyle: 'none' }}>
      {steps.map((step, index) => {
        const active = index === currentStep;
        const done = index < currentStep;
        return (
          <li
            key={step.id}
            style={{
              padding: '0.35rem 0.75rem',
              borderRadius: '999px',
              border: `1px solid ${active ? 'var(--accent, #2563eb)' : 'var(--border, #ddd)'}`,
              background: done ? 'rgba(37, 99, 235, 0.08)' : active ? 'rgba(37, 99, 235, 0.12)' : 'transparent',
              fontWeight: active ? 600 : 400,
            }}
          >
            {index + 1}. {step.label}
          </li>
        );
      })}
    </ol>
  );
}

export const LAUNCH_WIZARD_STEPS: MetaWizardStep[] = [
  { id: 'client', label: 'Client & account' },
  { id: 'objective', label: 'Objective & budget' },
  { id: 'creative', label: 'Creative' },
  { id: 'tracking', label: 'Tracking' },
  { id: 'review', label: 'Review & submit' },
];

export const EDIT_WIZARD_STEPS: MetaWizardStep[] = [
  { id: 'select', label: 'Chọn ad' },
  { id: 'change', label: 'Creative / copy' },
  { id: 'diff', label: 'Diff review' },
  { id: 'submit', label: 'Submit' },
];
