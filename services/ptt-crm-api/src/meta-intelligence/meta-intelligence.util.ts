import { computeRoas } from '../performance/performance.util';

export const B10_ANOMALY_TYPES = ['spend_spike', 'cpl_spike', 'roas_low'] as const;

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
