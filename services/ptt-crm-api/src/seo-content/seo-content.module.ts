import { Module } from '@nestjs/common';
import { ConfigModule } from '../config/config.module';
import { SeoGovernanceModule } from '../seo-governance/seo-governance.module';
import { SeoCmsModule } from '../seo-cms/seo-cms.module';
import { StaffAuthModule } from '../staff-auth/staff-auth.module';
import {
  StaffSeoApproveGuard,
  StaffSeoSettingsGuard,
  StaffSeoViewGuard,
  StaffSeoWriteGuard,
} from '../seo-admin/guards/staff-seo-view.guard';
import { SeoContentController } from './seo-content.controller';
import { SeoContentRepository } from './seo-content.repository';
import { SeoContentService } from './seo-content.service';

@Module({
  imports: [ConfigModule, StaffAuthModule, SeoGovernanceModule, SeoCmsModule],
  controllers: [SeoContentController],
  providers: [
    SeoContentRepository,
    SeoContentService,
    StaffSeoViewGuard,
    StaffSeoWriteGuard,
    StaffSeoApproveGuard,
    StaffSeoSettingsGuard,
  ],
  exports: [SeoContentService],
})
export class SeoContentModule {}
