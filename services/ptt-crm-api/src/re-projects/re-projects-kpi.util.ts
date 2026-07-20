export const KPI_CATEGORIES = [
  'revenue',
  'sales',
  'marketing',
  'finance',
  'customer',
  'operation',
] as const;

export const KPI_TRACK_STATUSES = ['draft', 'active', 'completed', 'cancelled'] as const;

export const RE_LEADS_NEW_METRIC_CODE = 'RE_LEADS_NEW';

export const RE_LEADS_NEW_EXCLUDED_STATUSES = ['lost', 'junk', 'spam', 'duplicate'] as const;

export interface KpiMetricTemplate {
  code: string;
  crm_code: string;
  metric_name: string;
  category: string;
  unit: string;
  weight_pct: number;
}

/** Full RE metric templates — used by save/resolve; refresh only needs RE_LEADS_NEW. */
export const KPI_METRIC_TEMPLATES: readonly KpiMetricTemplate[] = [
  {
    code: 'units_sold',
    crm_code: 'RE_UNITS_SOLD',
    metric_name: 'Số căn bán ký HĐ',
    category: 'sales',
    unit: 'căn',
    weight_pct: 25,
  },
  {
    code: 'revenue_signed',
    crm_code: 'RE_REVENUE_SIGNED',
    metric_name: 'Doanh thu ký HĐ',
    category: 'revenue',
    unit: 'VND',
    weight_pct: 25,
  },
  {
    code: 'leads_new',
    crm_code: RE_LEADS_NEW_METRIC_CODE,
    metric_name: 'Lead mới qualified',
    category: 'marketing',
    unit: 'lead',
    weight_pct: 10,
  },
  {
    code: 'showroom_visits',
    crm_code: 'RE_SHOWROOM_VISITS',
    metric_name: 'Lượt tham quan showroom',
    category: 'sales',
    unit: 'lượt',
    weight_pct: 10,
  },
  {
    code: 'conversion_rate',
    crm_code: 'RE_CONVERSION_RATE',
    metric_name: 'Tỷ lệ chốt lead → cọc',
    category: 'sales',
    unit: '%',
    weight_pct: 15,
  },
  {
    code: 'deposit_collected',
    crm_code: 'RE_DEPOSIT_COLLECTED',
    metric_name: 'Số căn thu cọc',
    category: 'sales',
    unit: 'căn',
    weight_pct: 10,
  },
  {
    code: 'collection_rate',
    crm_code: 'RE_COLLECTION_RATE',
    metric_name: 'Tỷ lệ thu tiền theo tiến độ',
    category: 'finance',
    unit: '%',
    weight_pct: 5,
  },
];

export function parsePeriodMonth(periodMonth: string): { year: number | null; month: number | null } {
  const raw = String(periodMonth ?? '').trim();
  const m = /^(\d{4})-(\d{1,2})$/.exec(raw);
  if (!m) return { year: null, month: null };
  const year = Number(m[1]);
  const month = Number(m[2]);
  if (month < 1 || month > 12 || year < 2000 || year > 2100) {
    return { year: null, month: null };
  }
  return { year, month };
}

export function mapReTrackToStaffStatus(track: string): string {
  const map: Record<string, string> = {
    draft: 'draft',
    active: 'at_risk',
    completed: 'achieved',
    cancelled: 'missed',
  };
  return map[String(track || 'active')] ?? 'draft';
}

export function mapStaffToReTrackStatus(staffStatus: string): string {
  const map: Record<string, string> = {
    draft: 'draft',
    at_risk: 'active',
    achieved: 'completed',
    missed: 'cancelled',
  };
  return map[String(staffStatus || 'draft')] ?? 'active';
}

export function currentPeriodMonth(): string {
  const now = new Date();
  const y = now.getFullYear();
  const m = String(now.getMonth() + 1).padStart(2, '0');
  return `${y}-${m}`;
}
