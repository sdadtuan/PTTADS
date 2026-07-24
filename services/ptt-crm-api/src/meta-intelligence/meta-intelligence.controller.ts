import { Body, Controller, Get, Param, Patch, Post, Query, UseGuards } from '@nestjs/common';
import { StaffOrInternalKeyGuard } from '../staff-auth/staff-or-internal-key.guard';
import { StaffMetaIntelligenceConfigureGuard } from './guards/staff-meta-intelligence-configure.guard';
import { StaffMetaIntelligenceViewGuard } from './guards/staff-meta-intelligence.guard';
import { MetaIntelligenceService } from './meta-intelligence.service';
import {
  MetaAnomaliesListResponse,
  MetaBudgetRecommendationsResponse,
  MetaDailyInsightsResponse,
  MetaInsightsBreakdownResponse,
  MetaInsightsBreakdownRow,
  MetaForecastResponse,
  MetaIntelligenceSnapshotResponse,
  MetaPixelMutationResponse,
  MetaPixelsListResponse,
  MetaRoasResponse,
} from './meta-intelligence.types';

@Controller('api/v1/meta')
export class MetaIntelligenceController {
  constructor(private readonly intelligence: MetaIntelligenceService) {}

  @Get('anomalies')
  @UseGuards(StaffOrInternalKeyGuard, StaffMetaIntelligenceViewGuard)
  listAnomalies(
    @Query('client_id') clientId?: string,
    @Query('limit') limit?: string,
    @Query('days') days?: string,
    @Query('mode') mode?: string,
  ): Promise<MetaAnomaliesListResponse> {
    return this.intelligence.listAnomalies({ client_id: clientId, limit, days, mode });
  }

  @Get('forecast')
  @UseGuards(StaffOrInternalKeyGuard, StaffMetaIntelligenceViewGuard)
  getForecast(
    @Query('client_id') clientId?: string,
    @Query('metric') metric?: string,
    @Query('days') days?: string,
  ): Promise<MetaForecastResponse> {
    return this.intelligence.getForecast({ client_id: clientId, metric, days });
  }

  @Get('pixels')
  @UseGuards(StaffOrInternalKeyGuard, StaffMetaIntelligenceViewGuard)
  listPixels(
    @Query('client_id') clientId?: string,
    @Query('client_channel_account_id') clientChannelAccountId?: string,
  ): Promise<MetaPixelsListResponse> {
    return this.intelligence.listPixels({
      client_id: clientId,
      client_channel_account_id: clientChannelAccountId,
    });
  }

  @Post('pixels')
  @UseGuards(StaffOrInternalKeyGuard, StaffMetaIntelligenceConfigureGuard)
  createPixel(@Body() body: Record<string, unknown>): Promise<MetaPixelMutationResponse> {
    return this.intelligence.createPixel(body);
  }

  @Patch('pixels/:id')
  @UseGuards(StaffOrInternalKeyGuard, StaffMetaIntelligenceConfigureGuard)
  patchPixel(
    @Param('id') id: string,
    @Body() body: Record<string, unknown>,
  ): Promise<MetaPixelMutationResponse> {
    return this.intelligence.patchPixel(id, body);
  }

  @Post('intelligence/snapshot')
  @UseGuards(StaffOrInternalKeyGuard, StaffMetaIntelligenceConfigureGuard)
  createSnapshot(@Body() body: Record<string, unknown>): Promise<MetaIntelligenceSnapshotResponse> {
    return this.intelligence.createSnapshot(body);
  }

  @Get('roas')
  @UseGuards(StaffOrInternalKeyGuard, StaffMetaIntelligenceViewGuard)
  getRoas(
    @Query('client_id') clientId?: string,
    @Query('from') from?: string,
    @Query('to') to?: string,
    @Query('days') days?: string,
  ): Promise<MetaRoasResponse> {
    return this.intelligence.getRoas({ client_id: clientId, from, to, days });
  }

  @Get('budget-recommendations')
  @UseGuards(StaffOrInternalKeyGuard, StaffMetaIntelligenceViewGuard)
  listBudgetRecommendations(
    @Query('client_id') clientId?: string,
    @Query('days') days?: string,
  ): Promise<MetaBudgetRecommendationsResponse> {
    return this.intelligence.listBudgetRecommendations({ client_id: clientId, days });
  }

  @Get('insights/breakdown')
  @UseGuards(StaffOrInternalKeyGuard, StaffMetaIntelligenceViewGuard)
  getInsightsBreakdown(
    @Query('client_id') clientId?: string,
    @Query('campaign_id') campaignId?: string,
    @Query('date') date?: string,
    @Query('type') type?: string,
    @Query('from') from?: string,
    @Query('to') to?: string,
    @Query('days') days?: string,
  ): Promise<MetaInsightsBreakdownResponse> {
    return this.intelligence.getInsightsBreakdown({
      client_id: clientId,
      campaign_id: campaignId,
      date,
      type,
      from,
      to,
      days,
    });
  }

  @Get('insights/daily')
  @UseGuards(StaffOrInternalKeyGuard, StaffMetaIntelligenceViewGuard)
  listDailyInsights(
    @Query('client_id') clientId?: string,
    @Query('level') level?: string,
    @Query('from') from?: string,
    @Query('to') to?: string,
    @Query('days') days?: string,
    @Query('limit') limit?: string,
  ): Promise<MetaDailyInsightsResponse> {
    return this.intelligence.getDailyInsights({
      client_id: clientId,
      level,
      from,
      to,
      days,
      limit,
    });
  }
}
