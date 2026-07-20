import {
  Controller,
  Get,
  Param,
  ParseIntPipe,
  Query,
  UseGuards,
} from '@nestjs/common';
import { StaffOrInternalKeyGuard } from '../staff-auth/staff-or-internal-key.guard';
import { StaffKpiViewGuard } from './guards/staff-kpi.guard';
import { KpiService } from './kpi.service';

@Controller('api/crm/staff-kpi')
@UseGuards(StaffOrInternalKeyGuard, StaffKpiViewGuard)
export class StaffKpiController {
  constructor(private readonly kpi: KpiService) {}

  @Get(':staffId/metrics')
  staffMetrics(
    @Param('staffId', ParseIntPipe) staffId: number,
    @Query('role') role?: string,
    @Query('year') year?: string,
    @Query('month') month?: string,
  ) {
    return this.kpi.staffRoleMetrics(staffId, role, year, month);
  }
}
