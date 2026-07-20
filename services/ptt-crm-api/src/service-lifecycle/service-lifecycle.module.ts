import { Module } from '@nestjs/common';
import { StaffAuthModule } from '../staff-auth/staff-auth.module';
import {
  StaffServiceLifecycleViewGuard,
  StaffServiceLifecycleWriteGuard,
} from './guards/staff-service-lifecycle.guard';
import { ServiceLifecycleController } from './service-lifecycle.controller';
import { ServiceLifecycleSqliteRepository } from './service-lifecycle-sqlite.repository';
import { ServiceLifecycleService } from './service-lifecycle.service';

@Module({
  imports: [StaffAuthModule],
  controllers: [ServiceLifecycleController],
  providers: [
    ServiceLifecycleService,
    ServiceLifecycleSqliteRepository,
    StaffServiceLifecycleViewGuard,
    StaffServiceLifecycleWriteGuard,
  ],
  exports: [ServiceLifecycleService],
})
export class ServiceLifecycleModule {}
