import {
  Body,
  Controller,
  Delete,
  Get,
  Header,
  HttpCode,
  HttpStatus,
  Param,
  Patch,
  Post,
  Query,
  Res,
  UseGuards,
} from '@nestjs/common';
import type { Response } from 'express';
import { StaffOrInternalKeyGuard } from '../staff-auth/staff-or-internal-key.guard';
import { AgencyService } from './agency.service';
import {
  AgencyStatsResponse,
  FacebookHubResponse,
  JobsListResponse,
  NotificationsListResponse,
  PatchHubCampaignMapBody,
  CreateHubCampaignMapBody,
  UpdateHubCampaignMapBody,
  CreateKpiDefinitionBody,
  UpdateKpiDefinitionBody,
} from './agency.types';
import {
  StaffAgencyViewGuard,
  StaffFacebookAdsViewGuard,
} from './guards/staff-agency-view.guard';
import { StaffAgencyWriteGuard } from './guards/staff-agency-write.guard';

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

  @Post('jobs/:id/replay')
  @HttpCode(HttpStatus.OK)
  @UseGuards(StaffOrInternalKeyGuard, StaffAgencyWriteGuard)
  async replayJob(@Param('id') id: string) {
    return this.agency.replayJob(id);
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

  @Patch('notifications/:id/read')
  @UseGuards(StaffOrInternalKeyGuard, StaffAgencyViewGuard)
  async markNotificationRead(
    @Param('id') id: string,
    @Query('recipient_id') recipientId?: string,
  ) {
    const recipient = (recipientId ?? 'ops').trim() || 'ops';
    return this.agency.markNotificationRead(id, recipient);
  }

  @Post('notifications/mark-all-read')
  @HttpCode(HttpStatus.OK)
  @UseGuards(StaffOrInternalKeyGuard, StaffAgencyViewGuard)
  async markAllNotificationsRead(@Query('recipient_id') recipientId?: string) {
    const recipient = (recipientId ?? 'ops').trim() || 'ops';
    return this.agency.markAllNotificationsRead(recipient);
  }

  @Get('kpi-definitions')
  @UseGuards(StaffOrInternalKeyGuard, StaffAgencyViewGuard)
  async listKpiDefinitions() {
    return this.agency.listKpiDefinitions();
  }

  @Post('kpi-definitions')
  @HttpCode(HttpStatus.CREATED)
  @UseGuards(StaffOrInternalKeyGuard, StaffAgencyWriteGuard)
  async createKpiDefinition(@Body() body: CreateKpiDefinitionBody) {
    return this.agency.createKpiDefinition(body);
  }

  @Patch('kpi-definitions/:code')
  @UseGuards(StaffOrInternalKeyGuard, StaffAgencyWriteGuard)
  async updateKpiDefinition(@Param('code') code: string, @Body() body: UpdateKpiDefinitionBody) {
    return this.agency.updateKpiDefinition(code, body);
  }

  @Delete('kpi-definitions/:code')
  @UseGuards(StaffOrInternalKeyGuard, StaffAgencyWriteGuard)
  async deleteKpiDefinition(@Param('code') code: string) {
    return this.agency.deleteKpiDefinition(code);
  }

  @Get('facebook-ads/migration-status')
  @UseGuards(StaffOrInternalKeyGuard, StaffFacebookAdsViewGuard)
  facebookAdsMigrationStatus(): Record<string, unknown> {
    return this.agency.facebookAdsMigrationStatus();
  }

  @Get('facebook-ads/migration-signoff')
  @UseGuards(StaffOrInternalKeyGuard, StaffFacebookAdsViewGuard)
  facebookAdsMigrationSignoff(): Record<string, unknown> {
    return this.agency.facebookAdsMigrationSignoff();
  }

  @Patch('facebook-ads/migration-signoff/manual-uat')
  @UseGuards(StaffOrInternalKeyGuard, StaffFacebookAdsViewGuard)
  patchFacebookAdsMigrationManualUat(@Body() body: Partial<Record<string, boolean>>) {
    return this.agency.patchFacebookAdsMigrationManualUat(body);
  }

  @Get('facebook-ads/hub')
  @UseGuards(StaffOrInternalKeyGuard, StaffFacebookAdsViewGuard)
  async facebookHub(
    @Query('days') days?: string,
    @Query('to') to?: string,
    @Query('date_to') dateTo?: string,
    @Query('from') from?: string,
    @Query('date_from') dateFrom?: string,
    @Query('status') status?: string,
    @Query('client_id') clientId?: string,
    @Query('q') q?: string,
  ): Promise<FacebookHubResponse> {
    return this.agency.facebookHub({
      days,
      to,
      date_to: dateTo,
      from,
      date_from: dateFrom,
      status,
      client_id: clientId,
      q,
    });
  }

  @Get('facebook-ads/hub/export')
  @UseGuards(StaffOrInternalKeyGuard, StaffFacebookAdsViewGuard)
  @Header('Content-Type', 'text/csv; charset=utf-8')
  async facebookHubExport(
    @Res({ passthrough: true }) res: Response,
    @Query('days') days?: string,
    @Query('to') to?: string,
    @Query('date_to') dateTo?: string,
    @Query('from') from?: string,
    @Query('date_from') dateFrom?: string,
    @Query('status') status?: string,
    @Query('client_id') clientId?: string,
    @Query('q') q?: string,
    @Query('scope') scope?: string,
  ): Promise<string> {
    const out = await this.agency.facebookHubExportCsv({
      days,
      to,
      date_to: dateTo,
      from,
      date_from: dateFrom,
      status,
      client_id: clientId,
      q,
      scope,
    });
    res.setHeader('Content-Disposition', `attachment; filename="${out.filename}"`);
    return out.csv;
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

  @Patch('crm/hub-campaign-maps')
  @UseGuards(StaffOrInternalKeyGuard, StaffAgencyWriteGuard)
  async patchHubCampaignMap(@Body() body: PatchHubCampaignMapBody) {
    return this.agency.patchHubCampaignMap(body);
  }

  @Post('crm/hub-campaign-maps')
  @HttpCode(HttpStatus.CREATED)
  @UseGuards(StaffOrInternalKeyGuard, StaffAgencyWriteGuard)
  async createHubCampaignMap(@Body() body: CreateHubCampaignMapBody) {
    return this.agency.createHubCampaignMap(body);
  }

  @Patch('crm/hub-campaign-maps/:mapId')
  @UseGuards(StaffOrInternalKeyGuard, StaffAgencyWriteGuard)
  async updateHubCampaignMap(
    @Param('mapId') mapId: string,
    @Body() body: UpdateHubCampaignMapBody,
    @Query('client_id') clientId?: string,
  ) {
    return this.agency.updateHubCampaignMapById(mapId, body, clientId?.trim() || undefined);
  }

  @Delete('crm/hub-campaign-maps/:mapId')
  @HttpCode(HttpStatus.OK)
  @UseGuards(StaffOrInternalKeyGuard, StaffAgencyWriteGuard)
  async deleteHubCampaignMap(
    @Param('mapId') mapId: string,
    @Query('client_id') clientId?: string,
  ) {
    return this.agency.deleteHubCampaignMapById(mapId, clientId?.trim() || undefined);
  }
}
