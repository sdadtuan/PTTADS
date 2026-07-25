import { Module } from '@nestjs/common';
import { ConfigModule } from '../config/config.module';
import { StaffAuthModule } from '../staff-auth/staff-auth.module';
import {
  StaffSeoApproveGuard,
  StaffSeoSettingsGuard,
  StaffSeoViewGuard,
} from '../seo-admin/guards/staff-seo-view.guard';
import { SeoGovernanceController } from './seo-governance.controller';
import { SeoGovernanceRepository } from './seo-governance.repository';
import { SeoGovernanceService } from './seo-governance.service';

@Module({
  imports: [ConfigModule, StaffAuthModule],
  controllers: [SeoGovernanceController],
  providers: [
    SeoGovernanceRepository,
    SeoGovernanceService,
    StaffSeoViewGuard,
    StaffSeoSettingsGuard,
    StaffSeoApproveGuard,
  ],
  exports: [SeoGovernanceService, SeoGovernanceRepository],
})
export class SeoGovernanceModule {}
