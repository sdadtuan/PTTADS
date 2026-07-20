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

  @Get(':id/tasks')
  listTasks(@Param('id', ParseIntPipe) id: number) {
    return this.serviceLifecycle.listTasks(id);
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

  @Patch(':id')
  @UseGuards(StaffServiceLifecycleWriteGuard)
  patch(@Param('id', ParseIntPipe) id: number, @Body() body: PatchServiceLifecycleBody) {
    return this.serviceLifecycle.patch(id, body);
  }
}
