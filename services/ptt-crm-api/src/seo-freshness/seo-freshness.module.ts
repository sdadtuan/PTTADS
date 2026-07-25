import { Module } from '@nestjs/common';
import { ConfigModule } from '../config/config.module';
import { StaffAuthModule } from '../staff-auth/staff-auth.module';
import { StaffSeoViewGuard, StaffSeoWriteGuard } from '../seo-admin/guards/staff-seo-view.guard';
import { SeoFreshnessController } from './seo-freshness.controller';
import { SeoFreshnessRepository } from './seo-freshness.repository';
import { SeoFreshnessService } from './seo-freshness.service';

@Module({
  imports: [ConfigModule, StaffAuthModule],
  controllers: [SeoFreshnessController],
  providers: [SeoFreshnessRepository, SeoFreshnessService, StaffSeoViewGuard, StaffSeoWriteGuard],
  exports: [SeoFreshnessService],
})
export class SeoFreshnessModule {}
