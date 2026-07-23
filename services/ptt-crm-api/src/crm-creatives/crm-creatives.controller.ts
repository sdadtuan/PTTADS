import { Body, Controller, Get, Post, Query, Req, UseGuards } from '@nestjs/common';
import type { Request } from 'express';
import { StaffOrInternalKeyGuard } from '../staff-auth/staff-or-internal-key.guard';
import {
  StaffServiceLifecycleViewGuard,
  StaffServiceLifecycleWriteGuard,
} from '../service-lifecycle/guards/staff-service-lifecycle.guard';
import { CrmCreativesService } from './crm-creatives.service';

@Controller('api/crm/creatives')
@UseGuards(StaffOrInternalKeyGuard, StaffServiceLifecycleViewGuard)
export class CrmCreativesController {
  constructor(private readonly service: CrmCreativesService) {}

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
      title: body.title != null ? String(body.title) : undefined,
      description: body.description != null ? String(body.description) : undefined,
      asset_url: body.asset_url != null ? String(body.asset_url) : undefined,
      asset_type: body.asset_type != null ? String(body.asset_type) : undefined,
      version: body.version != null ? Number(body.version) : undefined,
      resubmit: Boolean(body.resubmit),
      submitted_by: staff?.email,
    });
  }
}
