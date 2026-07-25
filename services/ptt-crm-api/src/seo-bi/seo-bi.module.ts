import { Module } from '@nestjs/common';
import { ConfigModule } from '../config/config.module';
import { StaffAuthModule } from '../staff-auth/staff-auth.module';
import { StaffSeoSettingsGuard, StaffSeoViewGuard } from '../seo-admin/guards/staff-seo-view.guard';
import { WebhooksModule } from '../webhooks/webhooks.module';
import { SeoBiController } from './seo-bi.controller';
import { SeoBiRepository } from './seo-bi.repository';
import { SeoBiService } from './seo-bi.service';

@Module({
  imports: [ConfigModule, StaffAuthModule, WebhooksModule],
  controllers: [SeoBiController],
  providers: [SeoBiRepository, SeoBiService, StaffSeoViewGuard, StaffSeoSettingsGuard],
  exports: [SeoBiService, SeoBiRepository],
})
export class SeoBiModule {}
