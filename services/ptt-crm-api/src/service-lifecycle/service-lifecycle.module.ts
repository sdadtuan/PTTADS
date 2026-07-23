import { Module } from '@nestjs/common';
import { CreativesModule } from '../creatives/creatives.module';
import { IntakeModule } from '../intake/intake.module';
import { SopModule } from '../sop/sop.module';
import { StaffAuthModule } from '../staff-auth/staff-auth.module';
import { SvcFinanceModule } from '../svc-finance/svc-finance.module';
import { TemporalModule } from '../temporal/temporal.module';
import { WorkflowsModule } from '../workflows/workflows.module';
import {
  StaffServiceLifecycleViewGuard,
  StaffServiceLifecycleWriteGuard,
} from './guards/staff-service-lifecycle.guard';
import { LaunchQaAutoStartService } from './launch-qa-auto-start.service';
import { LaunchQaPgRepository } from './launch-qa-pg.repository';
import { LifecycleConsultService } from './lifecycle-consult.service';
import { LifecycleLaunchQaService } from './lifecycle-launch-qa.service';
import { LifecycleTasksRepository } from './lifecycle-tasks.repository';
import { ServiceLifecycleController } from './service-lifecycle.controller';
import { ServiceLifecycleSqliteRepository } from './service-lifecycle-sqlite.repository';
import { ServiceLifecycleService } from './service-lifecycle.service';

@Module({
  imports: [
    StaffAuthModule,
    SvcFinanceModule,
    IntakeModule,
    SopModule,
    CreativesModule,
    TemporalModule,
    WorkflowsModule,
  ],
  controllers: [ServiceLifecycleController],
  providers: [
    ServiceLifecycleService,
    ServiceLifecycleSqliteRepository,
    LifecycleTasksRepository,
    LifecycleConsultService,
    LifecycleLaunchQaService,
    LaunchQaPgRepository,
    LaunchQaAutoStartService,
    StaffServiceLifecycleViewGuard,
    StaffServiceLifecycleWriteGuard,
  ],
  exports: [ServiceLifecycleService, LifecycleTasksRepository],
})
export class ServiceLifecycleModule {}
