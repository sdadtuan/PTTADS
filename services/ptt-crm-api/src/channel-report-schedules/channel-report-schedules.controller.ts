import {
  Body,
  Controller,
  Get,
  HttpCode,
  HttpStatus,
  Param,
  Patch,
  Post,
  Query,
  UseGuards,
} from '@nestjs/common';
import { StaffOrInternalKeyGuard } from '../staff-auth/staff-or-internal-key.guard';
import {
  StaffFacebookAdsViewGuard,
  StaffZaloAdsViewGuard,
} from '../agency/guards/staff-agency-view.guard';
import { StaffAgencyConfigureGuard } from '../agency/guards/staff-agency-configure.guard';
import { ChannelReportSchedulesService } from './channel-report-schedules.service';
import {
  ChannelReportScheduleListResponse,
  ChannelReportScheduleRow,
  CreateChannelReportScheduleBody,
  PatchChannelReportScheduleBody,
} from './channel-report-schedules.types';

@Controller('api/v1/facebook-ads/reports/schedules')
@UseGuards(StaffOrInternalKeyGuard, StaffFacebookAdsViewGuard)
export class MetaReportSchedulesController {
  constructor(private readonly schedules: ChannelReportSchedulesService) {}

  @Get()
  list(
    @Query('client_id') clientId?: string,
    @Query('limit') limit?: string,
    @Query('offset') offset?: string,
  ): Promise<ChannelReportScheduleListResponse> {
    return this.schedules.list('meta', clientId ?? '', {
      limit: limit ? Number(limit) : undefined,
      offset: offset ? Number(offset) : undefined,
    });
  }

  @Post()
  @UseGuards(StaffAgencyConfigureGuard)
  create(@Body() body: CreateChannelReportScheduleBody): Promise<ChannelReportScheduleRow> {
    return this.schedules.create('meta', body);
  }

  @Patch(':id')
  @UseGuards(StaffAgencyConfigureGuard)
  patch(
    @Param('id') id: string,
    @Body() body: PatchChannelReportScheduleBody,
  ): Promise<ChannelReportScheduleRow> {
    return this.schedules.patch('meta', id, body);
  }

  @Post('run-due')
  @HttpCode(HttpStatus.OK)
  @UseGuards(StaffAgencyConfigureGuard)
  runDue(@Query('as_of') asOf?: string) {
    return this.schedules.runDue('meta', asOf);
  }

  @Post(':id/run')
  @HttpCode(HttpStatus.OK)
  @UseGuards(StaffAgencyConfigureGuard)
  run(@Param('id') id: string) {
    return this.schedules.run('meta', id);
  }

  @Post(':id/delete')
  @HttpCode(HttpStatus.OK)
  @UseGuards(StaffAgencyConfigureGuard)
  delete(@Param('id') id: string) {
    return this.schedules.delete('meta', id);
  }
}

@Controller('api/v1/zalo-ads/reports/schedules')
@UseGuards(StaffOrInternalKeyGuard, StaffZaloAdsViewGuard)
export class ZaloReportSchedulesController {
  constructor(private readonly schedules: ChannelReportSchedulesService) {}

  @Get()
  list(
    @Query('client_id') clientId?: string,
    @Query('limit') limit?: string,
    @Query('offset') offset?: string,
  ): Promise<ChannelReportScheduleListResponse> {
    return this.schedules.list('zalo', clientId ?? '', {
      limit: limit ? Number(limit) : undefined,
      offset: offset ? Number(offset) : undefined,
    });
  }

  @Post()
  @UseGuards(StaffAgencyConfigureGuard)
  create(@Body() body: CreateChannelReportScheduleBody): Promise<ChannelReportScheduleRow> {
    return this.schedules.create('zalo', body);
  }

  @Patch(':id')
  @UseGuards(StaffAgencyConfigureGuard)
  patch(
    @Param('id') id: string,
    @Body() body: PatchChannelReportScheduleBody,
  ): Promise<ChannelReportScheduleRow> {
    return this.schedules.patch('zalo', id, body);
  }

  @Post('run-due')
  @HttpCode(HttpStatus.OK)
  @UseGuards(StaffAgencyConfigureGuard)
  runDue(@Query('as_of') asOf?: string) {
    return this.schedules.runDue('zalo', asOf);
  }

  @Post(':id/run')
  @HttpCode(HttpStatus.OK)
  @UseGuards(StaffAgencyConfigureGuard)
  run(@Param('id') id: string) {
    return this.schedules.run('zalo', id);
  }

  @Post(':id/delete')
  @HttpCode(HttpStatus.OK)
  @UseGuards(StaffAgencyConfigureGuard)
  delete(@Param('id') id: string) {
    return this.schedules.delete('zalo', id);
  }
}
