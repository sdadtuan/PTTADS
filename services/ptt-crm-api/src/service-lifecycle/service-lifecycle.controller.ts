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
  Req,
  UseGuards,
} from '@nestjs/common';
import type { Request } from 'express';
import { StaffOrInternalKeyGuard } from '../staff-auth/staff-or-internal-key.guard';
import {
  StaffServiceLifecycleViewGuard,
  StaffServiceLifecycleWriteGuard,
} from './guards/staff-service-lifecycle.guard';
import { ServiceLifecycleService } from './service-lifecycle.service';
import { CreateServiceLifecycleBody, PatchServiceLifecycleBody } from './service-lifecycle.types';

@Controller('api/crm/service-lifecycle')
@UseGuards(StaffOrInternalKeyGuard, StaffServiceLifecycleViewGuard)
export class ServiceLifecycleController {
  constructor(private readonly serviceLifecycle: ServiceLifecycleService) {}

  @Get()
  list(
    @Query('service_slug') serviceSlug?: string,
    @Query('am_id') amId?: string,
    @Query('include_draft') includeDraft?: string,
  ) {
    return this.serviceLifecycle.list(serviceSlug, amId, includeDraft);
  }

  @Get(':id/context')
  context(@Param('id', ParseIntPipe) id: number) {
    return this.serviceLifecycle.context(id);
  }

  @Get(':id/advance-info')
  advanceInfo(@Param('id', ParseIntPipe) id: number) {
    return this.serviceLifecycle.advanceInfo(id);
  }

  @Get(':id/events')
  events(@Param('id', ParseIntPipe) id: number) {
    return this.serviceLifecycle.events(id);
  }

  @Get(':id/progress')
  progress(@Param('id', ParseIntPipe) id: number) {
    return this.serviceLifecycle.progress(id);
  }

  @Get(':id/tasks')
  listTasks(@Param('id', ParseIntPipe) id: number) {
    return this.serviceLifecycle.listTasks(id);
  }

  @Get(':id/marketing-plan/validation')
  marketingPlanValidation(@Param('id', ParseIntPipe) id: number) {
    return this.serviceLifecycle.marketingPlanValidation(id);
  }

  @Get(':id/marketing-plan')
  marketingPlan(@Param('id', ParseIntPipe) id: number) {
    return this.serviceLifecycle.marketingPlan(id);
  }

  @Get(':id/presales-summary')
  presalesSummary(@Param('id', ParseIntPipe) id: number) {
    return this.serviceLifecycle.presalesSummary(id);
  }

  @Get(':id/finance-summary')
  financeSummary(@Param('id', ParseIntPipe) id: number) {
    return this.serviceLifecycle.financeSummary(id);
  }

  @Get(':id')
  detail(@Param('id', ParseIntPipe) id: number) {
    return this.serviceLifecycle.detail(id);
  }

  @Post()
  @HttpCode(HttpStatus.CREATED)
  @UseGuards(StaffServiceLifecycleWriteGuard)
  create(@Body() body: CreateServiceLifecycleBody) {
    return this.serviceLifecycle.create(body);
  }

  @Post(':id/tasks')
  @UseGuards(StaffServiceLifecycleWriteGuard)
  createTask(@Param('id', ParseIntPipe) id: number, @Body() body: Record<string, unknown>) {
    return this.serviceLifecycle.createCustomTask(id, body);
  }

  @Post(':id/expenses')
  @UseGuards(StaffServiceLifecycleWriteGuard)
  createExpense(@Param('id', ParseIntPipe) id: number, @Body() body: Record<string, unknown>) {
    return this.serviceLifecycle.createExpense(id, body);
  }

  @Patch(':id/tasks/:taskId')
  @UseGuards(StaffServiceLifecycleWriteGuard)
  patchTask(
    @Param('id', ParseIntPipe) id: number,
    @Param('taskId', ParseIntPipe) taskId: number,
    @Body() body: Record<string, unknown>,
    @Req() req: Request,
  ) {
    const staff = (req as Request & { staffUser?: { id?: number } }).staffUser;
    return this.serviceLifecycle.updateTask(
      id,
      taskId,
      {
        is_done: body.is_done != null ? Boolean(body.is_done) : undefined,
        notes: body.notes != null ? String(body.notes) : undefined,
        form_data: body.form_data as Record<string, unknown> | undefined,
      },
      staff?.id ?? null,
    );
  }

  @Patch(':id/marketing-plan')
  @UseGuards(StaffServiceLifecycleWriteGuard)
  patchMarketingPlan(@Param('id', ParseIntPipe) id: number, @Body() body: Record<string, unknown>) {
    return this.serviceLifecycle.patchMarketingPlan(id, body);
  }

  @Patch(':id')
  @UseGuards(StaffServiceLifecycleWriteGuard)
  patch(@Param('id', ParseIntPipe) id: number, @Body() body: PatchServiceLifecycleBody) {
    return this.serviceLifecycle.patch(id, body);
  }
}
