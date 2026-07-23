import { Body, Controller, Get, Param, Post, Query, Req, UseGuards } from '@nestjs/common';
import type { Request } from 'express';
import { StaffOrInternalKeyGuard } from '../staff-auth/staff-or-internal-key.guard';
import {
  StaffServiceLifecycleWriteGuard,
} from '../service-lifecycle/guards/staff-service-lifecycle.guard';
import {
  StaffMetaCampaignWriteApproveGuard,
  StaffMetaCampaignWriteViewGuard,
} from './guards/staff-meta-campaign-write.guard';
import { CrmCampaignWritesService } from './crm-campaign-writes.service';

@Controller('api/crm/campaign-writes')
@UseGuards(StaffOrInternalKeyGuard, StaffMetaCampaignWriteViewGuard)
export class CrmCampaignWritesController {
  constructor(private readonly service: CrmCampaignWritesService) {}

  @Get('stats')
  stats() {
    return this.service.stats();
  }

  @Get()
  list(
    @Query('status') status?: string,
    @Query('client_id') clientId?: string,
    @Query('external_campaign_id') externalCampaignId?: string,
    @Query('limit') limit?: string,
  ) {
    const lim = limit ? Number(limit) : 100;
    return this.service.list({
      status,
      clientId,
      externalCampaignId,
      limit: Number.isFinite(lim) ? lim : 100,
    });
  }

  @Post('submit')
  @UseGuards(StaffServiceLifecycleWriteGuard)
  submit(@Body() body: Record<string, unknown>, @Req() req: Request) {
    const staff = (req as Request & { staffUser?: { email?: string } }).staffUser;
    return this.service.submit({
      client_id: body.client_id != null ? String(body.client_id) : undefined,
      external_campaign_id:
        body.external_campaign_id != null ? String(body.external_campaign_id) : undefined,
      external_campaign_name:
        body.external_campaign_name != null ? String(body.external_campaign_name) : undefined,
      daily_budget_vnd: body.daily_budget_vnd != null ? Number(body.daily_budget_vnd) : undefined,
      change_type: body.change_type != null ? String(body.change_type) : undefined,
      submitted_by: staff?.email,
    });
  }

  @Post(':id/approve')
  @UseGuards(StaffMetaCampaignWriteApproveGuard)
  approve(@Param('id') id: string, @Body() body: Record<string, unknown>, @Req() req: Request) {
    const staff = (req as Request & { staffUser?: { email?: string } }).staffUser;
    return this.service.approve(id, {
      approved_by: staff?.email ?? (body.approved_by != null ? String(body.approved_by) : undefined),
      note: body.note != null ? String(body.note) : undefined,
    });
  }

  @Post(':id/reject')
  @UseGuards(StaffMetaCampaignWriteApproveGuard)
  reject(@Param('id') id: string, @Body() body: Record<string, unknown>, @Req() req: Request) {
    const staff = (req as Request & { staffUser?: { email?: string } }).staffUser;
    return this.service.reject(id, {
      approved_by: staff?.email ?? (body.approved_by != null ? String(body.approved_by) : undefined),
      note: body.note != null ? String(body.note) : undefined,
    });
  }
}
