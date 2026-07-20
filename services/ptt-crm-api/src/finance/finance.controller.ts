import {
  Body,
  Controller,
  Get,
  HttpCode,
  HttpStatus,
  Patch,
  Post,
  Query,
  UseGuards,
} from '@nestjs/common';
import { StaffOrInternalKeyGuard } from '../staff-auth/staff-or-internal-key.guard';
import {
  StaffFinanceConfigureGuard,
  StaffFinanceExportGuard,
  StaffFinanceViewGuard,
} from './guards/staff-finance.guard';
import { FinanceService } from './finance.service';

@Controller('api/crm/finance')
@UseGuards(StaffOrInternalKeyGuard)
export class FinanceController {
  constructor(private readonly finance: FinanceService) {}

  @Get('business-dashboard')
  @UseGuards(StaffFinanceViewGuard)
  businessDashboard(
    @Query('year') year?: string,
    @Query('month') month?: string,
    @Query('trend_months') trendMonths?: string,
  ) {
    return this.finance.businessDashboard(year, month, trendMonths);
  }

  @Get('financials')
  @UseGuards(StaffFinanceViewGuard)
  financials(@Query('year') year?: string, @Query('month') month?: string) {
    return this.finance.financials(year, month);
  }

  @Get('ar-aging')
  @UseGuards(StaffFinanceViewGuard)
  arAging(@Query('as_of') asOf?: string, @Query('am_id') amId?: string) {
    return this.finance.arAging(asOf, amId);
  }

  @Get('recurring-summary')
  @UseGuards(StaffFinanceViewGuard)
  recurringSummary(
    @Query('year') year?: string,
    @Query('month') month?: string,
    @Query('am_id') amId?: string,
  ) {
    return this.finance.recurringSummary(year, month, amId);
  }

  @Get('lead-kpi')
  @UseGuards(StaffFinanceViewGuard)
  leadKpi(
    @Query('year') year?: string,
    @Query('month') month?: string,
    @Query('staff_id') staffId?: string,
  ) {
    return this.finance.leadKpi(year, month, staffId);
  }

  @Post('period-inputs')
  @HttpCode(HttpStatus.OK)
  @UseGuards(StaffFinanceConfigureGuard)
  periodInputs(@Body() body: Record<string, unknown>) {
    return this.finance.periodInputs(body);
  }

  @Get('kpi-alerts')
  @UseGuards(StaffFinanceViewGuard)
  kpiAlerts(@Query('year') year?: string, @Query('month') month?: string) {
    return this.finance.kpiAlerts(year, month);
  }

  @Get('kpi-trends')
  @UseGuards(StaffFinanceViewGuard)
  kpiTrends(
    @Query('year') year?: string,
    @Query('month') month?: string,
    @Query('months') months?: string,
  ) {
    return this.finance.kpiTrends(year, month, months);
  }

  @Get('kpi-config')
  @UseGuards(StaffFinanceViewGuard)
  kpiConfigGet() {
    return this.finance.kpiConfigGet();
  }

  @Patch('kpi-config')
  @UseGuards(StaffFinanceConfigureGuard)
  kpiConfigPatch(@Body() body: Record<string, unknown>) {
    return this.finance.kpiConfigPatch(body);
  }

  @Get('kpi-export')
  @UseGuards(StaffFinanceExportGuard)
  kpiExport(
    @Query('year') year?: string,
    @Query('month') month?: string,
    @Query('format') format?: string,
  ) {
    const fmt = String(format ?? 'json').trim().toLowerCase();
    if (fmt !== 'json') {
      return this.finance.kpiExport(year, month);
    }
    return this.finance.kpiExport(year, month);
  }

  @Post('kpi-alert-cron')
  @HttpCode(HttpStatus.OK)
  kpiAlertCron(
    @Body() body: Record<string, unknown>,
    @Query('year') year?: string,
    @Query('month') month?: string,
  ) {
    return this.finance.kpiAlertCron(body, year, month);
  }

  @Post('kpi-inbox/sync')
  @HttpCode(HttpStatus.OK)
  kpiInboxSync(@Body() body: Record<string, unknown>) {
    return this.finance.kpiInboxSync(body);
  }

  @Get('kpi-inbox/summary')
  @UseGuards(StaffFinanceViewGuard)
  kpiInboxSummary() {
    return this.finance.kpiInboxSummary();
  }
}
