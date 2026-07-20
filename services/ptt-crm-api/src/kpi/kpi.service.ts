import {
  BadRequestException,
  ConflictException,
  Injectable,
  NotFoundException,
} from '@nestjs/common';
import { KpiSqliteRepository } from './kpi-sqlite.repository';
import {
  CreateKpiMetricBody,
  PatchKpiMetricBody,
  PatchStaffKpiProgressBody,
} from './kpi.types';

@Injectable()
export class KpiService {
  constructor(private readonly sqlite: KpiSqliteRepository) {}

  listMetrics(includeInactive: boolean) {
    return { metrics: this.sqlite.listMetrics(includeInactive) };
  }

  createMetric(body: CreateKpiMetricBody) {
    const name = String(body.name ?? '').trim();
    if (!name) {
      throw new BadRequestException({ error: 'Thiếu tên chỉ tiêu' });
    }
    try {
      return this.sqlite.createMetric({ ...body, name });
    } catch (err) {
      if (err instanceof Error && err.message === 'DUPLICATE_CODE') {
        throw new ConflictException({ error: 'Mã chỉ tiêu đã tồn tại' });
      }
      throw err;
    }
  }

  patchMetric(metricId: number, body: PatchKpiMetricBody) {
    if ('name' in body && body.name != null) {
      const nm = String(body.name).trim();
      if (!nm) {
        throw new BadRequestException({ error: 'Tên không được trống' });
      }
    }
    try {
      const updated = this.sqlite.patchMetric(metricId, body);
      if (!updated) {
        throw new NotFoundException({ error: 'Không tìm thấy chỉ tiêu' });
      }
      return updated;
    } catch (err) {
      if (err instanceof Error && err.message === 'DUPLICATE_CODE') {
        throw new ConflictException({ error: 'Mã chỉ tiêu đã tồn tại' });
      }
      throw err;
    }
  }

  listStaffKpi(year?: string, month?: string, staffId?: string) {
    const parsed = this.parseYearMonth(year, month);
    let sid: number | undefined;
    if (staffId) {
      const n = Number(staffId);
      if (!Number.isFinite(n) || n <= 0) {
        throw new BadRequestException({ error: 'staff_id không hợp lệ' });
      }
      sid = n;
    }
    return { staff_kpi: this.sqlite.listStaffKpi(parsed.year, parsed.month, sid) };
  }

  listAlerts(year?: string, month?: string, staffId?: string) {
    const parsed = this.parseYearMonth(year, month);
    let sid: number | undefined;
    if (staffId) {
      const n = Number(staffId);
      if (!Number.isFinite(n) || n <= 0) {
        throw new BadRequestException({ error: 'staff_id không hợp lệ' });
      }
      sid = n;
    }
    return this.sqlite.listKpiAlerts(parsed.year, parsed.month, sid);
  }

  boardSummary(year?: string, month?: string) {
    const parsed = this.parseYearMonth(year, month, true);
    const alerts = this.sqlite.listKpiAlerts(parsed.year, parsed.month);
    const staffKpi = this.sqlite.listStaffKpi(parsed.year, parsed.month);
    const staffIds = new Set(staffKpi.map((row) => row.staff_id));
    return {
      year: parsed.year,
      month: parsed.month,
      summary: alerts.summary,
      staff_count: staffIds.size,
      kpi_count: staffKpi.length,
      alerts: alerts.alerts,
    };
  }

  chart(metricIdRaw?: string, year?: string, month?: string, staffId?: string) {
    const metricId = Number(metricIdRaw ?? 0);
    if (!Number.isFinite(metricId) || metricId <= 0) {
      throw new BadRequestException({ error: 'Cần metric_id (chỉ tiêu để vẽ biểu đồ)' });
    }
    const parsed = this.parseYearMonth(year, month);
    let sid: number | undefined;
    if (staffId) {
      const n = Number(staffId);
      if (!Number.isFinite(n) || n <= 0) {
        throw new BadRequestException({ error: 'staff_id không hợp lệ' });
      }
      sid = n;
    }
    const chart = this.sqlite.fetchKpiChart(metricId, parsed.year, parsed.month, sid);
    if (!chart) {
      throw new NotFoundException({ error: 'Không tìm thấy chỉ tiêu' });
    }
    return chart;
  }

  exportStaffKpi(year?: string, month?: string, staffId?: string) {
    const parsed = this.parseYearMonth(year, month);
    let sid: number | undefined;
    if (staffId) {
      const n = Number(staffId);
      if (!Number.isFinite(n) || n <= 0) {
        throw new BadRequestException({ error: 'staff_id không hợp lệ' });
      }
      sid = n;
    }
    return this.sqlite.exportStaffKpi(parsed.year, parsed.month, sid);
  }

  patchStaffKpiProgress(kpiId: number, body: PatchStaffKpiProgressBody) {
    const updated = this.sqlite.patchStaffKpiProgress(kpiId, body);
    if (!updated) {
      throw new NotFoundException({ error: 'Không tìm thấy KPI' });
    }
    return updated;
  }

  staffRoleMetrics(staffId: number, role?: string, year?: string, month?: string) {
    if (!this.sqlite.staffExists(staffId)) {
      throw new NotFoundException({ error: 'Không tìm thấy staff' });
    }
    const roleNorm = String(role ?? 'am').trim().toLowerCase();
    if (roleNorm !== 'am' && roleNorm !== 'sp') {
      throw new BadRequestException({ error: 'role phải là am hoặc sp' });
    }
    const parsed = this.parseYearMonth(year, month, true);
    return this.sqlite.computeStaffRoleMetrics(
      staffId,
      roleNorm,
      parsed.year,
      parsed.month,
    );
  }

  private parseYearMonth(
    yearRaw?: string,
    monthRaw?: string,
    defaultNow = false,
  ): { year: number; month: number } {
    const now = new Date();
    let year = Number(yearRaw ?? (defaultNow ? now.getFullYear() : 0));
    let month = Number(monthRaw ?? (defaultNow ? now.getMonth() + 1 : 0));
    if (!Number.isFinite(year) || !Number.isFinite(month)) {
      throw new BadRequestException({ error: 'year/month không hợp lệ' });
    }
    if (year < 2000 || year > 2100 || month < 1 || month > 12) {
      throw new BadRequestException({ error: 'Kỳ không hợp lệ' });
    }
    return { year, month };
  }
}
