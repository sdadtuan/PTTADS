import { Module } from '@nestjs/common';
import { StaffAuthModule } from '../staff-auth/staff-auth.module';
import {
  StaffPayrollSalaryEditGuard,
  StaffPayrollSalaryExportGuard,
  StaffPayrollSalaryViewGuard,
  StaffPayrollViewGuard,
} from './guards/staff-payroll.guard';
import { PayrollController } from './payroll.controller';
import { PayrollSqliteRepository } from './payroll-sqlite.repository';
import { PayrollService } from './payroll.service';

@Module({
  imports: [StaffAuthModule],
  controllers: [PayrollController],
  providers: [
    PayrollService,
    PayrollSqliteRepository,
    StaffPayrollViewGuard,
    StaffPayrollSalaryViewGuard,
    StaffPayrollSalaryEditGuard,
    StaffPayrollSalaryExportGuard,
  ],
})
export class PayrollModule {}
