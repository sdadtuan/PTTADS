export function fmtVnd(n: number | null | undefined): string {
  if (n == null) return '—';
  return Math.round(n).toLocaleString('vi-VN') + ' ₫';
}

export function fmtPct(n: number | null | undefined): string {
  if (n == null) return '—';
  return `${n.toLocaleString('vi-VN', { maximumFractionDigits: 1 })}%`;
}

export function fmtDeltaVnd(n: number | null | undefined): string {
  if (n == null) return '—';
  const sign = n > 0 ? '+' : '';
  return sign + fmtVnd(n);
}

export function fmtDeltaPct(n: number | null | undefined): string {
  if (n == null) return '—';
  const sign = n > 0 ? '+' : '';
  return sign + fmtPct(n);
}

export function fmtDateTime(iso: string | null | undefined): string {
  if (!iso) return '—';
  try {
    return new Date(iso).toLocaleString('vi-VN');
  } catch {
    return iso;
  }
}

export function yesterdayIso(): string {
  const d = new Date();
  d.setUTCDate(d.getUTCDate() - 1);
  return d.toISOString().slice(0, 10);
}
