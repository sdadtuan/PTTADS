import { Controller, Get, Query, UseGuards } from '@nestjs/common';
import { StaffOrInternalKeyGuard } from '../staff-auth/staff-or-internal-key.guard';
import { AgencyService } from './agency.service';
import {
  AgencyStatsResponse,
  FacebookHubResponse,
  JobsListResponse,
  NotificationsListResponse,
} from './agency.types';
import {
  StaffAgencyViewGuard,
  StaffFacebookAdsViewGuard,
} from './guards/staff-agency-view.guard';

@Controller('api/v1')
export class AgencyOpsController {
  constructor(private readonly agency: AgencyService) {}

  @Get('agency/stats')
  @UseGuards(StaffOrInternalKeyGuard, StaffAgencyViewGuard)
  async stats(): Promise<AgencyStatsResponse> {
    return this.agency.stats();
  }

  @Get('jobs')
  @UseGuards(StaffOrInternalKeyGuard, StaffAgencyViewGuard)
  async listJobs(
    @Query('status') status?: string,
    @Query('limit') limit?: string,
    @Query('offset') offset?: string,
  ): Promise<JobsListResponse> {
    return this.agency.listJobs({
      status,
      limit: limit !== undefined ? Number(limit) : undefined,
      offset: offset !== undefined ? Number(offset) : undefined,
    });
  }

  @Get('notifications')
  @UseGuards(StaffOrInternalKeyGuard, StaffAgencyViewGuard)
  async listNotifications(
    @Query('recipient_id') recipientId?: string,
    @Query('unread') unread?: string,
    @Query('limit') limit?: string,
  ): Promise<NotificationsListResponse> {
    return this.agency.listNotifications({
      recipient_id: recipientId,
      unread,
      limit: limit !== undefined ? Number(limit) : undefined,
    });
  }

  @Get('facebook-ads/hub')
  @UseGuards(StaffOrInternalKeyGuard, StaffFacebookAdsViewGuard)
  async facebookHub(
    @Query('days') days?: string,
    @Query('to') to?: string,
    @Query('date_to') dateTo?: string,
    @Query('status') status?: string,
  ): Promise<FacebookHubResponse> {
    return this.agency.facebookHub({ days, to, date_to: dateTo, status });
  }

  @Get('crm/hub-campaign-maps')
  @UseGuards(StaffOrInternalKeyGuard, StaffAgencyViewGuard)
  async globalHubMaps(
    @Query('client_id') clientId?: string,
    @Query('campaign_id') campaignId?: string,
    @Query('limit') limit?: string,
  ) {
    return this.agency.hubCampaignMapsGlobal({
      client_id: clientId,
      campaign_id: campaignId,
      limit: limit !== undefined ? Number(limit) : undefined,
    });
  }
}
