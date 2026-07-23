import {
  Body,
  Controller,
  Get,
  HttpCode,
  HttpStatus,
  Param,
  ParseIntPipe,
  Post,
  Query,
  UseGuards,
} from '@nestjs/common';
import { StaffOrInternalKeyGuard } from '../staff-auth/staff-or-internal-key.guard';
import { StaffSopViewGuard, StaffSopWriteGuard } from './guards/staff-sop.guard';
import { SopService } from './sop.service';
import { CreateSopRunBody } from './sop.types';

@Controller('api/crm/sop')
@UseGuards(StaffOrInternalKeyGuard, StaffSopViewGuard)
export class SopController {
  constructor(private readonly sop: SopService) {}

  @Get('templates')
  listTemplates(@Query('include_inactive') includeInactive?: string) {
    return this.sop.listTemplates(includeInactive);
  }

  @Get('templates/:id/steps')
  listTemplateSteps(@Param('id', ParseIntPipe) id: number) {
    return this.sop.listTemplateSteps(id);
  }

  @Get('templates/:id')
  getTemplate(@Param('id', ParseIntPipe) id: number) {
    return this.sop.getTemplate(id);
  }

  @Get('overdue-tasks')
  listOverdueTasks(@Query('limit') limit?: string) {
    return this.sop.listOverdueTasks(limit);
  }

  @Get('runs')
  listRuns(@Query('status') status?: string) {
    return this.sop.listRuns(status);
  }

  @Post('runs')
  @HttpCode(HttpStatus.CREATED)
  @UseGuards(StaffSopWriteGuard)
  createRun(@Body() body: CreateSopRunBody) {
    return this.sop.createRun(body);
  }
}
