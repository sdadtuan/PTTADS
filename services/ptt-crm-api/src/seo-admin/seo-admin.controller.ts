import {
  Body,
  Controller,
  Get,
  Param,
  ParseIntPipe,
  Post,
  Put,
  Query,
  UseGuards,
} from '@nestjs/common';
import { StaffOrInternalKeyGuard } from '../staff-auth/staff-or-internal-key.guard';
import { StaffSeoSettingsGuard, StaffSeoViewGuard } from './guards/staff-seo-view.guard';
import { SeoAdminService } from './seo-admin.service';
import {
  SeoClientTasksResponse,
  SeoClientWorkspaceResponse,
  SeoClientsListResponse,
  SeoHubResponse,
  SeoSettingsUpdateBody,
  SeoSyncTriggerResponse,
} from './seo-admin.types';

@Controller('api/v1/seo')
@UseGuards(StaffOrInternalKeyGuard, StaffSeoViewGuard)
export class SeoAdminController {
  constructor(private readonly seo: SeoAdminService) {}

  @Get('hub')
  async hub(
    @Query('customer_id') customerId?: string,
    @Query('days') days?: string,
    @Query('market') market?: string,
  ): Promise<SeoHubResponse> {
    const parsedId = customerId ? Number.parseInt(customerId, 10) : undefined;
    return this.seo.hub({
      customerId: Number.isFinite(parsedId) ? parsedId : undefined,
      days: days ? Number.parseInt(days, 10) : undefined,
      market,
    });
  }

  @Get('clients')
  async clients(
    @Query('customer_id') customerId?: string,
    @Query('market') market?: string,
  ): Promise<SeoClientsListResponse> {
    const parsedId = customerId ? Number.parseInt(customerId, 10) : undefined;
    return this.seo.listClients({
      customerId: Number.isFinite(parsedId) ? parsedId : undefined,
      market,
    });
  }

  @Get('clients/:id')
  async clientWorkspace(@Param('id', ParseIntPipe) id: number): Promise<SeoClientWorkspaceResponse> {
    return this.seo.getClientWorkspace(id);
  }

  @Get('clients/:id/tasks')
  async clientTasks(@Param('id', ParseIntPipe) id: number): Promise<SeoClientTasksResponse> {
    return this.seo.listTasks(id);
  }

  @Get('clients/:id/settings')
  async clientSettings(@Param('id', ParseIntPipe) id: number) {
    return this.seo.getSettings(id);
  }

  @Put('clients/:id/settings')
  @UseGuards(StaffSeoSettingsGuard)
  async updateClientSettings(
    @Param('id', ParseIntPipe) id: number,
    @Body() body: SeoSettingsUpdateBody,
  ) {
    return this.seo.updateSettings(id, body);
  }

  @Post('clients/:id/sync/:source')
  @UseGuards(StaffSeoSettingsGuard)
  async triggerSync(
    @Param('id', ParseIntPipe) id: number,
    @Param('source') source: string,
  ): Promise<SeoSyncTriggerResponse> {
    return this.seo.triggerSync(id, source);
  }

  @Get('clients/:id/gsc/oauth/url')
  @UseGuards(StaffSeoSettingsGuard)
  gscOAuthStart(
    @Param('id', ParseIntPipe) id: number,
    @Query('site_url') siteUrl?: string,
  ) {
    return this.seo.oauthStart(id, 'gsc', { siteUrl });
  }

  @Get('clients/:id/ga4/oauth/url')
  @UseGuards(StaffSeoSettingsGuard)
  ga4OAuthStart(
    @Param('id', ParseIntPipe) id: number,
    @Query('property_id') propertyId?: string,
  ) {
    return this.seo.oauthStart(id, 'ga4', { propertyId });
  }
}
