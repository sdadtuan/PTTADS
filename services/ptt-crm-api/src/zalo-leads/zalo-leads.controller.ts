import { Controller, Get, Param, Post, Query, UseGuards } from '@nestjs/common';
import { StaffOrInternalKeyGuard } from '../staff-auth/staff-or-internal-key.guard';
import { StaffZaloAdsViewGuard } from '../agency/guards/staff-agency-view.guard';
import { StaffAgencyWriteGuard } from '../agency/guards/staff-agency-write.guard';
import { ZaloLeadsService } from './zalo-leads.service';
import type {
  ZaloFormPollResponse,
  ZaloFormsListResponse,
  ZaloLeadEventsResponse,
  ZaloLeadsListResponse,
} from './zalo-leads.types';

@Controller('api/v1/zalo')
export class ZaloLeadsController {
  constructor(private readonly zaloLeads: ZaloLeadsService) {}

  @Get('leads')
  @UseGuards(StaffOrInternalKeyGuard, StaffZaloAdsViewGuard)
  listLeads(
    @Query('client_id') clientId?: string,
    @Query('form_id') formId?: string,
    @Query('q') q?: string,
    @Query('limit') limit?: string,
    @Query('offset') offset?: string,
  ): Promise<ZaloLeadsListResponse> {
    return this.zaloLeads.listLeads({
      client_id: clientId,
      form_id: formId,
      q,
      limit: limit !== undefined ? Number(limit) : undefined,
      offset: offset !== undefined ? Number(offset) : undefined,
    });
  }

  @Get('forms')
  @UseGuards(StaffOrInternalKeyGuard, StaffZaloAdsViewGuard)
  listForms(@Query('client_id') clientId?: string): Promise<ZaloFormsListResponse> {
    return this.zaloLeads.listForms({ client_id: clientId });
  }

  @Post('forms/:formId/poll')
  @UseGuards(StaffOrInternalKeyGuard, StaffAgencyWriteGuard, StaffZaloAdsViewGuard)
  pollForm(
    @Param('formId') formId: string,
    @Query('client_id') clientId?: string,
    @Query('force') force?: string,
  ): Promise<ZaloFormPollResponse> {
    return this.zaloLeads.pollForm(formId, {
      client_id: clientId,
      force: force === '1' || force === 'true',
    });
  }

  @Get('leads/:id/events')
  @UseGuards(StaffOrInternalKeyGuard, StaffZaloAdsViewGuard)
  leadEvents(@Param('id') leadId: string): Promise<ZaloLeadEventsResponse> {
    return this.zaloLeads.leadEvents(leadId);
  }
}
