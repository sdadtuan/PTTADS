import { Module } from '@nestjs/common';
import { StaffAuthModule } from '../staff-auth/staff-auth.module';
import {
  StaffFinanceConfigureGuard,
  StaffFinanceExportGuard,
  StaffFinanceViewGuard,
} from './guards/staff-finance.guard';
import { FinanceController } from './finance.controller';
import { FinanceSqliteRepository } from './finance-sqlite.repository';
import { FinanceService } from './finance.service';

@Module({
  imports: [StaffAuthModule],
  controllers: [FinanceController],
  providers: [
    FinanceService,
    FinanceSqliteRepository,
    StaffFinanceViewGuard,
    StaffFinanceExportGuard,
    StaffFinanceConfigureGuard,
  ],
})
export class FinanceModule {}
