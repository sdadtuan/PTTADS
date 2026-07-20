import { Module } from '@nestjs/common';
import { StaffAuthModule } from '../staff-auth/staff-auth.module';
import {
  StaffOwnerWeeklyConfigureGuard,
  StaffOwnerWeeklyExportGuard,
  StaffOwnerWeeklyViewGuard,
} from './guards/staff-owner-weekly.guard';
import { OwnerWeeklyController } from './owner-weekly.controller';
import { OwnerWeeklySqliteRepository } from './owner-weekly-sqlite.repository';
import { OwnerWeeklyService } from './owner-weekly.service';

@Module({
  imports: [StaffAuthModule],
  controllers: [OwnerWeeklyController],
  providers: [
    OwnerWeeklyService,
    OwnerWeeklySqliteRepository,
    StaffOwnerWeeklyViewGuard,
    StaffOwnerWeeklyExportGuard,
    StaffOwnerWeeklyConfigureGuard,
  ],
})
export class OwnerWeeklyModule {}
