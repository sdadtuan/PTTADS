import { Module } from '@nestjs/common';
import { ConfigModule } from '../config/config.module';
import { StaffAuthModule } from '../staff-auth/staff-auth.module';
import { StaffSeoViewGuard, StaffSeoWriteGuard } from '../seo-admin/guards/staff-seo-view.guard';
import { WebhooksModule } from '../webhooks/webhooks.module';
import { SeoAeoController } from './seo-aeo.controller';
import { SeoAeoRepository } from './seo-aeo.repository';
import { SeoAeoService } from './seo-aeo.service';

@Module({
  imports: [ConfigModule, StaffAuthModule, WebhooksModule],
  controllers: [SeoAeoController],
  providers: [SeoAeoRepository, SeoAeoService, StaffSeoViewGuard, StaffSeoWriteGuard],
  exports: [SeoAeoService, SeoAeoRepository],
})
export class SeoAeoModule {}
