import { Module } from '@nestjs/common';
import { ConfigModule } from '../config/config.module';
import { StaffAuthModule } from '../staff-auth/staff-auth.module';
import {
  StaffSeoReportsGuard,
  StaffSeoSettingsGuard,
  StaffSeoViewGuard,
} from '../seo-admin/guards/staff-seo-view.guard';
import { SeoReportsController } from './seo-reports.controller';
import { SeoReportsRepository } from './seo-reports.repository';
import { SeoReportsService } from './seo-reports.service';

@Module({
  imports: [ConfigModule, StaffAuthModule],
  controllers: [SeoReportsController],
  providers: [
    SeoReportsRepository,
    SeoReportsService,
    StaffSeoViewGuard,
    StaffSeoReportsGuard,
    StaffSeoSettingsGuard,
  ],
  exports: [SeoReportsService, SeoReportsRepository],
})
export class SeoReportsModule {}
