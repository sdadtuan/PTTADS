import { DatabaseSync } from 'node:sqlite';
import {
  getArAging,
  getCacMetrics,
  getConcentrationMetrics,
  getExecMetrics,
  getLeadKpiSummary,
  getMrrArrMetrics,
  getPortfolioMetrics,
  getRetentionMetrics,
  getRecurringRevenueSummary,
  getServicePackageRollup,
  tableExists,
} from './finance-metrics.util';

export const ALERT_CRITICAL = 'critical';
export const ALERT_WARNING = 'warning';

export const THRESHOLD_DEFAULTS: Record<string, number> = {
  top2_warn_pct: 50,
  top1_warn_pct: 40,
  top2_critical_pct: 70,
  top1_critical_pct: 55,
  ar_overdue_critical_vnd: 50_000_000,
  ontime_warn_pct: 80,
  ontime_min_decided: 2,
  renewal_warn_pct: 70,
  customer_churn_warn_pct: 10,
  customer_churn_min_prev: 3,
  close_rate_warn_pct: 25,
  close_rate_min_qualified: 5,
  low_margin_warn_pct: 20,
  capacity_warn_util_pct: 85,
};

export const THRESHOLD_ENV_KEYS: Record<string, string> = {
  top2_warn_pct: 'PTT_KPI_ALERT_TOP2_WARN_PCT',
  top1_warn_pct: 'PTT_KPI_ALERT_TOP1_WARN_PCT',
  top2_critical_pct: 'PTT_KPI_ALERT_TOP2_CRITICAL_PCT',
  top1_critical_pct: 'PTT_KPI_ALERT_TOP1_CRITICAL_PCT',
  ar_overdue_critical_vnd: 'PTT_KPI_ALERT_AR_OVERDUE_CRITICAL_VND',
  ontime_warn_pct: 'PTT_KPI_ALERT_ONTIME_WARN_PCT',
  ontime_min_decided: 'PTT_KPI_ALERT_ONTIME_MIN_DECIDED',
  renewal_warn_pct: 'PTT_KPI_ALERT_RENEWAL_WARN_PCT',
  customer_churn_warn_pct: 'PTT_KPI_ALERT_CHURN_WARN_PCT',
  customer_churn_min_prev: 'PTT_KPI_ALERT_CHURN_MIN_PREV',
  close_rate_warn_pct: 'PTT_KPI_ALERT_CLOSE_RATE_WARN_PCT',
  close_rate_min_qualified: 'PTT_KPI_ALERT_CLOSE_RATE_MIN_QUALIFIED',
  low_margin_warn_pct: 'PTT_KPI_ALERT_LOW_MARGIN_WARN_PCT',
  capacity_warn_util_pct: 'PTT_KPI_ALERT_CAPACITY_WARN_PCT',
};

const INT_THRESHOLD_KEYS = new Set([
  'ontime_min_decided',
  'customer_churn_min_prev',
  'close_rate_min_qualified',
  'ar_overdue_critical_vnd',
]);

function envNumber(name: string, defaultVal: number): number {
  const raw = String(process.env[name] ?? '').trim();
  if (!raw) return defaultVal;
  const n = Number(raw);
  return Number.isFinite(n) ? n : defaultVal;
}

export function ensureKpiConfigSchema(db: DatabaseSync): void {
  db.exec(`
    CREATE TABLE IF NOT EXISTS crm_finance_kpi_config (
      config_key TEXT PRIMARY KEY,
      config_value TEXT NOT NULL,
      updated_at TEXT NOT NULL DEFAULT ''
    )
  `);
}

export function getAlertThresholds(db: DatabaseSync): Record<string, number> {
  ensureKpiConfigSchema(db);
  const dbRows = db.prepare('SELECT config_key, config_value FROM crm_finance_kpi_config').all() as Array<
    Record<string, unknown>
  >;
  const dbMap: Record<string, string> = {};
  for (const r of dbRows) dbMap[String(r.config_key)] = String(r.config_value);

  const out: Record<string, number> = {};
  for (const [key, defaultVal] of Object.entries(THRESHOLD_DEFAULTS)) {
    if (key in dbMap) {
      const raw = dbMap[key]!.trim();
      const parsed = INT_THRESHOLD_KEYS.has(key) ? parseInt(raw, 10) : parseFloat(raw);
      if (Number.isFinite(parsed)) {
        out[key] = parsed;
        continue;
      }
    }
    const envKey = THRESHOLD_ENV_KEYS[key];
    out[key] = envKey ? envNumber(envKey, defaultVal) : defaultVal;
  }
  return out;
}

export function setAlertThresholds(db: DatabaseSync, updates: Record<string, unknown>): Record<string, number> {
  ensureKpiConfigSchema(db);
  const ts = new Date().toISOString().replace('T', ' ').slice(0, 19);
  for (const [key, value] of Object.entries(updates)) {
    if (!(key in THRESHOLD_DEFAULTS)) continue;
    const val = INT_THRESHOLD_KEYS.has(key)
      ? Math.max(0, Math.trunc(Number(value)))
      : Number(value);
    db.prepare(
      `
      INSERT INTO crm_finance_kpi_config (config_key, config_value, updated_at)
      VALUES (?, ?, ?)
      ON CONFLICT(config_key) DO UPDATE SET
        config_value = excluded.config_value,
        updated_at = excluded.updated_at
    `,
    ).run(key, String(val), ts);
  }
  return getAlertThresholds(db);
}

function prevMonth(year: number, month: number): [number, number] {
  if (month === 1) return [year - 1, 12];
  return [year, month - 1];
}

function monthPoints(endYear: number, endMonth: number, count: number): Array<[number, number]> {
  const points: Array<[number, number]> = [];
  let y = endYear;
  let m = endMonth;
  for (let i = 0; i < Math.max(1, count); i++) {
    points.push([y, m]);
    [y, m] = prevMonth(y, m);
  }
  return points.reverse();
}

export function getFinanceKpiTrends(
  db: DatabaseSync,
  year: number,
  month: number,
  months = 6,
): Record<string, unknown> {
  const count = Math.max(2, Math.min(months, 12));
  const points = monthPoints(year, month, count);
  const labels: string[] = [];
  const mrrSeries: number[] = [];
  const concSeries: number[] = [];
  const cacSeries: number[] = [];

  for (const [y, m] of points) {
    labels.push(`${String(m).padStart(2, '0')}/${y}`);
    const mrr = getMrrArrMetrics(db, y, m);
    const conc = getConcentrationMetrics(db, y, m);
    const cac = getCacMetrics(db, y, m);
    mrrSeries.push(Number(mrr.mrr_bookings_vnd ?? 0));
    concSeries.push(Number(conc.top2_concentration_pct ?? 0));
    cacSeries.push(Number(cac.cac_vnd ?? 0));
  }

  return {
    year,
    month,
    months: count,
    labels,
    mrr_bookings_vnd: mrrSeries,
    top2_concentration_pct: concSeries,
    cac_vnd: cacSeries,
  };
}

export function loadFinanceKpiBundle(db: DatabaseSync, year: number, month: number): Record<string, unknown> {
  return {
    year,
    month,
    ar_aging: getArAging(db),
    recurring_summary: getRecurringRevenueSummary(db, year, month),
    package_rollup: getServicePackageRollup(db, year, month),
    retention_metrics: getRetentionMetrics(db, year, month),
    lead_kpi: getLeadKpiSummary(db, year, month),
    portfolio_metrics: getPortfolioMetrics(db, year, month),
    exec_metrics: getExecMetrics(db, year, month),
  };
}

function alertRow(opts: {
  alertId: string;
  level: string;
  category: string;
  title: string;
  message: string;
  metricKey?: string;
  metricValue?: unknown;
}): Record<string, unknown> {
  return {
    id: opts.alertId,
    level: opts.level,
    category: opts.category,
    title: opts.title,
    message: opts.message,
    metric_key: opts.metricKey ?? null,
    metric_value: opts.metricValue ?? null,
  };
}

export function collectFinanceKpiAlerts(
  db: DatabaseSync,
  year: number,
  month: number,
  bundle?: Record<string, unknown>,
): Record<string, unknown> {
  const data = bundle ?? loadFinanceKpiBundle(db, year, month);
  const thresholds = getAlertThresholds(db);
  const alerts: Record<string, unknown>[] = [];

  const portfolio = data.portfolio_metrics as Record<string, unknown>;
  const conc = portfolio.concentration as Record<string, unknown>;
  const cap = portfolio.capacity as Record<string, unknown>;
  const ar = data.ar_aging as Record<string, unknown>;
  const exec = data.exec_metrics as Record<string, unknown>;
  const ot = exec.delivery_ontime as Record<string, unknown>;
  const ret = data.retention_metrics as Record<string, unknown>;
  const rc = ret.renewal_cohort as Record<string, unknown>;
  const lead = data.lead_kpi as Record<string, unknown>;

  const top1 = Number(conc.top1_share_pct ?? 0);
  const top2 = Number(conc.top2_concentration_pct ?? 0);
  const top2Crit = Number(thresholds.top2_critical_pct);
  const top1Crit = Number(thresholds.top1_critical_pct);
  const top2Warn = Number(thresholds.top2_warn_pct);

  if (top2 >= top2Crit || top1 >= top1Crit) {
    alerts.push(
      alertRow({
        alertId: 'concentration_critical',
        level: ALERT_CRITICAL,
        category: 'portfolio',
        title: 'Rủi ro tập trung doanh thu (cao)',
        message: `Top-1 ${top1.toFixed(1)}% · Top-2 ${top2.toFixed(1)}% tổng thu tháng (ngưỡng cảnh báo Top-2 ${top2Warn.toFixed(0)}%).`,
        metricKey: 'top2_concentration_pct',
        metricValue: top2,
      }),
    );
  } else if (top2 >= top2Warn || top1 >= Number(thresholds.top1_warn_pct)) {
    alerts.push(
      alertRow({
        alertId: 'concentration_warning',
        level: ALERT_WARNING,
        category: 'portfolio',
        title: 'Rủi ro tập trung doanh thu',
        message: `Top-2 KH chiếm ${top2.toFixed(1)}% doanh thu tháng (ngưỡng ${top2Warn.toFixed(0)}%).`,
        metricKey: 'top2_concentration_pct',
        metricValue: top2,
      }),
    );
  }

  const capThresh = Number(thresholds.capacity_warn_util_pct);
  const combinedU = Number(cap.combined_utilization_pct ?? 0);
  const amU = Number(cap.am_utilization_pct ?? 0);
  const spU = Number(cap.sp_utilization_pct ?? 0);
  if (combinedU >= capThresh || amU >= capThresh || spU >= capThresh) {
    alerts.push(
      alertRow({
        alertId: 'capacity_warning',
        level: ALERT_WARNING,
        category: 'portfolio',
        title: 'Công suất team gần full',
        message: `AM ${amU.toFixed(1)}% · SP ${spU.toFixed(1)}% utilization (ngưỡng ${capThresh.toFixed(0)}%).`,
        metricKey: 'combined_utilization_pct',
        metricValue: combinedU,
      }),
    );
  }

  const arCrit = Number(thresholds.ar_overdue_critical_vnd);
  const overdue = Number(ar.total_overdue_vnd ?? 0);
  if (overdue >= arCrit) {
    alerts.push(
      alertRow({
        alertId: 'ar_overdue_critical',
        level: ALERT_CRITICAL,
        category: 'finance',
        title: 'AR quá hạn lớn',
        message: `Tổng AR quá hạn ${overdue.toLocaleString('vi-VN')} ₫ (ngưỡng ${arCrit.toLocaleString('vi-VN')} ₫).`,
        metricKey: 'total_overdue_vnd',
        metricValue: overdue,
      }),
    );
  } else if (overdue > 0) {
    alerts.push(
      alertRow({
        alertId: 'ar_overdue_warning',
        level: ALERT_WARNING,
        category: 'finance',
        title: 'Có khoản AR quá hạn',
        message: `Tổng AR quá hạn ${overdue.toLocaleString('vi-VN')} ₫.`,
        metricKey: 'total_overdue_vnd',
        metricValue: overdue,
      }),
    );
  }

  const ontimeMin = Number(thresholds.ontime_min_decided);
  const ontimeWarn = Number(thresholds.ontime_warn_pct);
  const decided = Number(ot.tasks_decided ?? 0);
  const onTime = Number(ot.on_time_rate_pct ?? 0);
  if (decided >= ontimeMin && onTime < ontimeWarn) {
    alerts.push(
      alertRow({
        alertId: 'delivery_ontime_warning',
        level: ALERT_WARNING,
        category: 'delivery',
        title: 'Delivery trễ hạn',
        message: `On-time ${onTime.toFixed(1)}% trên ${decided} task (ngưỡng ${ontimeWarn.toFixed(0)}%).`,
        metricKey: 'on_time_rate_pct',
        metricValue: onTime,
      }),
    );
  }

  const renewalWarn = Number(thresholds.renewal_warn_pct);
  const renewalDecided = Number(rc.contracts_decided ?? 0);
  const renewalRate = Number(rc.renewal_rate_pct ?? 0);
  if (renewalDecided >= 1 && renewalRate < renewalWarn) {
    alerts.push(
      alertRow({
        alertId: 'renewal_rate_warning',
        level: ALERT_WARNING,
        category: 'retention',
        title: 'Renewal rate thấp',
        message: `${renewalRate.toFixed(1)}% HĐ hết hạn đã quyết định được gia hạn (${rc.renewed}/${renewalDecided}, ngưỡng ${renewalWarn.toFixed(0)}%).`,
        metricKey: 'renewal_rate_pct',
        metricValue: renewalRate,
      }),
    );
  }

  const churnMinPrev = Number(thresholds.customer_churn_min_prev);
  const churnWarn = Number(thresholds.customer_churn_warn_pct);
  const prevActive = Number(ret.active_customers_prev ?? 0);
  const churnPct = Number(ret.customer_churn_pct ?? 0);
  if (prevActive >= churnMinPrev && churnPct > churnWarn) {
    alerts.push(
      alertRow({
        alertId: 'customer_churn_warning',
        level: ALERT_WARNING,
        category: 'retention',
        title: 'Churn khách hàng MoM cao',
        message: `Churn ${churnPct.toFixed(1)}% so với tháng trước (ngưỡng ${churnWarn.toFixed(0)}%).`,
        metricKey: 'customer_churn_pct',
        metricValue: churnPct,
      }),
    );
  }

  const closeMin = Number(thresholds.close_rate_min_qualified);
  const closeWarn = Number(thresholds.close_rate_warn_pct);
  const qualified = Number(lead.qualified_in_month ?? 0);
  const closeCohort = Number(lead.cohort_close_rate_pct ?? 0);
  if (qualified >= closeMin && closeCohort < closeWarn) {
    alerts.push(
      alertRow({
        alertId: 'close_rate_warning',
        level: ALERT_WARNING,
        category: 'sales',
        title: 'Close rate cohort thấp',
        message: `${closeCohort.toFixed(1)}% qualified tháng chốt won (ngưỡng ${closeWarn.toFixed(0)}%).`,
        metricKey: 'cohort_close_rate_pct',
        metricValue: closeCohort,
      }),
    );
  }

  const marginWarn = Number(thresholds.low_margin_warn_pct);
  const pkgRollup = data.package_rollup as Record<string, unknown>;
  for (const pkg of (pkgRollup.packages as Record<string, unknown>[]) ?? []) {
    const recv = Number(pkg.received_month_vnd ?? 0);
    const margin = Number(pkg.gross_margin_month_pct ?? 0);
    if (recv > 0 && margin < marginWarn) {
      const slug = String(pkg.service_slug ?? '');
      alerts.push(
        alertRow({
          alertId: `low_margin_${slug || pkg.service_label || 'pkg'}`,
          level: ALERT_WARNING,
          category: 'margin',
          title: 'Gross margin tháng thấp',
          message: `${pkg.service_label ?? slug}: margin ${margin.toFixed(1)}% (thu ${recv.toLocaleString('vi-VN')} ₫, ngưỡng ${marginWarn.toFixed(0)}%).`,
          metricKey: 'gross_margin_month_pct',
          metricValue: margin,
        }),
      );
    }
  }

  const levelOrder: Record<string, number> = { [ALERT_CRITICAL]: 0, [ALERT_WARNING]: 1 };
  alerts.sort(
    (a, b) =>
      (levelOrder[String(a.level)] ?? 9) - (levelOrder[String(b.level)] ?? 9) ||
      String(a.title).localeCompare(String(b.title), 'vi'),
  );

  return {
    year,
    month,
    alerts,
    alert_count: alerts.length,
    critical_count: alerts.filter((a) => a.level === ALERT_CRITICAL).length,
    warning_count: alerts.filter((a) => a.level === ALERT_WARNING).length,
    has_critical: alerts.some((a) => a.level === ALERT_CRITICAL),
  };
}

function kvRows(pairs: Array<[string, unknown]>): unknown[][] {
  return pairs.map(([k, v]) => [k, v]);
}

export interface ExportSheet {
  name: string;
  headers: string[];
  rows: unknown[][];
}

export function buildFinanceKpiExportSheets(bundle: Record<string, unknown>): ExportSheet[] {
  const year = Number(bundle.year);
  const month = Number(bundle.month);
  const ar = bundle.ar_aging as Record<string, unknown>;
  const rec = bundle.recurring_summary as Record<string, unknown>;
  const pkg = bundle.package_rollup as Record<string, unknown>;
  const ret = bundle.retention_metrics as Record<string, unknown>;
  const rc = ret.renewal_cohort as Record<string, unknown>;
  const lead = bundle.lead_kpi as Record<string, unknown>;
  const portfolio = bundle.portfolio_metrics as Record<string, unknown>;
  const conc = portfolio.concentration as Record<string, unknown>;
  const cap = portfolio.capacity as Record<string, unknown>;
  const exec = bundle.exec_metrics as Record<string, unknown>;
  const cac = exec.cac as Record<string, unknown>;
  const ot = exec.delivery_ontime as Record<string, unknown>;
  const mrr = exec.mrr_arr as Record<string, unknown>;

  const summaryRows = kvRows([
    ['Kỳ', `${String(month).padStart(2, '0')}/${year}`],
    ['AR chờ thu (VNĐ)', ar.total_pending_vnd ?? 0],
    ['AR quá hạn (VNĐ)', ar.total_overdue_vnd ?? 0],
    ['Thu recurring tháng (VNĐ)', rec.received_recurring_vnd ?? 0],
    ['Retention rate MoM (%)', ret.customer_retention_pct ?? 0],
    ['Renewal rate (%)', rc.renewal_rate_pct ?? 0],
    ['Close rate cohort (%)', lead.cohort_close_rate_pct ?? 0],
    ['Top-2 concentration (%)', conc.top2_concentration_pct ?? 0],
    ['AM utilization (%)', cap.am_utilization_pct ?? 0],
    ['CAC (VNĐ)', cac.cac_vnd ?? 0],
    ['Delivery on-time (%)', ot.on_time_rate_pct ?? 0],
    ['MRR bookings (VNĐ)', mrr.mrr_bookings_vnd ?? 0],
    ['ARR bookings (VNĐ)', mrr.arr_bookings_vnd ?? 0],
  ]);

  const arRows = kvRows([
    ['As of', ar.as_of ?? ''],
    ['Tổng chờ thu', ar.total_pending_vnd ?? 0],
    ['Tổng quá hạn', ar.total_overdue_vnd ?? 0],
  ]);
  for (const [key, label] of Object.entries((ar.bucket_labels as Record<string, string>) ?? {})) {
    arRows.push([label, (ar.buckets as Record<string, number>)?.[key] ?? 0]);
  }

  const pkgHeaders = [
    'Gói dịch vụ',
    'Deal',
    'Thu tháng',
    'Chi delivery tháng',
    'Margin tháng (%)',
    'Thu lifetime',
    'Margin lifetime (%)',
    'AR quá hạn',
  ];
  const pkgRows: unknown[][] = [];
  for (const p of (pkg.packages as Record<string, unknown>[]) ?? []) {
    pkgRows.push([
      p.service_label ?? p.service_slug,
      p.lifecycle_count ?? 0,
      p.received_month_vnd ?? 0,
      p.delivery_expenses_month_vnd ?? 0,
      p.gross_margin_month_pct ?? 0,
      p.received_lifetime_vnd ?? 0,
      p.gross_margin_lifetime_pct ?? 0,
      p.ar_overdue_vnd ?? 0,
    ]);
  }

  const topHeaders = ['Khách hàng', 'Thu tháng (VNĐ)', 'Share (%)'];
  const topRows = ((conc.top_customers as Record<string, unknown>[]) ?? []).map((c) => [
    c.customer_name,
    c.received_vnd,
    c.share_pct,
  ]);

  return [
    { name: 'Tom tat', headers: ['Chi so', 'Gia tri'], rows: summaryRows },
    { name: 'AR Aging', headers: ['Chi so', 'Gia tri'], rows: arRows },
    { name: 'Goi dich vu', headers: pkgHeaders, rows: pkgRows },
    { name: 'Top KH', headers: topHeaders, rows: topRows },
  ];
}

export function financeKpiExportFilename(year: number, month: number): string {
  const stamp = new Date().toISOString().slice(0, 10);
  return `crm-finance-kpi-${String(year).padStart(4, '0')}-${String(month).padStart(2, '0')}-${stamp}.json`;
}

export function syncFinanceKpiInboxStub(
  db: DatabaseSync,
  year: number,
  month: number,
): Record<string, unknown> {
  if (!tableExists(db, 'crm_reminders')) {
    return {
      year,
      month,
      period_ref: year * 100 + month,
      synced: 0,
      removed: 0,
      alert_count: 0,
      stub: true,
    };
  }
  const alerts = collectFinanceKpiAlerts(db, year, month);
  return {
    year,
    month,
    period_ref: year * 100 + month,
    synced: Number(alerts.alert_count ?? 0),
    removed: 0,
    alert_count: Number(alerts.alert_count ?? 0),
    stub: true,
  };
}
