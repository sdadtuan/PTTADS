import { Controller, Get, Query, UseGuards } from '@nestjs/common';
import { StaffOrInternalKeyGuard } from '../staff-auth/staff-or-internal-key.guard';
import { StaffMetaTrackingViewGuard } from './guards/staff-meta-tracking.guard';
import { MetaTrackingService } from './meta-tracking.service';
import { TrackingHealthResponse } from './meta-tracking.types';

@Controller('api/v1/meta/tracking')
export class MetaTrackingController {
  constructor(private readonly tracking: MetaTrackingService) {}

  @Get('health')
  @UseGuards(StaffOrInternalKeyGuard, StaffMetaTrackingViewGuard)
  getHealth(
    @Query('client_id') clientId?: string,
    @Query('window_days') windowDays?: string,
  ): Promise<TrackingHealthResponse> {
    return this.tracking.getHealth({ client_id: clientId, window_days: windowDays });
  }
}
