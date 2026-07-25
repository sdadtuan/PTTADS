import { Module } from '@nestjs/common';
import { ConfigModule } from '../config/config.module';
import { StaffAuthModule } from '../staff-auth/staff-auth.module';
import {
  StaffSeoTechnicalGuard,
  StaffSeoViewGuard,
} from '../seo-admin/guards/staff-seo-view.guard';
import { SeoTechnicalController } from './seo-technical.controller';
import { SeoTechnicalRepository } from './seo-technical.repository';
import { SeoTechnicalService } from './seo-technical.service';

@Module({
  imports: [ConfigModule, StaffAuthModule],
  controllers: [SeoTechnicalController],
  providers: [SeoTechnicalRepository, SeoTechnicalService, StaffSeoViewGuard, StaffSeoTechnicalGuard],
  exports: [SeoTechnicalService, SeoTechnicalRepository],
})
export class SeoTechnicalModule {}
