import { Controller, Get, Query, UseGuards } from '@nestjs/common';
import { StaffOrInternalKeyGuard } from '../staff-auth/staff-or-internal-key.guard';
import { StaffMetricsViewGuard } from './guards/staff-metrics.guard';
import { MetricsService } from './metrics.service';
import { CrossChannelSummaryResponse } from './metrics.types';

@Controller('api/v1/metrics')
export class MetricsController {
  constructor(private readonly metrics: MetricsService) {}

  @Get('cross-channel/summary')
  @UseGuards(StaffOrInternalKeyGuard, StaffMetricsViewGuard)
  crossChannelSummary(
    @Query('days') days?: string,
    @Query('client_id') clientId?: string,
    @Query('date_from') dateFrom?: string,
    @Query('date_to') dateTo?: string,
  ): Promise<CrossChannelSummaryResponse> {
    return this.metrics.crossChannelSummary({
      days,
      client_id: clientId,
      date_from: dateFrom,
      date_to: dateTo,
    });
  }
}
