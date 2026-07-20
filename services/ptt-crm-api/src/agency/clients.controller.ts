import {
  Body,
  Controller,
  Get,
  HttpCode,
  HttpException,
  HttpStatus,
  Param,
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
}
