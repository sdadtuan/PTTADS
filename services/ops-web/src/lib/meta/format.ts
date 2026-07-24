import type { MetaBadgeVariant } from './types';

export function fmtVnd(n: number | null | undefined): string {
  if (n == null) return '—';
  return Math.round(n).toLocaleString('vi-VN') + ' ₫';
}

export function fmtPct(n: number | null | undefined): string {
  if (n == null || !Number.isFinite(n)) return '—';
  return `${n.toLocaleString('vi-VN', { maximumFractionDigits: 1 })}%`;
}

export function fmtMs(value: number | null | undefined): string {
  if (value == null || !Number.isFinite(value)) return '—';
  if (value >= 1000) return `${(value / 1000).toFixed(1)}s`;
  return `${Math.round(value)}ms`;
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

export function fmtRelativeTime(iso: string | null | undefined): string {
  if (!iso) return '—';
  const ts = new Date(iso).getTime();
  if (!Number.isFinite(ts)) return '—';
  const diffMs = Date.now() - ts;
  const mins = Math.floor(diffMs / 60000);
  if (mins < 60) return `${mins} phút trước`;
  const hours = Math.floor(mins / 60);
  if (hours < 48) return `${hours} giờ trước`;
  const days = Math.floor(hours / 24);
  return `${days} ngày trước`;
}

export function yesterdayIso(): string {
  const d = new Date();
  d.setUTCDate(d.getUTCDate() - 1);
  return d.toISOString().slice(0, 10);
}

export function capiBadgeFromAccount(input: {
  pixel_id?: string | null;
  capi_enabled?: boolean;
  last_sent_at?: string | null;
}): { variant: MetaBadgeVariant; label: string } {
  if (!input.pixel_id) {
    return { variant: 'error', label: 'Thiếu pixel' };
  }
  if (input.capi_enabled && input.last_sent_at) {
    return { variant: 'ok', label: 'CAPI OK' };
  }
  if (input.capi_enabled) {
    return { variant: 'warn', label: 'CAPI bật' };
  }
  return { variant: 'muted', label: 'CAPI tắt' };
}
