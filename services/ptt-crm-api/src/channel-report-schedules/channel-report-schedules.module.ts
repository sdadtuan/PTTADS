import { Module } from '@nestjs/common';
import { ConfigModule } from '../config/config.module';
import { StaffAgencyConfigureGuard } from '../agency/guards/staff-agency-configure.guard';
import {
  StaffFacebookAdsViewGuard,
  StaffZaloAdsViewGuard,
} from '../agency/guards/staff-agency-view.guard';
import { StaffAuthModule } from '../staff-auth/staff-auth.module';
import { WebhooksModule } from '../webhooks/webhooks.module';
import {
  MetaReportSchedulesController,
  ZaloReportSchedulesController,
} from './channel-report-schedules.controller';
import { ChannelReportSchedulesRepository } from './channel-report-schedules.repository';
import {
  ChannelReportSchedulesJobService,
  ChannelReportSchedulesService,
} from './channel-report-schedules.service';

@Module({
  imports: [ConfigModule, WebhooksModule, StaffAuthModule],
  controllers: [MetaReportSchedulesController, ZaloReportSchedulesController],
  providers: [
    ChannelReportSchedulesRepository,
    ChannelReportSchedulesService,
    ChannelReportSchedulesJobService,
    StaffFacebookAdsViewGuard,
    StaffZaloAdsViewGuard,
    StaffAgencyConfigureGuard,
  ],
  exports: [ChannelReportSchedulesService],
})
export class ChannelReportSchedulesModule {}
