import { Module } from '@nestjs/common';
import { CampaignWritesModule } from '../campaign-writes/campaign-writes.module';
import { StaffAuthModule } from '../staff-auth/staff-auth.module';
import { ZaloAdsOpsController } from './zalo-ads-ops.controller';
import { ZaloAdsOpsRepository } from './zalo-ads-ops.repository';
import { ZaloAdsOpsService } from './zalo-ads-ops.service';

@Module({
  imports: [StaffAuthModule, CampaignWritesModule],
  controllers: [ZaloAdsOpsController],
  providers: [ZaloAdsOpsRepository, ZaloAdsOpsService],
  exports: [ZaloAdsOpsService],
})
export class ZaloAdsOpsModule {}
