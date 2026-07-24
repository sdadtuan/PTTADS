import { Body, Controller, Delete, Get, Param, Post, Query, Req, UseGuards } from '@nestjs/common';
import type { Request } from 'express';
import { StaffOrInternalKeyGuard } from '../staff-auth/staff-or-internal-key.guard';
import {
  StaffMetaCreativeRegistryEditGuard,
  StaffMetaCreativeRegistryViewGuard,
} from './guards/staff-meta-creative-registry.guard';
import { MetaCreativeRegistryService } from './meta-creative-registry.service';
import {
  MetaCreativeLinkMutationResponse,
  MetaCreativeLinkResolveResponse,
  MetaCreativeLinksListResponse,
} from './meta-creative-registry.types';

@Controller('api/v1/meta/creative-links')
export class MetaCreativeRegistryController {
  constructor(private readonly registry: MetaCreativeRegistryService) {}

  @Get()
  @UseGuards(StaffOrInternalKeyGuard, StaffMetaCreativeRegistryViewGuard)
  listLinks(
    @Query('client_id') clientId?: string,
    @Query('external_ad_id') externalAdId?: string,
    @Query('external_campaign_id') externalCampaignId?: string,
    @Query('creative_submission_id') creativeSubmissionId?: string,
    @Query('active_only') activeOnly?: string,
    @Query('limit') limit?: string,
  ): Promise<MetaCreativeLinksListResponse> {
    return this.registry.listLinks({
      client_id: clientId,
      external_ad_id: externalAdId,
      external_campaign_id: externalCampaignId,
      creative_submission_id: creativeSubmissionId,
      active_only: activeOnly,
      limit,
    });
  }

  @Get('resolve')
  @UseGuards(StaffOrInternalKeyGuard, StaffMetaCreativeRegistryViewGuard)
  resolveLink(
    @Query('client_id') clientId?: string,
    @Query('external_ad_id') externalAdId?: string,
  ): Promise<MetaCreativeLinkResolveResponse> {
    return this.registry.resolveLink({ client_id: clientId, external_ad_id: externalAdId });
  }

  @Post()
  @UseGuards(StaffOrInternalKeyGuard, StaffMetaCreativeRegistryEditGuard)
  createLink(
    @Body() body: Record<string, unknown>,
    @Req() req: Request,
  ): Promise<MetaCreativeLinkMutationResponse> {
    const staff = (req as Request & { staffUser?: { email?: string } }).staffUser;
    return this.registry.createLink(body, staff?.email ?? null);
  }

  @Delete(':id')
  @UseGuards(StaffOrInternalKeyGuard, StaffMetaCreativeRegistryEditGuard)
  deactivateLink(@Param('id') id: string): Promise<MetaCreativeLinkMutationResponse> {
    return this.registry.deactivateLink(id);
  }
}
