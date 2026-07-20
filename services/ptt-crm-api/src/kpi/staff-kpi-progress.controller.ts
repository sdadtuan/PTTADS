import {
  Controller,
  Get,
  Param,
  ParseIntPipe,
  Patch,
  Body,
  Query,
  UseGuards,
} from '@nestjs/common';
import { StaffOrInternalKeyGuard } from '../staff-auth/staff-or-internal-key.guard';
import { StaffKpiViewGuard } from './guards/staff-kpi.guard';
import { StaffKpiProgressGuard } from './guards/staff-kpi-progress.guard';
import { KpiService } from './kpi.service';
import { PatchStaffKpiProgressBody } from './kpi.types';

@Controller('api/crm/staff/kpi')
@UseGuards(StaffOrInternalKeyGuard, StaffKpiViewGuard)
export class StaffKpiProgressController {
  constructor(private readonly kpi: KpiService) {}

  @Get('export')
  export(
    @Query('year') year?: string,
    @Query('month') month?: string,
    @Query('staff_id') staffId?: string,
  ) {
    return this.kpi.exportStaffKpi(year, month, staffId);
  }

  @Patch(':kpiId')
  @UseGuards(StaffKpiProgressGuard)
  patchProgress(
    @Param('kpiId', ParseIntPipe) kpiId: number,
    @Body() body: PatchStaffKpiProgressBody,
  ) {
    return this.kpi.patchStaffKpiProgress(kpiId, body);
  }
}
