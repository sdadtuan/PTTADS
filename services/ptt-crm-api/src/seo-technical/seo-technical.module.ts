import { Module } from '@nestjs/common';
import { ConfigModule } from '../config/config.module';
import { StaffAuthModule } from '../staff-auth/staff-auth.module';
import {
  StaffSeoTechnicalGuard,
  StaffSeoViewGuard,
} from '../seo-admin/guards/staff-seo-view.guard';
import { SeoTechnicalController } from './seo-technical.controller';
import { SeoCrawlInternalController, SeoCrawlSecretGuard } from './seo-crawl-internal.controller';
import { SeoTechnicalRepository } from './seo-technical.repository';
import { SeoTechnicalService } from './seo-technical.service';

@Module({
  imports: [ConfigModule, StaffAuthModule],
  controllers: [SeoTechnicalController, SeoCrawlInternalController],
  providers: [SeoTechnicalRepository, SeoTechnicalService, StaffSeoViewGuard, StaffSeoTechnicalGuard, SeoCrawlSecretGuard],
  exports: [SeoTechnicalService, SeoTechnicalRepository],
})
export class SeoTechnicalModule {}
