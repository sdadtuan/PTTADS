import { Module } from '@nestjs/common';
import { ConfigModule } from '../config/config.module';
import { StaffAuthModule } from '../staff-auth/staff-auth.module';
import {
  StaffSeoSettingsGuard,
  StaffSeoViewGuard,
  StaffSeoWriteGuard,
} from '../seo-admin/guards/staff-seo-view.guard';
import { SeoStrategyController } from './seo-strategy.controller';
import { SeoStrategyRepository } from './seo-strategy.repository';
import { SeoStrategyService } from './seo-strategy.service';

@Module({
  imports: [ConfigModule, StaffAuthModule],
  controllers: [SeoStrategyController],
  providers: [
    SeoStrategyRepository,
    SeoStrategyService,
    StaffSeoViewGuard,
    StaffSeoWriteGuard,
    StaffSeoSettingsGuard,
  ],
  exports: [SeoStrategyService],
})
export class SeoStrategyModule {}
