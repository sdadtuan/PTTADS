import { Module } from '@nestjs/common';
import { ConfigModule } from '../config/config.module';
import { StaffAuthModule } from '../staff-auth/staff-auth.module';
import {
  StaffSeoSettingsGuard,
  StaffSeoTechnicalGuard,
  StaffSeoViewGuard,
} from '../seo-admin/guards/staff-seo-view.guard';
import { SeoCmsController } from './seo-cms.controller';
import { SeoCmsInternalController, SeoCmsPilotSecretGuard } from './seo-cms-internal.controller';
import { SeoCmsRepository } from './seo-cms.repository';
import { SeoCmsService } from './seo-cms.service';

@Module({
  imports: [ConfigModule, StaffAuthModule],
  controllers: [SeoCmsController, SeoCmsInternalController],
  providers: [
    SeoCmsRepository,
    SeoCmsService,
    SeoCmsPilotSecretGuard,
    StaffSeoViewGuard,
    StaffSeoSettingsGuard,
    StaffSeoTechnicalGuard,
  ],
  exports: [SeoCmsService, SeoCmsRepository],
})
export class SeoCmsModule {}
