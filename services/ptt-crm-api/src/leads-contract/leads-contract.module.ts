import { Module, forwardRef } from '@nestjs/common';
import { StaffAuthModule } from '../staff-auth/staff-auth.module';
import { LeadsModule } from '../leads/leads.module';
import { LeadsFunnelModule } from '../leads-funnel/leads-funnel.module';
import { SopModule } from '../sop/sop.module';
import {
  AgencyContractsController,
  ContractsApprovalController,
  LeadsContractController,
} from './leads-contract.controller';
import { LeadsContractService } from './leads-contract.service';
import { LeadsContractSqliteRepository } from './leads-contract-sqlite.repository';
import { ServiceDeliveryNestGuard } from './guards/service-delivery-nest.guard';

@Module({
  imports: [StaffAuthModule, SopModule, forwardRef(() => LeadsModule), forwardRef(() => LeadsFunnelModule)],
  controllers: [LeadsContractController, ContractsApprovalController, AgencyContractsController],
  providers: [LeadsContractService, LeadsContractSqliteRepository, ServiceDeliveryNestGuard],
  exports: [LeadsContractService, LeadsContractSqliteRepository],
})
export class LeadsContractModule {}
