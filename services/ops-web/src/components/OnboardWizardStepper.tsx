'use client';

export type OnboardWizardPhase = {
  id: string;
  label: string;
  modules: string[];
  embed?: 'channels' | 'portal' | 'launch_qa' | null;
};

export const ONBOARD_WIZARD_PHASES: OnboardWizardPhase[] = [
  { id: 'crm', label: 'CRM & Lifecycle', modules: ['crm'] },
  { id: 'checklist', label: 'Checklist agency', modules: ['agency'] },
  { id: 'channels', label: 'Kết nối channel', modules: ['meta', 'zalo'], embed: 'channels' },
  { id: 'modules', label: 'SEO / Email', modules: ['seo', 'email'] },
  { id: 'portal', label: 'Portal & approver', modules: ['portal'], embed: 'portal' },
  { id: 'golive', label: 'Go-live', modules: ['crm'], embed: 'launch_qa' },
];

interface OnboardWizardStepperProps {
  phases: OnboardWizardPhase[];
  currentPhase: number;
  phaseComplete: (index: number) => boolean;
  onSelectPhase: (index: number) => void;
}

export function OnboardWizardStepper({
  phases,
  currentPhase,
  phaseComplete,
  onSelectPhase,
}: OnboardWizardStepperProps) {
  return (
    <ol className="onboard-wizard-stepper" style={{ display: 'flex', gap: '0.5rem', flexWrap: 'wrap', padding: 0, listStyle: 'none', margin: '0 0 1rem' }}>
      {phases.map((phase, index) => {
        const active = index === currentPhase;
        const done = phaseComplete(index);
        return (
          <li key={phase.id}>
            <button
              type="button"
              onClick={() => onSelectPhase(index)}
              style={{
                padding: '0.35rem 0.75rem',
                borderRadius: '999px',
                border: `1px solid ${active ? 'var(--accent, #2563eb)' : 'var(--border, #ddd)'}`,
                background: done ? 'rgba(37, 99, 235, 0.08)' : active ? 'rgba(37, 99, 235, 0.12)' : 'transparent',
                fontWeight: active ? 600 : 400,
                cursor: 'pointer',
              }}
            >
              {index + 1}. {phase.label}
              {done ? ' ✓' : ''}
            </button>
          </li>
        );
      })}
    </ol>
  );
}
