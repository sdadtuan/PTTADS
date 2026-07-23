/** Reuse existing Launch QA run for client+campaign pair (no SQLite column). */
export function shouldReuseLaunchQaRun(
  existing: { status?: string } | null | undefined,
): boolean {
  if (!existing) return false;
  const status = String(existing.status ?? '').trim();
  return status === 'in_progress' || status === 'passed';
}
