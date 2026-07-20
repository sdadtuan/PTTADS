import { BadRequestException, Injectable } from '@nestjs/common';
import { FinanceSqliteRepository } from './finance-sqlite.repository';

@Injectable()
export class FinanceService {
  constructor(private readonly sqlite: FinanceSqliteRepository) {}

  businessDashboard(yearRaw?: string, monthRaw?: string, trendMonthsRaw?: string) {
    const { year, month } = this.parseYearMonth(yearRaw, monthRaw, true);
    let trendMonths = Number(trendMonthsRaw ?? 6);
    if (!Number.isFinite(trendMonths)) trendMonths = 6;
    trendMonths = Math.max(3, Math.min(Math.trunc(trendMonths), 12));
    return this.sqlite.businessDashboard(year, month, trendMonths);
  }

  financials(yearRaw?: string, monthRaw?: string) {
    const { year, month } = this.parseYearMonth(yearRaw, monthRaw, true);
    return this.sqlite.financials(year, month);
  }

  arAging(asOf?: string, amIdRaw?: string) {
    let amId: number | undefined;
    const amRaw = String(amIdRaw ?? '').trim();
    if (amRaw) {
      const n = Number(amRaw);
      if (!Number.isFinite(n)) throw new BadRequestException({ error: 'am_id không hợp lệ' });
      amId = n;
    }
    return this.sqlite.arAging(asOf, amId);
  }

  recurringSummary(yearRaw?: string, monthRaw?: string, amIdRaw?: string) {
    const { year, month } = this.parseYearMonth(yearRaw, monthRaw, true);
    let amId: number | undefined;
    const amRaw = String(amIdRaw ?? '').trim();
    if (amRaw) {
      const n = Number(amRaw);
      if (!Number.isFinite(n)) throw new BadRequestException({ error: 'am_id không hợp lệ' });
      amId = n;
    }
    return this.sqlite.recurringSummary(year, month, amId);
  }

  leadKpi(yearRaw?: string, monthRaw?: string, staffIdRaw?: string) {
    const { year, month } = this.parseYearMonth(yearRaw, monthRaw, true);
    let staffId: number | undefined;
    const staffRaw = String(staffIdRaw ?? '').trim();
    if (staffRaw) {
      const n = Number(staffRaw);
      if (!Number.isFinite(n)) throw new BadRequestException({ error: 'staff_id không hợp lệ' });
      staffId = n;
    }
    return this.sqlite.leadKpi(year, month, staffId);
  }

  periodInputs(body: Record<string, unknown>) {
    const year = Number(body.year ?? 0);
    const month = Number(body.month ?? 0);
    if (!Number.isFinite(year) || !Number.isFinite(month) || month < 1 || month > 12) {
      throw new BadRequestException({ error: 'year và month không hợp lệ.' });
    }
    let amount: number;
    try {
      amount = Math.max(0, Math.trunc(Number(body.marketing_spend_vnd ?? 0)));
    } catch {
      throw new BadRequestException({ error: 'marketing_spend_vnd không hợp lệ.' });
    }
    return this.sqlite.setPeriodInputs(year, month, amount);
  }

  kpiAlerts(yearRaw?: string, monthRaw?: string) {
    const { year, month } = this.parseYearMonth(yearRaw, monthRaw, true);
    return this.sqlite.kpiAlerts(year, month);
  }

  kpiTrends(yearRaw?: string, monthRaw?: string, monthsRaw?: string) {
    const { year, month } = this.parseYearMonth(yearRaw, monthRaw, true);
    let months = Number(monthsRaw ?? 6);
    if (!Number.isFinite(months)) months = 6;
    return this.sqlite.kpiTrends(year, month, months);
  }

  kpiConfigGet() {
    return this.sqlite.kpiConfigGet();
  }

  kpiConfigPatch(body: Record<string, unknown>) {
    const updates = (body.thresholds ?? body) as Record<string, unknown>;
    if (!updates || typeof updates !== 'object' || Array.isArray(updates)) {
      throw new BadRequestException({ error: 'thresholds phải là object.' });
    }
    return this.sqlite.kpiConfigPatch(updates);
  }

  kpiExport(yearRaw?: string, monthRaw?: string) {
    const { year, month } = this.parseYearMonth(yearRaw, monthRaw, true);
    return this.sqlite.kpiExport(year, month);
  }

  kpiInboxSummary() {
    return this.sqlite.kpiInboxSummary();
  }

  kpiInboxSync(body: Record<string, unknown>) {
    const now = new Date();
    const year = Number(body.year ?? now.getFullYear());
    const month = Number(body.month ?? now.getMonth() + 1);
    return this.sqlite.kpiInboxSync(year, month);
  }

  kpiAlertCron(body: Record<string, unknown>, yearRaw?: string, monthRaw?: string) {
    const now = new Date();
    const year = Number(body.year ?? yearRaw ?? now.getFullYear());
    const month = Number(body.month ?? monthRaw ?? now.getMonth() + 1);
    return this.sqlite.kpiAlertCron(year, month);
  }

  private parseYearMonth(
    yearRaw?: string,
    monthRaw?: string,
    defaultNow = false,
  ): { year: number; month: number } {
    const now = new Date();
    const year = Number(yearRaw ?? (defaultNow ? now.getFullYear() : 0));
    const month = Number(monthRaw ?? (defaultNow ? now.getMonth() + 1 : 0));
    if (!Number.isFinite(year) || !Number.isFinite(month)) {
      throw new BadRequestException({ error: 'year/month không hợp lệ' });
    }
    if (year < 2000 || year > 2100 || month < 1 || month > 12) {
      throw new BadRequestException({ error: 'Kỳ không hợp lệ' });
    }
    return { year, month };
  }
}
