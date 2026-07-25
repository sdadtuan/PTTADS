import { Controller, Get, Param, ParseIntPipe, Post, Query, UseGuards } from '@nestjs/common';
import {
  StaffSeoSettingsGuard,
  StaffSeoViewGuard,
} from '../seo-admin/guards/staff-seo-view.guard';
import { StaffOrInternalKeyGuard } from '../staff-auth/staff-or-internal-key.guard';
import { SeoBiService } from './seo-bi.service';

@Controller('api/v1/seo')
@UseGuards(StaffOrInternalKeyGuard, StaffSeoViewGuard)
export class SeoBiController {
  constructor(private readonly bi: SeoBiService) {}

  @Get('bi/status')
  status() {
    return this.bi.status();
  }

  @Get('bi/dashboard')
  dashboard(@Query('customer_id') customerId?: string, @Query('days') days?: string) {
    const cid = customerId ? Number.parseInt(customerId, 10) : null;
    const d = days ? Number.parseInt(days, 10) : 28;
    return this.bi.dashboard(Number.isNaN(cid ?? NaN) ? null : cid, d);
  }

  @Get('bi/parity')
  parity(@Query('days') days?: string) {
    const d = days ? Number.parseInt(days, 10) : 7;
    return this.bi.parity(d);
  }

  @Post('bi/export-clickhouse')
  @UseGuards(StaffSeoSettingsGuard)
  exportClickhouse(@Query('fact_date') factDate?: string) {
    return this.bi.exportClickhouse(factDate?.trim() || undefined);
  }

  @Get('clients/:id/attribution')
  attribution(
    @Param('id', ParseIntPipe) id: number,
    @Query('days') days?: string,
  ) {
    const d = days ? Number.parseInt(days, 10) : 28;
    return this.bi.attribution(id, d);
  }
}
