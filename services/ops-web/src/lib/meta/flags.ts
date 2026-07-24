/** Feature flags for Meta Enterprise B8 UI. */

export function metaAlertsEnabled(): boolean {
  const raw = (process.env.NEXT_PUBLIC_PTT_META_ALERTS_ENABLED ?? '0').trim().toLowerCase();
  return ['1', 'true', 'yes', 'on'].includes(raw);
}
