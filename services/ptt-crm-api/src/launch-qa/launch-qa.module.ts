import { Module } from '@nestjs/common';
import { InternalKeyGuard } from '../auth/internal-key.guard';
import { CampaignWritesRepository } from '../campaign-writes/campaign-writes.repository';
import { CreativesRepository } from '../creatives/creatives.repository';
import { MetaTrackingModule } from '../meta-tracking/meta-tracking.module';
import { StaffAuthModule } from '../staff-auth/staff-auth.module';
import { LaunchQaPgRepository } from '../service-lifecycle/launch-qa-pg.repository';
import {
  StaffServiceLifecycleViewGuard,
} from '../service-lifecycle/guards/staff-service-lifecycle.guard';
import { ServiceLifecycleSqliteRepository } from '../service-lifecycle/service-lifecycle-sqlite.repository';
import { LaunchQaController } from './launch-qa.controller';
import { LaunchQaCampaignWriteBridgeService } from './launch-qa-campaign-write-bridge.service';
import { LaunchQaCreativeBridgeService } from './launch-qa-creative-bridge.service';
import { LaunchQaHubService } from './launch-qa-hub.service';
import { LaunchQaInternalController } from './launch-qa-internal.controller';
import { LaunchQaLifecycleLookupService } from './launch-qa-lifecycle-lookup.service';
import { LaunchQaMetaBridgeService } from './launch-qa-meta-bridge.service';

@Module({
  imports: [StaffAuthModule, MetaTrackingModule],
  controllers: [LaunchQaController, LaunchQaInternalController],
  providers: [
    LaunchQaHubService,
    LaunchQaLifecycleLookupService,
    LaunchQaCreativeBridgeService,
    LaunchQaCampaignWriteBridgeService,
    LaunchQaMetaBridgeService,
    LaunchQaPgRepository,
    CreativesRepository,
    CampaignWritesRepository,
    ServiceLifecycleSqliteRepository,
    StaffServiceLifecycleViewGuard,
    InternalKeyGuard,
  ],
  exports: [
    LaunchQaPgRepository,
    LaunchQaCreativeBridgeService,
    LaunchQaCampaignWriteBridgeService,
    LaunchQaMetaBridgeService,
    LaunchQaLifecycleLookupService,
  ],
})
export class LaunchQaModule {}
