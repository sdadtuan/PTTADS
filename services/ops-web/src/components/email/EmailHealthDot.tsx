'use client';

const LABELS: Record<string, string> = {
  healthy: 'Healthy',
  at_risk: 'At risk',
  unknown: 'Unknown',
  critical: 'Critical',
};

export function EmailHealthDot({ health }: { health: string }) {
  const key = (health || 'unknown').toLowerCase();
  const label = LABELS[key] ?? health;
  return (
    <span className={`email-health-dot email-health-${key}`} aria-label={`Domain health: ${label}`}>
      {label}
    </span>
  );
}
