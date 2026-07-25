import { Module } from '@nestjs/common';
import { EventsModule } from '../events/events.module';
import { LeadsContractModule } from '../leads-contract/leads-contract.module';
import { PerformanceModule } from '../performance/performance.module';
import { StaffAuthModule } from '../staff-auth/staff-auth.module';
import { WebhooksModule } from '../webhooks/webhooks.module';
import { WorkflowsModule } from '../workflows/workflows.module';
import { AgencyOpsController } from './agency-ops.controller';
import { AgencySideEffectsService } from './agency-side-effects.service';
import { AgencyRepository } from './agency.repository';
import { AgencyService } from './agency.service';
import { ClientOffboardRepository } from './client-offboard.repository';
import { ClientOffboardFollowUpService } from './client-offboard-follow-up.service';
import { ClientOffboardService } from './client-offboard.service';
import { PortalClientUsersRepository } from './portal-client-users.repository';
import { PortalClientUsersService } from './portal-client-users.service';
import { OnboardingOrchestratorRepository } from './onboarding-orchestrator.repository';
import { OnboardingOrchestratorService } from './onboarding-orchestrator.service';
import { ClientsController } from './clients.controller';
import {
  StaffAgencyViewGuard,
  StaffFacebookAdsViewGuard,
} from './guards/staff-agency-view.guard';
import { StaffAgencyConfigureGuard } from './guards/staff-agency-configure.guard';
import { StaffAgencyWriteGuard } from './guards/staff-agency-write.guard';

@Module({
  imports: [StaffAuthModule, PerformanceModule, EventsModule, WebhooksModule, WorkflowsModule, LeadsContractModule],
  controllers: [ClientsController, AgencyOpsController],
  providers: [
    AgencyService,
    AgencyRepository,
    AgencySideEffectsService,
    ClientOffboardRepository,
    ClientOffboardFollowUpService,
    ClientOffboardService,
    PortalClientUsersRepository,
    PortalClientUsersService,
    OnboardingOrchestratorRepository,
    OnboardingOrchestratorService,
    StaffAgencyViewGuard,
    StaffFacebookAdsViewGuard,
    StaffAgencyWriteGuard,
    StaffAgencyConfigureGuard,
  ],
  exports: [AgencyService, ClientOffboardService, OnboardingOrchestratorService],
})
export class AgencyModule {}
