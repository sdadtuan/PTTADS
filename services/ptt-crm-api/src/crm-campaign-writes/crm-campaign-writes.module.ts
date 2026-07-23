import { Module } from '@nestjs/common';
import { CampaignWritesModule } from '../campaign-writes/campaign-writes.module';
import { LaunchQaModule } from '../launch-qa/launch-qa.module';
import { StaffAuthModule } from '../staff-auth/staff-auth.module';
import {
  StaffServiceLifecycleWriteGuard,
} from '../service-lifecycle/guards/staff-service-lifecycle.guard';
import { CrmCampaignWritesController } from './crm-campaign-writes.controller';
import { CrmCampaignWritesService } from './crm-campaign-writes.service';
import {
  StaffMetaCampaignWriteApproveGuard,
  StaffMetaCampaignWriteViewGuard,
} from './guards/staff-meta-campaign-write.guard';

@Module({
  imports: [StaffAuthModule, CampaignWritesModule, LaunchQaModule],
  controllers: [CrmCampaignWritesController],
  providers: [
    CrmCampaignWritesService,
    StaffMetaCampaignWriteViewGuard,
    StaffMetaCampaignWriteApproveGuard,
    StaffServiceLifecycleWriteGuard,
  ],
})
export class CrmCampaignWritesModule {}
