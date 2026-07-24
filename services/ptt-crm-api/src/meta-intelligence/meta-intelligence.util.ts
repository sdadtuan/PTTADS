import { computeRoas } from '../performance/performance.util';

export const B10_ANOMALY_TYPES = ['spend_spike', 'cpl_spike', 'roas_low'] as const;
export const B11_STAT_ANOMALY_TYPES = ['spend_zscore', 'cpl_zscore'] as const;

export function envFloat(name: string, fallback: number): number {
  const raw = (process.env[name] ?? String(fallback)).trim();
  const n = Number(raw);
  return Number.isFinite(n) ? n : fallback;
}

export function envInt(name: string, fallback: number): number {
  return Math.round(envFloat(name, fallback));
}

export function median(values: number[]): number | null {
  const cleaned = values.filter((v) => v > 0);
  if (!cleaned.length) return null;
  const sorted = [...cleaned].sort((a, b) => a - b);
  const mid = Math.floor(sorted.length / 2);
  if (sorted.length % 2 === 1) return sorted[mid];
  return (sorted[mid - 1] + sorted[mid]) / 2;
}

export function computeSpikePct(current: number, baselineMedian: number): number | null {
  if (baselineMedian <= 0 || current <= baselineMedian) return null;
  return Math.round(((current - baselineMedian) / baselineMedian) * 1000) / 10;
}

export function isMedianSpike(
  current: number,
  baselineValues: number[],
  spikePct: number,
): { spike: boolean; baselineMedian: number | null } {
  const base = median(baselineValues);
  if (base == null || base <= 0 || current <= 0) {
    return { spike: false, baselineMedian: base };
  }
  const threshold = base * (1 + spikePct / 100);
  return { spike: current > threshold, baselineMedian: base };
}

export interface DetectedAnomaly {
  alert_type: string;
  severity: string;
  metric_value: number | null;
  threshold_value: number | null;
  spike_pct: number | null;
  message: string;
}

export function detectCampaignAnomalies(params: {
  spendToday: number;
  leadsToday: number;
  conversionValueToday: number;
  spendHistory: number[];
  cplHistory: number[];
  spikePct: number;
  roasMinTarget: number;
  roasMinSpend: number;
}): DetectedAnomaly[] {
  const out: DetectedAnomaly[] = [];
  const spendSpike = isMedianSpike(params.spendToday, params.spendHistory, params.spikePct);
  if (spendSpike.spike && spendSpike.baselineMedian != null) {
    const pct = computeSpikePct(params.spendToday, spendSpike.baselineMedian);
    out.push({
      alert_type: 'spend_spike',
      severity: 'warning',
      metric_value: params.spendToday,
      threshold_value: spendSpike.baselineMedian * (1 + params.spikePct / 100),
      spike_pct: pct,
      message: `Spend spike ${pct?.toFixed(1) ?? '?'}% vs median 7d (${params.spendToday.toLocaleString('vi-VN')} VND)`,
    });
  }

  if (params.leadsToday >= 2) {
    const cplToday = params.spendToday / params.leadsToday;
    const cplSpike = isMedianSpike(cplToday, params.cplHistory, params.spikePct);
    if (cplSpike.spike && cplSpike.baselineMedian != null) {
      const pct = computeSpikePct(cplToday, cplSpike.baselineMedian);
      out.push({
        alert_type: 'cpl_spike',
        severity: 'warning',
        metric_value: cplToday,
        threshold_value: cplSpike.baselineMedian * (1 + params.spikePct / 100),
        spike_pct: pct,
        message: `CPL spike ${pct?.toFixed(1) ?? '?'}% vs median 7d (${cplToday.toLocaleString('vi-VN')} VND)`,
      });
    }
  }

  if (params.spendToday >= params.roasMinSpend && params.conversionValueToday > 0) {
    const roas = computeRoas(params.conversionValueToday, params.spendToday);
    if (roas != null && roas < params.roasMinTarget) {
      out.push({
        alert_type: 'roas_low',
        severity: 'warning',
        metric_value: roas,
        threshold_value: params.roasMinTarget,
        spike_pct: null,
        message: `ROAS ${roas.toFixed(2)} dưới ngưỡng ${params.roasMinTarget.toFixed(2)}`,
      });
    }
  }

  return out;
}

export function recommendBudgetChange(params: {
  avgDailySpend: number;
  cpl: number | null;
  targetCpl: number | null;
  leads: number;
  roas: number | null;
  decreasePct: number;
  increasePct: number;
  cplOverRatio: number;
  cplUnderRatio: number;
}):
  | {
      recommendation_type: 'decrease_budget' | 'increase_budget';
      change_pct: number;
      suggested_daily_budget_vnd: number;
      rationale: string;
    }
  | null {
  if (params.avgDailySpend <= 0 || params.cpl == null || params.targetCpl == null || params.targetCpl <= 0) {
    return null;
  }

  if (params.cpl > params.targetCpl * params.cplOverRatio && params.leads >= 2) {
    const suggested = Math.round(params.avgDailySpend * (1 - params.decreasePct / 100));
    return {
      recommendation_type: 'decrease_budget',
      change_pct: -params.decreasePct,
      suggested_daily_budget_vnd: Math.max(0, suggested),
      rationale: `CPL ${params.cpl.toLocaleString('vi-VN')} VND vượt target ${params.targetCpl.toLocaleString('vi-VN')} — giảm ngân sách ${params.decreasePct}%`,
    };
  }

  if (
    params.cpl < params.targetCpl * params.cplUnderRatio &&
    params.leads >= 3 &&
    (params.roas == null || params.roas >= 1)
  ) {
    const suggested = Math.round(params.avgDailySpend * (1 + params.increasePct / 100));
    return {
      recommendation_type: 'increase_budget',
      change_pct: params.increasePct,
      suggested_daily_budget_vnd: suggested,
      rationale: `CPL ${params.cpl.toLocaleString('vi-VN')} VND dưới target ${params.targetCpl.toLocaleString('vi-VN')} — tăng ngân sách ${params.increasePct}%`,
    };
  }

  return null;
}

export function computeZscore(value: number, baselineValues: number[]): number | null {
  const cleaned = baselineValues.filter((v) => v > 0);
  if (cleaned.length < 3 || value <= 0) return null;
  const mean = cleaned.reduce((a, b) => a + b, 0) / cleaned.length;
  const variance = cleaned.reduce((acc, v) => acc + (v - mean) ** 2, 0) / cleaned.length;
  const std = Math.sqrt(variance);
  if (std <= 0) return null;
  return Math.round(((value - mean) / std) * 1000) / 1000;
}

export interface DetectedStatAnomaly extends DetectedAnomaly {
  z_score: number | null;
}

export function detectCampaignStatAnomalies(params: {
  spendToday: number;
  leadsToday: number;
  spendHistory: number[];
  cplHistory: number[];
  zscoreThreshold: number;
}): DetectedStatAnomaly[] {
  const out: DetectedStatAnomaly[] = [];
  const spendZ = computeZscore(params.spendToday, params.spendHistory);
  if (spendZ != null && spendZ >= params.zscoreThreshold) {
    out.push({
      alert_type: 'spend_zscore',
      severity: 'warning',
      metric_value: params.spendToday,
      threshold_value: params.zscoreThreshold,
      spike_pct: null,
      z_score: spendZ,
      message: `Spend z-score ${spendZ.toFixed(2)} (threshold ${params.zscoreThreshold.toFixed(1)})`,
    });
  }
  if (params.leadsToday >= 2) {
    const cplToday = params.spendToday / params.leadsToday;
    const cplZ = computeZscore(cplToday, params.cplHistory);
    if (cplZ != null && cplZ >= params.zscoreThreshold) {
      out.push({
        alert_type: 'cpl_zscore',
        severity: 'warning',
        metric_value: cplToday,
        threshold_value: params.zscoreThreshold,
        spike_pct: null,
        z_score: cplZ,
        message: `CPL z-score ${cplZ.toFixed(2)} (threshold ${params.zscoreThreshold.toFixed(1)})`,
      });
    }
  }
  return out;
}

export function linearRegression(points: Array<{ x: number; y: number }>): { slope: number; intercept: number } {
  const n = points.length;
  if (!n) return { slope: 0, intercept: 0 };
  if (n === 1) return { slope: 0, intercept: points[0].y };
  const sumX = points.reduce((acc, p) => acc + p.x, 0);
  const sumY = points.reduce((acc, p) => acc + p.y, 0);
  const sumXY = points.reduce((acc, p) => acc + p.x * p.y, 0);
  const sumXX = points.reduce((acc, p) => acc + p.x * p.x, 0);
  const denom = n * sumXX - sumX * sumX;
  if (denom === 0) return { slope: 0, intercept: sumY / n };
  const slope = (n * sumXY - sumX * sumY) / denom;
  const intercept = (sumY - slope * sumX) / n;
  return { slope, intercept };
}

export function buildForecastProjection(params: {
  historical: Array<{ performance_date: string; value: number }>;
  projectionDays: number;
}): {
  slope: number;
  intercept: number;
  historical: Array<{ performance_date: string; value: number }>;
  projection: Array<{ performance_date: string; projected_value: number }>;
} {
  const sorted = [...params.historical].sort((a, b) => a.performance_date.localeCompare(b.performance_date));
  const points = sorted
    .map((row, idx) => ({ x: idx, y: row.value }))
    .filter((p) => p.y > 0);
  const { slope, intercept } = linearRegression(points);
  const lastDate = sorted.length ? sorted[sorted.length - 1].performance_date : formatDateOnly(new Date());
  const lastIdx = points.length ? points[points.length - 1].x : 0;
  const projection: Array<{ performance_date: string; projected_value: number }> = [];
  const base = parseDate(lastDate, new Date());
  for (let offset = 1; offset <= params.projectionDays; offset += 1) {
    const x = lastIdx + offset;
    const projected = Math.max(0, slope * x + intercept);
    const day = new Date(base);
    day.setUTCDate(day.getUTCDate() + offset);
    projection.push({
      performance_date: formatDateOnly(day),
      projected_value: Math.round(projected * 100) / 100,
    });
  }
  return {
    slope: Math.round(slope * 10000) / 10000,
    intercept: Math.round(intercept * 100) / 100,
    historical: sorted.map((row) => ({
      performance_date: row.performance_date,
      value: Math.round(row.value * 100) / 100,
    })),
    projection,
  };
}

function formatDateOnly(d: Date): string {
  return d.toISOString().slice(0, 10);
}

function parseDate(value: string, fallback: Date): Date {
  const parsed = new Date(`${value}T00:00:00.000Z`);
  return Number.isNaN(parsed.getTime()) ? fallback : parsed;
}
