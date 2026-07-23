import { forwardRef, Module } from '@nestjs/common';
import { StaffAuthModule } from '../staff-auth/staff-auth.module';
import { LeadsModule } from '../leads/leads.module';
import { LeadsFunnelController } from './leads-funnel.controller';
import { LeadsFunnelService } from './leads-funnel.service';
import { LeadsFunnelSqliteRepository } from './leads-funnel-sqlite.repository';
import { LeadsFunnelEnabledGuard, PresalesOnLeadGuard } from './guards/leads-funnel-enabled.guard';
import { LeadNotInReviewQueueGuard } from './guards/lead-not-in-review-queue.guard';
import { StaffLeadsGdkdGuard } from './guards/staff-leads-gdkd.guard';

@Module({
  imports: [StaffAuthModule, forwardRef(() => LeadsModule)],
  controllers: [LeadsFunnelController],
  providers: [
    LeadsFunnelService,
    LeadsFunnelSqliteRepository,
    LeadsFunnelEnabledGuard,
    PresalesOnLeadGuard,
    StaffLeadsGdkdGuard,
    LeadNotInReviewQueueGuard,
  ],
  exports: [LeadsFunnelService, LeadsFunnelSqliteRepository, LeadNotInReviewQueueGuard],
})
export class LeadsFunnelModule {}
