import { Controller, Get, Post, Query, UseGuards } from '@nestjs/common';
import {
  StaffSeoSettingsGuard,
  StaffSeoViewGuard,
} from '../seo-admin/guards/staff-seo-view.guard';
import { StaffOrInternalKeyGuard } from '../staff-auth/staff-or-internal-key.guard';
import { SeoAutomationsService } from './seo-automations.service';

@Controller('api/v1/seo')
@UseGuards(StaffOrInternalKeyGuard, StaffSeoViewGuard)
export class SeoAutomationsController {
  constructor(private readonly automations: SeoAutomationsService) {}

  @Get('automations/status')
  async status(@Query('customer_id') customerId?: string) {
    const cid = customerId ? Number.parseInt(customerId, 10) : undefined;
    return this.automations.status(Number.isNaN(cid ?? NaN) ? undefined : cid);
  }

  @Get('automations/sync-runs')
  async syncRuns(@Query('customer_id') customerId?: string, @Query('limit') limit?: string) {
    const cid = customerId ? Number.parseInt(customerId, 10) : undefined;
    const lim = limit ? Number.parseInt(limit, 10) : 50;
    return this.automations.syncRuns(Number.isNaN(cid ?? NaN) ? undefined : cid, lim);
  }

  @Post('automations/run-alert-checks')
  @UseGuards(StaffSeoSettingsGuard)
  async runAlertChecks() {
    return this.automations.runAlertChecks();
  }
}
