import { Module } from '@nestjs/common';
import { ConfigModule } from '../config/config.module';
import { StaffAuthModule } from '../staff-auth/staff-auth.module';
import { WebhooksModule } from '../webhooks/webhooks.module';
import { StaffSeoSettingsGuard, StaffSeoViewGuard } from './guards/staff-seo-view.guard';
import { SeoAdminController } from './seo-admin.controller';
import { SeoAdminRepository } from './seo-admin.repository';
import { SeoAdminService } from './seo-admin.service';

@Module({
  imports: [ConfigModule, StaffAuthModule, WebhooksModule],
  controllers: [SeoAdminController],
  providers: [SeoAdminRepository, SeoAdminService, StaffSeoViewGuard, StaffSeoSettingsGuard],
  exports: [SeoAdminService],
})
export class SeoAdminModule {}
