import { Module } from '@nestjs/common';
import { ConfigModule } from '../config/config.module';
import { StaffAuthModule } from '../staff-auth/staff-auth.module';
import { TemporalModule } from '../temporal/temporal.module';
import { WebhooksModule } from '../webhooks/webhooks.module';
import { EmailMarketingCampaignRepository } from './email-marketing-campaign.repository';
import { EmailMarketingExperimentRepository } from './email-marketing-experiment.repository';
import { EmailMarketingEnterpriseRepository } from './email-marketing-enterprise.repository';
import { EmailMarketingController } from './email-marketing.controller';
import { EmailMarketingOpsRepository } from './email-marketing-ops.repository';
import { EmailMarketingRepository } from './email-marketing.repository';
import { EmailMarketingService } from './email-marketing.service';
import { EmailJobQueueService } from './email-job-queue.service';
import { EmailSendOrchestratorService } from './email-send-orchestrator.service';
import { TemporalEmailCampaignService } from './temporal-email-campaign.service';
import { TemporalEmailJourneyService } from './temporal-email-journey.service';
import { EmailPublicController, EmailCaptureController } from './email-public.controller';
import { StaffEmailApproveGuard } from './guards/staff-email-approve.guard';
import { StaffEmailDeliverabilityGuard } from './guards/staff-email-deliverability.guard';
import { StaffEmailReportsGuard } from './guards/staff-email-reports.guard';
import { StaffEmailComplianceGuard } from './guards/staff-email-compliance.guard';
import { StaffEmailSettingsGuard } from './guards/staff-email-settings.guard';
import { StaffEmailViewGuard } from './guards/staff-email-view.guard';
import { StaffEmailWriteGuard } from './guards/staff-email-write.guard';

@Module({
  imports: [ConfigModule, StaffAuthModule, WebhooksModule, TemporalModule],
  controllers: [EmailMarketingController, EmailPublicController, EmailCaptureController],
  providers: [
    EmailMarketingRepository,
    EmailMarketingOpsRepository,
    EmailMarketingCampaignRepository,
    EmailMarketingEnterpriseRepository,
    EmailMarketingExperimentRepository,
    EmailMarketingService,
    EmailJobQueueService,
    EmailSendOrchestratorService,
    TemporalEmailCampaignService,
    TemporalEmailJourneyService,
    StaffEmailViewGuard,
    StaffEmailSettingsGuard,
    StaffEmailWriteGuard,
    StaffEmailComplianceGuard,
    StaffEmailApproveGuard,
    StaffEmailDeliverabilityGuard,
    StaffEmailReportsGuard,
  ],
  exports: [EmailMarketingService, EmailSendOrchestratorService],
})
export class EmailMarketingModule {}
