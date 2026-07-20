import { Module } from '@nestjs/common';
import { PerformanceModule } from '../performance/performance.module';
import { StaffAuthModule } from '../staff-auth/staff-auth.module';
import { AgencyOpsController } from './agency-ops.controller';
import { AgencyRepository } from './agency.repository';
import { AgencyService } from './agency.service';
import { ClientsController } from './clients.controller';
import {
  StaffAgencyViewGuard,
  StaffFacebookAdsViewGuard,
} from './guards/staff-agency-view.guard';
import { StaffAgencyWriteGuard } from './guards/staff-agency-write.guard';

@Module({
  imports: [StaffAuthModule, PerformanceModule],
  controllers: [ClientsController, AgencyOpsController],
  providers: [
    AgencyService,
    AgencyRepository,
    StaffAgencyViewGuard,
    StaffFacebookAdsViewGuard,
    StaffAgencyWriteGuard,
  ],
  exports: [AgencyService],
})
export class AgencyModule {}
