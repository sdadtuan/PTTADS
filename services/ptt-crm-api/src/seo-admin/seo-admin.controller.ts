import { Controller, Get, Query, UseGuards } from '@nestjs/common';
import { StaffOrInternalKeyGuard } from '../staff-auth/staff-or-internal-key.guard';
import { StaffSeoViewGuard } from './guards/staff-seo-view.guard';
import { SeoAdminService } from './seo-admin.service';
import { SeoClientsListResponse, SeoHubResponse } from './seo-admin.types';

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
}
