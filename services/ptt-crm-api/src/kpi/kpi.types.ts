export interface KpiMetricRow {
  id: number;
  code: string;
  name: string;
  unit: string;
  description: string;
  sort_order: number;
  active: number;
  higher_is_better: number;
  warn_ratio: number | null;
  created_at: string;
  updated_at: string;
}

export interface CreateKpiMetricBody {
  code?: string;
  name: string;
  unit?: string;
  description?: string;
  sort_order?: number;
  higher_is_better?: boolean | number;
  warn_ratio?: number | null;
}

export interface PatchKpiMetricBody {
  code?: string;
  name?: string;
  unit?: string;
  description?: string;
  sort_order?: number;
  active?: boolean | number;
  higher_is_better?: boolean | number;
  warn_ratio?: number | null;
}

export interface StaffKpiEntryRow {
  id: number;
  staff_id: number;
  metric_id: number;
  year: number;
  month: number;
  target_value: number | null;
  actual_value: number | null;
  status: string;
  note: string;
  created_at: string;
  updated_at: string;
  metric_name: string;
  metric_code: string;
  metric_unit: string;
  metric_higher_is_better: number;
  metric_warn_ratio: number | null;
  staff_name: string;
  staff_code: string;
}

export interface StaffKpiMetricItem {
  key: string;
  label: string;
  value: number;
  target: number | null;
}

export interface StaffKpiMetricsResponse {
  staff_id: number;
  role: string;
  year: number;
  month: number;
  metrics: StaffKpiMetricItem[];
}

export function truthyFlag(raw: unknown): boolean {
  return raw === true || raw === 1 || raw === '1' || raw === 'true' || raw === 'yes';
}

export interface KpiAlertRow {
  level: string;
  reason: string;
  message: string;
  kpi_id: number;
  staff_id: number;
  staff_name: string;
  staff_code: string;
  metric_id: number;
  metric_name: string;
  metric_code: string;
  target_value: number | null;
  actual_value: number | null;
  status: string;
}

export interface KpiAlertsResponse {
  alerts: KpiAlertRow[];
  summary: { critical: number; warn: number };
  year: number;
  month: number;
}

export interface KpiChartResponse {
  metric: Record<string, unknown>;
  higher_is_better: number;
  year: number;
  month: number;
  labels: string[];
  achievement_pct: Array<number | null>;
  staff_ids: number[];
}

export interface PatchStaffKpiProgressBody {
  actual_value?: number | null;
  status?: string;
  note?: string;
}

export interface StaffKpiExportResponse {
  staff_kpi: StaffKpiEntryRow[];
  year: number;
  month: number;
}

export function kpiAchievementPct(
  higherIsBetter: number,
  targetValue: unknown,
  actualValue: unknown,
): number | null {
  if (targetValue == null || actualValue == null) return null;
  const t = Number(targetValue);
  const a = Number(actualValue);
  if (!Number.isFinite(t) || !Number.isFinite(a) || t === 0) return null;
  const hi = Number(higherIsBetter || 1) === 1;
  if (hi) return Math.round(100 * Math.min(1, a / t) * 100) / 100;
  return Math.round(100 * Math.min(1, t / Math.max(a, 1e-9)) * 100) / 100;
}

export function deriveKpiAlert(
  status: string,
  higherIsBetter: number,
  warnRatio: unknown,
  targetValue: unknown,
  actualValue: unknown,
): { level: string | null; reason: string | null } {
  const st = String(status || 'draft').trim().toLowerCase();
  if (st === 'missed') return { level: 'critical', reason: 'status_missed' };
  if (st === 'at_risk') return { level: 'warn', reason: 'status_at_risk' };
  if (warnRatio == null || targetValue == null || actualValue == null) {
    return { level: null, reason: null };
  }
  const wr = Number(warnRatio);
  const t = Number(targetValue);
  const a = Number(actualValue);
  if (!Number.isFinite(wr) || !Number.isFinite(t) || !Number.isFinite(a)) {
    return { level: null, reason: null };
  }
  if (wr <= 0 || wr > 10 || t === 0) return { level: null, reason: null };
  const hi = Number(higherIsBetter || 1) === 1;
  if (hi && a < t * wr) return { level: 'warn', reason: 'below_threshold' };
  if (!hi && a > t / wr) return { level: 'warn', reason: 'above_threshold' };
  return { level: null, reason: null };
}

export function kpiAlertLabelVi(level: string, reason: string | null): string {
  if (level === 'critical' && reason === 'status_missed') return 'Không đạt KPI';
  if (level === 'warn' && reason === 'status_at_risk') return 'Có rủi ro';
  if (level === 'warn' && reason === 'below_threshold') return 'Dưới ngưỡng cảnh báo';
  if (level === 'warn' && reason === 'above_threshold') return 'Vượt ngưỡng cảnh báo';
  return level === 'critical' ? 'Cảnh báo nghiêm trọng' : 'Cảnh báo';
}
