import {
  Body,
  Controller,
  Get,
  HttpCode,
  HttpStatus,
  Param,
  ParseIntPipe,
  Patch,
  Post,
  Put,
  Query,
  UseGuards,
} from '@nestjs/common';
import { StaffKpiViewGuard } from '../kpi/guards/staff-kpi.guard';
import { StaffOrInternalKeyGuard } from '../staff-auth/staff-or-internal-key.guard';
import {
  StaffRosterViewGuard,
  StaffRosterWriteGuard,
} from './guards/staff-roster.guard';
import { CrmStaffService } from './crm-staff.service';
import {
  PatchCrmStaffBody,
  StaffCompetencyPutBody,
  StaffImportBody,
  StaffLevelsPutBody,
} from './crm-staff.types';

@Controller('api/crm/staff')
@UseGuards(StaffOrInternalKeyGuard)
export class CrmStaffController {
  constructor(private readonly crmStaff: CrmStaffService) {}

  @Get('kpi')
  @UseGuards(StaffKpiViewGuard)
  listStaffKpi(
    @Query('year') year?: string,
    @Query('month') month?: string,
    @Query('staff_id') staffId?: string,
  ) {
    return this.crmStaff.listStaffKpi(year, month, staffId);
  }

  @Get('levels')
  @UseGuards(StaffRosterViewGuard)
  getLevels() {
    return this.crmStaff.getLevels();
  }

  @Put('levels')
  @UseGuards(StaffRosterWriteGuard)
  saveLevels(@Body() body: StaffLevelsPutBody) {
    return this.crmStaff.saveLevels(body);
  }

  @Get('competency')
  @UseGuards(StaffRosterViewGuard)
  getCompetency() {
    return this.crmStaff.getCompetency();
  }

  @Put('competency')
  @UseGuards(StaffRosterWriteGuard)
  saveCompetency(@Body() body: StaffCompetencyPutBody) {
    return this.crmStaff.saveCompetency(body);
  }

  @Post('import')
  @HttpCode(HttpStatus.OK)
  @UseGuards(StaffRosterWriteGuard)
  importStaff(@Body() body: StaffImportBody) {
    return this.crmStaff.importStaff(body);
  }

  @Get()
  @UseGuards(StaffRosterViewGuard)
  listStaff() {
    return this.crmStaff.listStaff();
  }

  @Get(':id/workspace')
  @UseGuards(StaffRosterViewGuard)
  workspace(@Param('id', ParseIntPipe) id: number) {
    return this.crmStaff.workspace(id);
  }

  @Get(':id')
  @UseGuards(StaffRosterViewGuard)
  detail(@Param('id', ParseIntPipe) id: number) {
    return this.crmStaff.detail(id);
  }

  @Patch(':id')
  @UseGuards(StaffRosterWriteGuard)
  patch(@Param('id', ParseIntPipe) id: number, @Body() body: PatchCrmStaffBody) {
    return this.crmStaff.patch(id, body);
  }
}
