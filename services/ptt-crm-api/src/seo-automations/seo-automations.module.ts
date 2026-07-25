import { Module } from '@nestjs/common';
import { ConfigModule } from '../config/config.module';
import { StaffAuthModule } from '../staff-auth/staff-auth.module';
import {
  StaffSeoSettingsGuard,
  StaffSeoViewGuard,
} from '../seo-admin/guards/staff-seo-view.guard';
import { SeoReportsModule } from '../seo-reports/seo-reports.module';
import { SeoAutomationsController } from './seo-automations.controller';
import { SeoAutomationsRepository } from './seo-automations.repository';
import { SeoAutomationsService } from './seo-automations.service';

@Module({
  imports: [ConfigModule, StaffAuthModule, SeoReportsModule],
  controllers: [SeoAutomationsController],
  providers: [
    SeoAutomationsRepository,
    SeoAutomationsService,
    StaffSeoViewGuard,
    StaffSeoSettingsGuard,
  ],
  exports: [SeoAutomationsService],
})
export class SeoAutomationsModule {}
