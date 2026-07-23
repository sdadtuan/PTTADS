import { Controller, Get, Query, UseGuards } from '@nestjs/common';
import { StaffOrInternalKeyGuard } from '../staff-auth/staff-or-internal-key.guard';
import {
  StaffServiceLifecycleViewGuard,
} from '../service-lifecycle/guards/staff-service-lifecycle.guard';
import { LaunchQaHubService } from './launch-qa-hub.service';

@Controller('api/crm/launch-qa')
@UseGuards(StaffOrInternalKeyGuard, StaffServiceLifecycleViewGuard)
export class LaunchQaController {
  constructor(private readonly hub: LaunchQaHubService) {}

  @Get('stats')
  stats() {
    return this.hub.stats();
  }

  @Get('runs')
  listRuns(@Query('status') status?: string, @Query('limit') limit?: string) {
    const lim = limit ? Number(limit) : 100;
    return this.hub.listRuns(status, Number.isFinite(lim) ? lim : 100);
  }
}
