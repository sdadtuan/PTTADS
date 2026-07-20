import { Module } from '@nestjs/common';
import { StaffAuthModule } from '../staff-auth/staff-auth.module';
import {
  StaffReProjectsBudgetDeleteGuard,
  StaffReProjectsBudgetExportGuard,
  StaffReProjectsBudgetViewGuard,
  StaffReProjectsBudgetWriteGuard,
  StaffReProjectsDeleteGuard,
  StaffReProjectsExportGuard,
  StaffReProjectsKpiDeleteGuard,
  StaffReProjectsKpiViewGuard,
  StaffReProjectsKpiWriteGuard,
  StaffReProjectsProductsDeleteGuard,
  StaffReProjectsProductsViewGuard,
  StaffReProjectsProductsWriteGuard,
  StaffReProjectsRisksDeleteGuard,
  StaffReProjectsRisksViewGuard,
  StaffReProjectsRisksWriteGuard,
  StaffReProjectsUpdateGuard,
  StaffReProjectsViewGuard,
  StaffReProjectsWriteGuard,
} from './guards/staff-re-projects.guard';
import { ReProjectsAccountingRepository } from './re-projects-accounting.repository';
import { ReProjectsAccountingService } from './re-projects-accounting.service';
import { ReProjectsController } from './re-projects.controller';
import { ReProjectsKpiBudgetService } from './re-projects-kpi-budget.service';
import { ReProjectsOpsService } from './re-projects-ops.service';
import { ReProjectsSqliteRepository } from './re-projects-sqlite.repository';
import { ReProjectsService } from './re-projects.service';

@Module({
  imports: [StaffAuthModule],
  controllers: [ReProjectsController],
  providers: [
    ReProjectsService,
    ReProjectsOpsService,
    ReProjectsKpiBudgetService,
    ReProjectsAccountingService,
    ReProjectsSqliteRepository,
    ReProjectsAccountingRepository,
    StaffReProjectsViewGuard,
    StaffReProjectsWriteGuard,
    StaffReProjectsDeleteGuard,
    StaffReProjectsExportGuard,
    StaffReProjectsUpdateGuard,
    StaffReProjectsProductsViewGuard,
    StaffReProjectsProductsWriteGuard,
    StaffReProjectsProductsDeleteGuard,
    StaffReProjectsKpiViewGuard,
    StaffReProjectsKpiWriteGuard,
    StaffReProjectsKpiDeleteGuard,
    StaffReProjectsRisksViewGuard,
    StaffReProjectsRisksWriteGuard,
    StaffReProjectsRisksDeleteGuard,
    StaffReProjectsBudgetViewGuard,
    StaffReProjectsBudgetWriteGuard,
    StaffReProjectsBudgetDeleteGuard,
    StaffReProjectsBudgetExportGuard,
  ],
  exports: [ReProjectsService, ReProjectsOpsService, ReProjectsKpiBudgetService, ReProjectsAccountingService],
})
export class ReProjectsModule {}
