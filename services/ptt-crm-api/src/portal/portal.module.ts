import { Module } from '@nestjs/common';
import { AgencyModule } from '../agency/agency.module';
import { PortalAuthController } from './portal-auth.controller';
import { PortalAuthService } from './portal-auth.service';
import { CampaignMilestoneNotifyService } from '../agency/campaign-milestone-notify.service';
import { PortalCreativeNotifyService } from './portal-creative-notify.service';
import { PortalNotificationController } from './portal-notification.controller';
import { PortalNotificationRepository } from './portal-notification.repository';
import { PortalNotificationService } from './portal-notification.service';
import { PortalNotifyWebhookService } from './portal-notify-webhook.service';
import { PortalPasswordResetNotifyService } from './portal-password-reset-notify.service';
import { PortalPasswordResetRepository } from './portal-password-reset.repository';
import { PortalPasswordResetService } from './portal-password-reset.service';
import { PortalJwtGuard } from './portal-jwt.guard';
import { PortalSettingsController } from './portal-settings.controller';
import { PortalSettingsRepository } from './portal-settings.repository';
import { PortalSettingsService } from './portal-settings.service';

@Module({
  imports: [AgencyModule],
  controllers: [PortalAuthController, PortalSettingsController, PortalNotificationController],
  providers: [
    PortalAuthService,
    PortalJwtGuard,
    PortalSettingsRepository,
    PortalSettingsService,
    PortalNotifyWebhookService,
    PortalNotificationRepository,
    PortalNotificationService,
    PortalCreativeNotifyService,
    CampaignMilestoneNotifyService,
    PortalPasswordResetRepository,
    PortalPasswordResetNotifyService,
    PortalPasswordResetService,
  ],
  exports: [
    PortalAuthService,
    PortalJwtGuard,
    PortalSettingsService,
    PortalCreativeNotifyService,
    PortalNotificationService,
    PortalNotifyWebhookService,
    CampaignMilestoneNotifyService,
    PortalPasswordResetService,
  ],
})
export class PortalModule {}
