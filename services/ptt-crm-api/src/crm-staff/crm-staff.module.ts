import { Module } from '@nestjs/common';
import { KpiModule } from '../kpi/kpi.module';
import { StaffAuthModule } from '../staff-auth/staff-auth.module';
import { CrmStaffController } from './crm-staff.controller';
import { CrmStaffSqliteRepository } from './crm-staff-sqlite.repository';
import { CrmStaffService } from './crm-staff.service';
import {
  StaffRosterViewGuard,
  StaffRosterWriteGuard,
} from './guards/staff-roster.guard';
import { StaffKpiViewGuard } from '../kpi/guards/staff-kpi.guard';

@Module({
  imports: [StaffAuthModule, KpiModule],
  controllers: [CrmStaffController],
  providers: [
    CrmStaffService,
    CrmStaffSqliteRepository,
    StaffRosterViewGuard,
    StaffRosterWriteGuard,
    StaffKpiViewGuard,
  ],
  exports: [CrmStaffService],
})
export class CrmStaffModule {}
