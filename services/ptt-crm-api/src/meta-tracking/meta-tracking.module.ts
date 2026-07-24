import { Module } from '@nestjs/common';
import { StaffAuthModule } from '../staff-auth/staff-auth.module';
import { WebhooksModule } from '../webhooks/webhooks.module';
import { MetaCapiEventsController } from './meta-capi-events.controller';
import { MetaConversionRulesController } from './meta-conversion-rules.controller';
import { MetaConversionRulesService } from './meta-conversion-rules.service';
import { MetaPixelTestController } from './meta-pixel-test.controller';
import { MetaPixelTestService } from './meta-pixel-test.service';
import { MetaTrackingController } from './meta-tracking.controller';
import { MetaTrackingRepository } from './meta-tracking.repository';
import {
  MetaCapiEventsService,
  MetaTrackingService,
} from './meta-tracking.service';
import {
  StaffMetaTrackingConfigureGuard,
  StaffMetaTrackingEnabledGuard,
  StaffMetaTrackingViewGuard,
} from './guards/staff-meta-tracking.guard';

@Module({
  imports: [StaffAuthModule, WebhooksModule],
  controllers: [
    MetaTrackingController,
    MetaCapiEventsController,
    MetaConversionRulesController,
    MetaPixelTestController,
  ],
  providers: [
    MetaTrackingRepository,
    MetaTrackingService,
    MetaCapiEventsService,
    MetaConversionRulesService,
    MetaPixelTestService,
    StaffMetaTrackingViewGuard,
    StaffMetaTrackingConfigureGuard,
    StaffMetaTrackingEnabledGuard,
  ],
  exports: [
    MetaTrackingService,
    MetaCapiEventsService,
    MetaConversionRulesService,
    MetaPixelTestService,
  ],
})
export class MetaTrackingModule {}
