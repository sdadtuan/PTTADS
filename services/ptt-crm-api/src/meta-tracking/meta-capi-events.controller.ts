import { Body, Controller, Get, Param, Post, Query, UseGuards } from '@nestjs/common';
import { StaffOrInternalKeyGuard } from '../staff-auth/staff-or-internal-key.guard';
import {
  StaffMetaTrackingConfigureGuard,
  StaffMetaTrackingViewGuard,
} from './guards/staff-meta-tracking.guard';
import { MetaCapiEventsService } from './meta-tracking.service';
import {
  CapiEventsListResponse,
  CapiFlushResponse,
  CapiRetryResponse,
} from './meta-tracking.types';

@Controller('api/v1/meta/capi')
export class MetaCapiEventsController {
  constructor(private readonly capiEvents: MetaCapiEventsService) {}

  @Get('events')
  @UseGuards(StaffOrInternalKeyGuard, StaffMetaTrackingViewGuard)
  listEvents(
    @Query('client_id') clientId?: string,
    @Query('status') status?: string,
    @Query('event_name') eventName?: string,
    @Query('limit') limit?: string,
    @Query('offset') offset?: string,
  ): Promise<CapiEventsListResponse> {
    return this.capiEvents.listEvents({
      client_id: clientId,
      status,
      event_name: eventName,
      limit,
      offset,
    });
  }

  @Post('events/:id/retry')
  @UseGuards(StaffOrInternalKeyGuard, StaffMetaTrackingConfigureGuard)
  retryEvent(@Param('id') id: string): Promise<CapiRetryResponse> {
    return this.capiEvents.retryEvent(id);
  }

  @Post('flush')
  @UseGuards(StaffOrInternalKeyGuard, StaffMetaTrackingConfigureGuard)
  flushPending(
    @Query('client_id') clientId?: string,
    @Query('limit') limit?: string,
    @Body() body?: { client_id?: string; limit?: number },
  ): Promise<CapiFlushResponse> {
    return this.capiEvents.flushPending({
      client_id: body?.client_id ?? clientId,
      limit: body?.limit != null ? String(body.limit) : limit,
    });
  }
}
