import { Controller, Get, Query, UseGuards } from '@nestjs/common';
import { StaffOrInternalKeyGuard } from '../staff-auth/staff-or-internal-key.guard';
import { StaffMetaIntelligenceViewGuard } from './guards/staff-meta-intelligence.guard';
import { MetaIntelligenceService } from './meta-intelligence.service';
import {
  MetaAnomaliesListResponse,
  MetaBudgetRecommendationsResponse,
  MetaDailyInsightsResponse,
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
  ): Promise<MetaAnomaliesListResponse> {
    return this.intelligence.listAnomalies({ client_id: clientId, limit, days });
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
