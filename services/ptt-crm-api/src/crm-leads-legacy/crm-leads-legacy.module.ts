import { Module } from '@nestjs/common';
import { LeadsModule } from '../leads/leads.module';
import { StaffAuthModule } from '../staff-auth/staff-auth.module';
import { CrmLeadsLegacyController } from './crm-leads-legacy.controller';
import { CrmLeadsLegacyService } from './crm-leads-legacy.service';
import { CrmLeadsSqliteRepository } from './crm-leads-sqlite.repository';

@Module({
  imports: [StaffAuthModule, LeadsModule],
  controllers: [CrmLeadsLegacyController],
  providers: [CrmLeadsLegacyService, CrmLeadsSqliteRepository],
  exports: [CrmLeadsLegacyService],
})
export class CrmLeadsLegacyModule {}
