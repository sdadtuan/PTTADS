import { Controller, Get, Post, Body, Query, Param, UseGuards } from '@nestjs/common';
import { StaffOrInternalKeyGuard } from '../staff-auth/staff-or-internal-key.guard';
import {
  StaffZaloAdsViewGuard,
} from '../agency/guards/staff-agency-view.guard';
import { StaffAgencyWriteGuard } from '../agency/guards/staff-agency-write.guard';
import { ZaloAdsOpsService } from './zalo-ads-ops.service';
import type { ZaloAdsOpsLaunchBody, ZaloAdsOpsStatusBody } from './zalo-ads-ops.types';

@Controller('api/v1/zalo/ads-ops')
export class ZaloAdsOpsController {
  constructor(private readonly adsOps: ZaloAdsOpsService) {}

  @Get('preflight')
  @UseGuards(StaffOrInternalKeyGuard, StaffZaloAdsViewGuard)
  preflight(@Query('client_id') clientId: string) {
    return this.adsOps.getPreflight(String(clientId ?? '').trim());
  }

  @Post('launch')
  @UseGuards(StaffOrInternalKeyGuard, StaffAgencyWriteGuard)
  launch(@Body() body: ZaloAdsOpsLaunchBody) {
    return this.adsOps.submitLaunch(body);
  }

  @Post('status')
  @UseGuards(StaffOrInternalKeyGuard, StaffAgencyWriteGuard)
  status(@Body() body: ZaloAdsOpsStatusBody) {
    return this.adsOps.submitStatus(body);
  }

  @Get('requests/:id')
  @UseGuards(StaffOrInternalKeyGuard, StaffZaloAdsViewGuard)
  requestStatus(@Param('id') id: string) {
    return this.adsOps.getRequestStatus(id);
  }
}
