import { Module } from '@nestjs/common';
import { StaffAuthModule } from '../staff-auth/staff-auth.module';
import {
  StaffSvcFinanceViewGuard,
  StaffSvcFinanceWriteGuard,
} from './guards/staff-svc-finance.guard';
import { SvcFinanceController } from './svc-finance.controller';
import { SvcFinanceSqliteRepository } from './svc-finance-sqlite.repository';
import { SvcFinanceService } from './svc-finance.service';

@Module({
  imports: [StaffAuthModule],
  controllers: [SvcFinanceController],
  providers: [
    SvcFinanceService,
    SvcFinanceSqliteRepository,
    StaffSvcFinanceViewGuard,
    StaffSvcFinanceWriteGuard,
  ],
  exports: [SvcFinanceService],
})
export class SvcFinanceModule {}
