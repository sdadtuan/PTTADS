import { Module } from '@nestjs/common';
import { ConfigModule } from '../config/config.module';
import { StaffAuthModule } from '../staff-auth/staff-auth.module';
import { StaffSeoSettingsGuard, StaffSeoViewGuard } from '../seo-admin/guards/staff-seo-view.guard';
import { SeoGateAController } from './seo-gate-a.controller';
import { SeoGateAService } from './seo-gate-a.service';

@Module({
  imports: [ConfigModule, StaffAuthModule],
  controllers: [SeoGateAController],
  providers: [SeoGateAService, StaffSeoViewGuard, StaffSeoSettingsGuard],
  exports: [SeoGateAService],
})
export class SeoGateAModule {}
