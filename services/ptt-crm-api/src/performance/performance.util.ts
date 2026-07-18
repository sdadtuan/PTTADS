export type PerformanceChannelFilter = 'meta' | 'google';

export function normalizePerformanceChannel(value: string | undefined): PerformanceChannelFilter | null {
  const channel = (value ?? '').trim().toLowerCase();
  if (!channel) {
    return null;
  }
  if (channel === 'meta' || channel === 'facebook') {
    return 'meta';
  }
  if (channel === 'google') {
    return 'google';
  }
  return null;
}

export function performanceChannelSql(channel: PerformanceChannelFilter | null): string[] {
  if (channel === 'meta') {
    return ['meta'];
  }
  if (channel === 'google') {
    return ['google'];
  }
  return ['meta', 'google'];
}

export function computeCpl(spend: number, leads: number): number | null {
  if (spend <= 0 || leads <= 0) {
    return null;
  }
  return Math.round((spend / leads) * 100) / 100;
}

export function computeRoas(conversionValue: number, spend: number): number | null {
  if (spend <= 0 || conversionValue <= 0) {
    return null;
  }
  return Math.round((conversionValue / spend) * 10000) / 10000;
}

export function parseDate(value: string | undefined, fallback: Date): Date {
  if (!value?.trim()) {
    return fallback;
  }
  const text = value.trim().slice(0, 10);
  const dt = new Date(`${text}T00:00:00Z`);
  return Number.isNaN(dt.getTime()) ? fallback : dt;
}

export function formatDateOnly(d: Date): string {
  return d.toISOString().slice(0, 10);
}

export function resolveDateWindow(
  query: { from?: string; to?: string; date_from?: string; date_to?: string },
  defaultDays = 7,
): { start: Date; end: Date } {
  const today = new Date();
  const yesterday = new Date(Date.UTC(today.getUTCFullYear(), today.getUTCMonth(), today.getUTCDate() - 1));
  let end = parseDate(query.to ?? query.date_to, yesterday);
  const startDefault = new Date(end);
  startDefault.setUTCDate(startDefault.getUTCDate() - (Math.max(1, defaultDays) - 1));
  let start = parseDate(query.from ?? query.date_from, startDefault);
  if (start > end) {
    const tmp = start;
    start = end;
    end = tmp;
  }
  return { start, end };
}

export function toIso(value: unknown): string | null {
  if (value == null) {
    return null;
  }
  if (value instanceof Date) {
    return value.toISOString();
  }
  return String(value);
}

export function toNumber(value: unknown): number {
  if (value == null || value === '') {
    return 0;
  }
  const n = Number(value);
  return Number.isFinite(n) ? n : 0;
}
