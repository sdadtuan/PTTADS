import { Module } from '@nestjs/common';
import { StaffAuthModule } from '../staff-auth/staff-auth.module';
import { LaunchQaPgRepository } from '../service-lifecycle/launch-qa-pg.repository';
import {
  StaffServiceLifecycleViewGuard,
} from '../service-lifecycle/guards/staff-service-lifecycle.guard';
import { ServiceLifecycleSqliteRepository } from '../service-lifecycle/service-lifecycle-sqlite.repository';
import { LaunchQaController } from './launch-qa.controller';
import { LaunchQaHubService } from './launch-qa-hub.service';
import { LaunchQaLifecycleLookupService } from './launch-qa-lifecycle-lookup.service';

@Module({
  imports: [StaffAuthModule],
  controllers: [LaunchQaController],
  providers: [
    LaunchQaHubService,
    LaunchQaLifecycleLookupService,
    LaunchQaPgRepository,
    ServiceLifecycleSqliteRepository,
    StaffServiceLifecycleViewGuard,
  ],
})
export class LaunchQaModule {}
