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
  Query,
  UseGuards,
} from '@nestjs/common';
import { StaffOrInternalKeyGuard } from '../staff-auth/staff-or-internal-key.guard';
import { CasesService } from './cases.service';
import { CreateCareReportBody, CreateCaseEventBody, PatchCaseBody } from './cases.types';
import { StaffCasesViewGuard, StaffCasesWriteGuard } from './guards/staff-cases.guard';

@Controller('api/crm/cases')
@UseGuards(StaffOrInternalKeyGuard, StaffCasesViewGuard)
export class CasesController {
  constructor(private readonly cases: CasesService) {}

  @Get()
  list(@Query('q') q?: string, @Query('staff_id') staffId?: string) {
    const sid = staffId ? Number(staffId) : undefined;
    return this.cases.list(q, sid && Number.isFinite(sid) && sid > 0 ? sid : undefined);
  }

  @Get(':id')
  detail(@Param('id', ParseIntPipe) id: number) {
    return this.cases.detail(id);
  }

  @Patch(':id')
  @UseGuards(StaffCasesWriteGuard)
  patch(@Param('id', ParseIntPipe) id: number, @Body() body: PatchCaseBody) {
    return this.cases.patch(id, body);
  }

  @Post(':id/events')
  @HttpCode(HttpStatus.CREATED)
  @UseGuards(StaffCasesWriteGuard)
  addEvent(@Param('id', ParseIntPipe) id: number, @Body() body: CreateCaseEventBody) {
    return this.cases.addEvent(id, body);
  }

  @Post(':id/care-reports')
  @HttpCode(HttpStatus.CREATED)
  @UseGuards(StaffCasesWriteGuard)
  addCareReport(@Param('id', ParseIntPipe) id: number, @Body() body: CreateCareReportBody) {
    return this.cases.addCareReport(id, body);
  }
}
