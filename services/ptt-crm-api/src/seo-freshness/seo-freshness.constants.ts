export const SEO_FRESHNESS_SCHEMA = 'seo_aeo';

export const FRESHNESS_PRIORITIES = ['urgent', 'high', 'medium', 'low'] as const;

export function refreshPriority(decayScore: number): string {
  if (decayScore >= 80) return 'urgent';
  if (decayScore >= 60) return 'high';
  if (decayScore >= 40) return 'medium';
  return 'low';
}

export function computeDecayScore(input: {
  ageDays: number;
  trafficDeltaPct: number | null;
  gscClicksCurrent: number;
  gscClicksPrevious: number;
  workflowStatus: string;
}): number {
  const scoreable = ['published', 'monitoring'].includes(input.workflowStatus);
  if (!scoreable) return 0;
  const base = Math.min((input.ageDays / 365) * 40, 40);
  let trafficComponent = 0;
  if (input.trafficDeltaPct != null) {
    trafficComponent = Math.min(Math.max(0, -input.trafficDeltaPct), 40);
  }
  let gscDecay = 0;
  if (input.gscClicksPrevious > 10 && input.gscClicksCurrent < input.gscClicksPrevious * 0.7) {
    gscDecay = 20;
  }
  return Math.min(100, Math.round((base + trafficComponent + gscDecay) * 100) / 100);
}
