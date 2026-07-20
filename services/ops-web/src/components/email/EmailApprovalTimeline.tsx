'use client';

const STEPS = [
  { key: 'draft', label: 'Draft' },
  { key: 'preflight', label: 'Preflight' },
  { key: 'pending_approval', label: 'Chờ duyệt' },
  { key: 'approved', label: 'Approved' },
  { key: 'sending', label: 'Sending' },
  { key: 'sent', label: 'Sent' },
];

function stepIndex(status: string): number {
  const s = status.toLowerCase();
  if (s === 'draft') return 0;
  if (s === 'pending_approval') return 2;
  if (s === 'approved' || s === 'scheduled') return 3;
  if (s === 'sending') return 4;
  if (s === 'sent') return 5;
  return 0;
}

export function EmailApprovalTimeline({ status }: { status: string }) {
  const current = stepIndex(status);
  return (
    <div className="email-approval-timeline" aria-label="Campaign approval timeline">
      {STEPS.map((step, index) => {
        let cls = 'email-approval-step email-approval-step--pending';
        if (index < current) cls = 'email-approval-step email-approval-step--done';
        if (index === current) cls = 'email-approval-step email-approval-step--current';
        return (
          <div key={step.key} className={cls}>
            {step.label}
          </div>
        );
      })}
    </div>
  );
}
