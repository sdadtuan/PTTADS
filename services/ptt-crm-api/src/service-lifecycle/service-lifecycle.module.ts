import { Module } from '@nestjs/common';
import { IntakeModule } from '../intake/intake.module';
import { StaffAuthModule } from '../staff-auth/staff-auth.module';
import { SvcFinanceModule } from '../svc-finance/svc-finance.module';
import {
  StaffServiceLifecycleViewGuard,
  StaffServiceLifecycleWriteGuard,
} from './guards/staff-service-lifecycle.guard';
import { LifecycleConsultService } from './lifecycle-consult.service';
import { LifecycleTasksRepository } from './lifecycle-tasks.repository';
import { ServiceLifecycleController } from './service-lifecycle.controller';
import { ServiceLifecycleSqliteRepository } from './service-lifecycle-sqlite.repository';
import { ServiceLifecycleService } from './service-lifecycle.service';

@Module({
  imports: [StaffAuthModule, SvcFinanceModule, IntakeModule],
  controllers: [ServiceLifecycleController],
  providers: [
    ServiceLifecycleService,
    ServiceLifecycleSqliteRepository,
    LifecycleTasksRepository,
    LifecycleConsultService,
    StaffServiceLifecycleViewGuard,
    StaffServiceLifecycleWriteGuard,
  ],
  exports: [ServiceLifecycleService, LifecycleTasksRepository],
})
export class ServiceLifecycleModule {}
