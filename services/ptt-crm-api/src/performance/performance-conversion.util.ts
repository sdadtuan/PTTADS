const WON_STATUSES = new Set(['won', 'closed_won', 'closed won', 'closed-won']);

export function isWonLeadStatus(status: string | null | undefined): boolean {
  const normalized = String(status ?? '')
    .trim()
    .toLowerCase();
  return WON_STATUSES.has(normalized);
}

export function parseDealValueVnd(meta: unknown): number {
  if (!meta || typeof meta !== 'object') return 0;
  const raw =
    (meta as Record<string, unknown>).deal_value_vnd ??
    (meta as Record<string, unknown>).deal_value ??
    (meta as Record<string, unknown>).value_vnd;
  if (raw == null || raw === '') return 0;
  const cleaned = String(raw).replace(/[^0-9.-]/g, '');
  const n = Number(cleaned);
  return Number.isFinite(n) && n > 0 ? n : 0;
}

export function computeCpa(spend: number, wonCount: number): number | null {
  if (spend <= 0 || wonCount <= 0) return null;
  return Math.round((spend / wonCount) * 100) / 100;
}
