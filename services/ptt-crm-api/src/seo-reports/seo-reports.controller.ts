import {
  Body,
  Controller,
  Get,
  Param,
  ParseIntPipe,
  Post,
  Query,
  Res,
  UseGuards,
} from '@nestjs/common';
import { Response } from 'express';
import {
  StaffSeoReportsGuard,
  StaffSeoSettingsGuard,
  StaffSeoViewGuard,
} from '../seo-admin/guards/staff-seo-view.guard';
import { StaffOrInternalKeyGuard } from '../staff-auth/staff-or-internal-key.guard';
import { SeoReportsService } from './seo-reports.service';

@Controller('api/v1/seo')
@UseGuards(StaffOrInternalKeyGuard, StaffSeoViewGuard)
export class SeoReportsController {
  constructor(private readonly reports: SeoReportsService) {}

  @Get('clients/:id/dashboard/:type')
  @UseGuards(StaffSeoReportsGuard)
  async dashboard(@Param('id', ParseIntPipe) id: number, @Param('type') type: string) {
    const dashboard = await this.reports.dashboard(id, type);
    return { ok: true, dashboard };
  }

  @Get('clients/:id/reports/export')
  @UseGuards(StaffSeoReportsGuard)
  async exportReport(
    @Param('id', ParseIntPipe) id: number,
    @Query('type') dashboardType: string,
    @Query('format') format: string,
    @Query('customer_label') customerLabel: string,
    @Res() res: Response,
  ) {
    const fmt = (format ?? 'csv').toLowerCase();
    const type = dashboardType ?? 'executive';
    const out = await this.reports.exportDashboard(id, type, fmt === 'pdf' ? 'html' : fmt, customerLabel);
    res.setHeader('Content-Type', out.contentType);
    res.setHeader('Content-Disposition', `attachment; filename="${out.filename}"`);
    res.send(out.body);
  }

  @Get('clients/:id/reports/schedules')
  @UseGuards(StaffSeoReportsGuard)
  async schedules(@Param('id', ParseIntPipe) id: number) {
    const schedules = await this.reports.listSchedules(id);
    return { ok: true, schedules };
  }

  @Post('clients/:id/reports/schedules')
  @UseGuards(StaffSeoSettingsGuard)
  async createSchedule(@Param('id', ParseIntPipe) id: number, @Body() body: Record<string, unknown>) {
    const schedule = await this.reports.createSchedule(id, body);
    return { ok: true, schedule };
  }

  @Get('alerts')
  async alerts(@Query('status') status?: string) {
    const items = await this.reports.listAlerts(status);
    return { ok: true, alerts: items };
  }

  @Post('alerts/:id/resolve')
  @UseGuards(StaffSeoSettingsGuard)
  async resolveAlert(@Param('id', ParseIntPipe) id: number) {
    return this.reports.resolveAlert(id);
  }

  @Post('alerts/run-checks')
  @UseGuards(StaffSeoSettingsGuard)
  async runChecks() {
    return this.reports.runAlertChecks();
  }
}
