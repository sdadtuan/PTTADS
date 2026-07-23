import {
  Body,
  Controller,
  Delete,
  Get,
  HttpCode,
  HttpException,
  HttpStatus,
  Param,
  Patch,
  Post,
  Query,
  UseGuards,
} from '@nestjs/common';
import { StaffOrInternalKeyGuard } from '../staff-auth/staff-or-internal-key.guard';
import { PerformanceService } from '../performance/performance.service';
import { PerformanceQuery } from '../performance/performance.types';
import { AgencyService } from './agency.service';
import {
  AgencyClientDetail,
  AgencyClientsListResponse,
  CreateClientBody,
  HubCampaignMapsResponse,
  OnboardingResponse,
  OnboardingSummaryResponse,
  UpdateClientBody,
  AddChannelAccountBody,
  UpdateChannelAccountBody,
  SetChannelTokenBody,
  CreateHubCampaignMapBody,
  UpdateHubCampaignMapBody,
} from './agency.types';
import { StaffAgencyViewGuard } from './guards/staff-agency-view.guard';
import { StaffAgencyWriteGuard } from './guards/staff-agency-write.guard';

@Controller('api/v1/clients')
@UseGuards(StaffOrInternalKeyGuard, StaffAgencyViewGuard)
export class ClientsController {
  constructor(
    private readonly agency: AgencyService,
    private readonly performance: PerformanceService,
  ) {}

  @Get()
  async listClients(
    @Query('status') status?: string,
    @Query('q') q?: string,
    @Query('owner_am_id') ownerAmId?: string,
    @Query('industry') industry?: string,
    @Query('limit') limit?: string,
    @Query('offset') offset?: string,
  ): Promise<AgencyClientsListResponse> {
    return this.agency.listClients({
      status,
      q,
      owner_am_id: ownerAmId,
      industry,
      limit: limit !== undefined ? Number(limit) : undefined,
      offset: offset !== undefined ? Number(offset) : undefined,
    });
  }

  @Post()
  @HttpCode(HttpStatus.CREATED)
  @UseGuards(StaffAgencyWriteGuard)
  async createClient(@Body() body: CreateClientBody): Promise<AgencyClientDetail> {
    return this.agency.createClient(body);
  }

  @Get(':id')
  async getClient(@Param('id') id: string): Promise<AgencyClientDetail> {
    return this.agency.getClient(id);
  }

  @Get(':id/hub-campaign-maps')
  async hubMaps(
    @Param('id') id: string,
    @Query('channel') channel?: string,
    @Query('include_inactive') includeInactive?: string,
    @Query('limit') limit?: string,
  ): Promise<HubCampaignMapsResponse> {
    return this.agency.hubCampaignMaps(id, {
      channel,
      include_inactive: includeInactive,
      limit: limit !== undefined ? Number(limit) : undefined,
    });
  }

  @Post(':id/hub-campaign-maps')
  @HttpCode(HttpStatus.CREATED)
  @UseGuards(StaffAgencyWriteGuard)
  async createHubMap(@Param('id') id: string, @Body() body: Omit<CreateHubCampaignMapBody, 'client_id'>) {
    return this.agency.createHubCampaignMap({ ...body, client_id: id });
  }

  @Patch(':id/hub-campaign-maps/:mapId')
  @UseGuards(StaffAgencyWriteGuard)
  async updateHubMap(
    @Param('id') id: string,
    @Param('mapId') mapId: string,
    @Body() body: UpdateHubCampaignMapBody,
  ) {
    return this.agency.updateHubCampaignMapById(mapId, body, id);
  }

  @Delete(':id/hub-campaign-maps/:mapId')
  @HttpCode(HttpStatus.OK)
  @UseGuards(StaffAgencyWriteGuard)
  async deleteHubMap(@Param('id') id: string, @Param('mapId') mapId: string) {
    return this.agency.deleteHubCampaignMapById(mapId, id);
  }

  @Get(':id/performance')
  async clientPerformance(@Param('id') id: string, @Query() query: PerformanceQuery) {
    try {
      return await this.performance.listForClient(id, query);
    } catch (err) {
      if (err instanceof HttpException) {
        throw err;
      }
      throw new HttpException({ error: String(err) }, HttpStatus.SERVICE_UNAVAILABLE);
    }
  }

  @Patch(':id')
  @UseGuards(StaffAgencyWriteGuard)
  async patchClient(
    @Param('id') id: string,
    @Body() body: UpdateClientBody,
  ): Promise<AgencyClientDetail> {
    return this.agency.updateClient(id, body);
  }

  @Post(':id/activate')
  @HttpCode(HttpStatus.OK)
  @UseGuards(StaffAgencyWriteGuard)
  async activateClient(
    @Param('id') id: string,
    @Query('force') force?: string,
  ): Promise<AgencyClientDetail> {
    return this.agency.activateClient(id, force === '1' || force === 'true');
  }

  @Get(':id/leads')
  async listClientLeads(@Param('id') id: string) {
    return this.agency.listClientLeads(id);
  }

  @Get(':id/onboarding/workflow-status')
  async onboardingWorkflowStatus(@Param('id') id: string) {
    return this.agency.getOnboardingWorkflowStatus(id);
  }

  @Get(':id/onboarding/summary')
  async onboardingSummary(@Param('id') id: string): Promise<OnboardingSummaryResponse> {
    return this.agency.getOnboardingSummary(id);
  }

  @Post(':id/onboarding/nudge')
  @HttpCode(HttpStatus.OK)
  @UseGuards(StaffAgencyWriteGuard)
  async nudgeOnboardingWorkflow(@Param('id') id: string) {
    return this.agency.nudgeOnboardingWorkflow(id);
  }

  @Post(':id/onboarding/start-workflow')
  @HttpCode(HttpStatus.OK)
  @UseGuards(StaffAgencyWriteGuard)
  async startOnboardingWorkflow(
    @Param('id') id: string,
    @Body() body: { started_by?: string },
  ) {
    return this.agency.startOnboardingWorkflow(id, body?.started_by);
  }

  @Get(':id/onboarding')
  async getOnboarding(@Param('id') id: string): Promise<OnboardingResponse> {
    return this.agency.getOnboarding(id);
  }

  @Patch(':id/onboarding/:itemKey')
  @UseGuards(StaffAgencyWriteGuard)
  async patchOnboardingItem(
    @Param('id') id: string,
    @Param('itemKey') itemKey: string,
    @Body() body: { completed: boolean; completed_by?: string; note?: string },
  ): Promise<OnboardingResponse> {
    return this.agency.patchOnboardingItem(id, itemKey, body);
  }

  @Post(':id/channel-accounts')
  @HttpCode(HttpStatus.CREATED)
  @UseGuards(StaffAgencyWriteGuard)
  async addChannelAccount(
    @Param('id') id: string,
    @Body() body: AddChannelAccountBody,
  ): Promise<AgencyClientDetail> {
    return this.agency.addChannelAccount(id, body);
  }

  @Patch(':id/channel-accounts/:accountId')
  @UseGuards(StaffAgencyWriteGuard)
  async patchChannelAccount(
    @Param('id') id: string,
    @Param('accountId') accountId: string,
    @Body() body: UpdateChannelAccountBody,
  ): Promise<AgencyClientDetail> {
    return this.agency.updateChannelAccount(id, accountId, body);
  }

  @Delete(':id/channel-accounts/:accountId')
  @HttpCode(HttpStatus.OK)
  @UseGuards(StaffAgencyWriteGuard)
  async deleteChannelAccount(
    @Param('id') id: string,
    @Param('accountId') accountId: string,
  ): Promise<{ ok: boolean }> {
    return this.agency.deleteChannelAccount(id, accountId);
  }

  @Patch(':id/channel-accounts/:accountId/token')
  @UseGuards(StaffAgencyWriteGuard)
  async setChannelToken(
    @Param('id') id: string,
    @Param('accountId') accountId: string,
    @Body() body: SetChannelTokenBody,
  ) {
    return this.agency.setChannelAccountToken(id, accountId, body);
  }

  @Post(':id/sync/insights')
  @HttpCode(HttpStatus.OK)
  @UseGuards(StaffAgencyWriteGuard)
  async syncInsights(@Param('id') id: string) {
    return this.agency.syncClientInsights(id);
  }
}
