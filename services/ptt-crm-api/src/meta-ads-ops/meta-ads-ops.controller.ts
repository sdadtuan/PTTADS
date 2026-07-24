import { Controller, Get, Post, Body, Query, Param, UseGuards } from '@nestjs/common';
import { StaffOrInternalKeyGuard } from '../staff-auth/staff-or-internal-key.guard';
import {
  StaffMetaAdsOpsSubmitGuard,
  StaffMetaAdsOpsViewGuard,
} from './guards/staff-meta-ads-ops.guard';
import { MetaAdsOpsService } from './meta-ads-ops.service';
import type { MetaAdsOpsEditSubmitBody, MetaAdsOpsLaunchBody } from './meta-ads-ops.types';

@Controller('api/v1/meta/ads-ops')
export class MetaAdsOpsController {
  constructor(private readonly adsOps: MetaAdsOpsService) {}

  @Get('templates')
  @UseGuards(StaffOrInternalKeyGuard, StaffMetaAdsOpsViewGuard)
  templates() {
    return this.adsOps.listTemplates();
  }

  @Get('preflight')
  @UseGuards(StaffOrInternalKeyGuard, StaffMetaAdsOpsViewGuard)
  preflight(@Query('client_id') clientId: string) {
    return this.adsOps.getPreflight(String(clientId ?? '').trim());
  }

  @Post('creative/upload')
  @UseGuards(StaffOrInternalKeyGuard, StaffMetaAdsOpsSubmitGuard)
  uploadCreative(
    @Body()
    body: { client_id: string; creative_submission_id: string; external_account_id?: string },
  ) {
    return this.adsOps.uploadCreative(body);
  }

  @Post('launch')
  @UseGuards(StaffOrInternalKeyGuard, StaffMetaAdsOpsSubmitGuard)
  launch(@Body() body: MetaAdsOpsLaunchBody) {
    return this.adsOps.submitLaunch(body);
  }

  @Get('requests/:id')
  @UseGuards(StaffOrInternalKeyGuard, StaffMetaAdsOpsViewGuard)
  requestStatus(@Param('id') id: string) {
    return this.adsOps.getRequestStatus(id);
  }

  @Get('deep-link')
  @UseGuards(StaffOrInternalKeyGuard, StaffMetaAdsOpsViewGuard)
  deepLink(
    @Query('client_id') clientId: string,
    @Query('external_campaign_id') campaignId?: string,
    @Query('external_ad_id') adId?: string,
  ) {
    return this.adsOps.getDeepLink({
      client_id: clientId,
      external_campaign_id: campaignId,
      external_ad_id: adId,
    });
  }

  @Get('edit/snapshot')
  @UseGuards(StaffOrInternalKeyGuard, StaffMetaAdsOpsViewGuard)
  editSnapshot(@Query('client_id') clientId: string, @Query('external_ad_id') adId: string) {
    return this.adsOps.getEditSnapshot(String(clientId ?? '').trim(), String(adId ?? '').trim());
  }

  @Get('edit/preflight')
  @UseGuards(StaffOrInternalKeyGuard, StaffMetaAdsOpsViewGuard)
  editPreflight(
    @Query('client_id') clientId: string,
    @Query('external_ad_id') adId: string,
    @Query('action') action?: string,
    @Query('creative_submission_id') creativeSubmissionId?: string,
    @Query('disapproved_ack') disapprovedAck?: string,
    @Query('effective_status') effectiveStatus?: string,
  ) {
    return this.adsOps.getEditPreflight({
      client_id: clientId,
      external_ad_id: adId,
      action,
      creative_submission_id: creativeSubmissionId,
      disapproved_ack: disapprovedAck,
      effective_status: effectiveStatus,
    });
  }

  @Post('edit/submit')
  @UseGuards(StaffOrInternalKeyGuard, StaffMetaAdsOpsSubmitGuard)
  editSubmit(@Body() body: MetaAdsOpsEditSubmitBody) {
    return this.adsOps.submitEdit(body);
  }
}
