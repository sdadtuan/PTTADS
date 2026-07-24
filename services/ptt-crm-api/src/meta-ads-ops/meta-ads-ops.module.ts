import { Module } from '@nestjs/common';
import { CampaignWritesModule } from '../campaign-writes/campaign-writes.module';
import { MetaTrackingModule } from '../meta-tracking/meta-tracking.module';
import { StaffAuthModule } from '../staff-auth/staff-auth.module';
import { MetaAdsOpsController } from './meta-ads-ops.controller';
import { MetaAdsOpsRepository } from './meta-ads-ops.repository';
import { MetaAdsOpsService } from './meta-ads-ops.service';
import {
  StaffMetaAdsOpsSubmitGuard,
  StaffMetaAdsOpsViewGuard,
} from './guards/staff-meta-ads-ops.guard';

@Module({
  imports: [StaffAuthModule, CampaignWritesModule, MetaTrackingModule],
  controllers: [MetaAdsOpsController],
  providers: [
    MetaAdsOpsRepository,
    MetaAdsOpsService,
    StaffMetaAdsOpsViewGuard,
    StaffMetaAdsOpsSubmitGuard,
  ],
  exports: [MetaAdsOpsService],
})
export class MetaAdsOpsModule {}
