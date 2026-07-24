import { Body, Controller, Get, Param, Patch, Query, UseGuards } from '@nestjs/common';
import { StaffOrInternalKeyGuard } from '../staff-auth/staff-or-internal-key.guard';
import { StaffMetaAlertsAckGuard, StaffMetaAlertsViewGuard } from './guards/staff-meta-alerts.guard';
import { MetaAlertsService } from './meta-alerts.service';
import { MetaAlertAckResponse, MetaAlertsListResponse } from './meta-alerts.types';

@Controller('api/v1/meta/alerts')
export class MetaAlertsController {
  constructor(private readonly metaAlerts: MetaAlertsService) {}

  @Get()
  @UseGuards(StaffOrInternalKeyGuard, StaffMetaAlertsViewGuard)
  list(
    @Query('client_id') clientId?: string,
    @Query('include_ack') includeAck?: string,
    @Query('limit') limit?: string,
  ): Promise<MetaAlertsListResponse> {
    return this.metaAlerts.list({
      client_id: clientId,
      include_ack: includeAck,
      limit,
    });
  }

  @Patch(':id/ack')
  @UseGuards(StaffOrInternalKeyGuard, StaffMetaAlertsAckGuard)
  acknowledge(@Param('id') id: string): Promise<MetaAlertAckResponse> {
    return this.metaAlerts.acknowledge(id);
  }
}
