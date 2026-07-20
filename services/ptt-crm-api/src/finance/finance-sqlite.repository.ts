import { Injectable, OnModuleDestroy } from '@nestjs/common';
import { DatabaseSync } from 'node:sqlite';
import { AppConfigService } from '../config/app-config.service';
import {
  buildFinanceKpiExportSheets,
  collectFinanceKpiAlerts,
  getAlertThresholds,
  getFinanceKpiTrends,
  loadFinanceKpiBundle,
  setAlertThresholds,
  syncFinanceKpiInboxStub,
  THRESHOLD_DEFAULTS,
  THRESHOLD_ENV_KEYS,
} from './finance-kpi.util';
import {
  getArAging,
  getCacMetrics,
  getExecMetrics,
  getFinanceKpiInboxSummary,
  getFinancialLifecycleRows,
  getLeadKpiSummary,
  getRecurringRevenueSummary,
  getServicePackageRollup,
  setMarketingSpendVnd,
} from './finance-metrics.util';

@Injectable()
export class FinanceSqliteRepository implements OnModuleDestroy {
  private db: DatabaseSync | null = null;

  constructor(private readonly config: AppConfigService) {}

  private get database(): DatabaseSync {
    if (!this.db) {
      this.db = new DatabaseSync(this.config.sqlitePath);
      this.db.exec('PRAGMA foreign_keys = ON');
    }
    return this.db;
  }

  onModuleDestroy(): void {
    if (this.db) {
      this.db.close();
      this.db = null;
    }
  }

  businessDashboard(year: number, month: number, trendMonths: number): Record<string, unknown> {
    const db = this.database;
    const bundle = loadFinanceKpiBundle(db, year, month);
    return {
      year,
      month,
      trend_months: trendMonths,
      exec_metrics: bundle.exec_metrics,
      kpi_alerts: collectFinanceKpiAlerts(db, year, month, bundle),
      trends: getFinanceKpiTrends(db, year, month, trendMonths),
      thresholds: getAlertThresholds(db),
      kpi_inbox: getFinanceKpiInboxSummary(db),
      ...bundle,
    };
  }

  financials(year: number, month: number): Record<string, unknown> {
    const db = this.database;
    const rows = getFinancialLifecycleRows(db);
    const arAging = getArAging(db);
    const recurringSummary = getRecurringRevenueSummary(db, year, month);
    const packageRollup = getServicePackageRollup(db, year, month);
    const bundle = loadFinanceKpiBundle(db, year, month);
    const kpiAlerts = collectFinanceKpiAlerts(db, year, month, bundle);
    return {
      year,
      month,
      rows,
      ar_aging: arAging,
      recurring_summary: recurringSummary,
      package_rollup: packageRollup,
      retention_metrics: bundle.retention_metrics,
      lead_kpi: bundle.lead_kpi,
      portfolio_metrics: bundle.portfolio_metrics,
      exec_metrics: bundle.exec_metrics,
      kpi_alerts: kpiAlerts,
    };
  }

  arAging(asOf?: string, amId?: number): Record<string, unknown> {
    return getArAging(this.database, { asOf: asOf ?? null, amId: amId ?? null });
  }

  recurringSummary(year: number, month: number, amId?: number): Record<string, unknown> {
    return getRecurringRevenueSummary(this.database, year, month, amId ?? null);
  }

  leadKpi(year: number, month: number, staffId?: number): Record<string, unknown> {
    return getLeadKpiSummary(this.database, year, month, staffId ?? null);
  }

  setPeriodInputs(year: number, month: number, marketingSpendVnd: number): Record<string, unknown> {
    setMarketingSpendVnd(this.database, year, month, marketingSpendVnd);
    return { ok: true, cac: getCacMetrics(this.database, year, month) };
  }

  kpiAlerts(year: number, month: number): Record<string, unknown> {
    return collectFinanceKpiAlerts(this.database, year, month);
  }

  kpiTrends(year: number, month: number, months: number): Record<string, unknown> {
    return getFinanceKpiTrends(this.database, year, month, months);
  }

  kpiConfigGet(): Record<string, unknown> {
    return {
      thresholds: getAlertThresholds(this.database),
      defaults: THRESHOLD_DEFAULTS,
      env_keys: THRESHOLD_ENV_KEYS,
    };
  }

  kpiConfigPatch(updates: Record<string, unknown>): Record<string, unknown> {
    return { ok: true, thresholds: setAlertThresholds(this.database, updates) };
  }

  kpiExport(year: number, month: number): Record<string, unknown> {
    const bundle = loadFinanceKpiBundle(this.database, year, month);
    const sheets = buildFinanceKpiExportSheets(bundle);
    const stamp = new Date().toISOString().slice(0, 10);
    return {
      filename: `crm-finance-kpi-${String(year).padStart(4, '0')}-${String(month).padStart(2, '0')}-${stamp}.json`,
      format: 'json',
      sheets,
    };
  }

  kpiInboxSummary(): Record<string, unknown> {
    return getFinanceKpiInboxSummary(this.database);
  }

  kpiInboxSync(year: number, month: number): Record<string, unknown> {
    return { ok: true, inbox: syncFinanceKpiInboxStub(this.database, year, month) };
  }

  kpiAlertCron(year: number, month: number): Record<string, unknown> {
    const alerts = collectFinanceKpiAlerts(this.database, year, month);
    return {
      ok: true,
      stub: true,
      year,
      month,
      alert_count: alerts.alert_count,
      critical_count: alerts.critical_count,
    };
  }

  execMetrics(year: number, month: number): Record<string, unknown> {
    return getExecMetrics(this.database, year, month);
  }
}
