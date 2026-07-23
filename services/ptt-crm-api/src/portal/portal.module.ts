import { Module } from '@nestjs/common';
import { PortalAuthController } from './portal-auth.controller';
import { PortalAuthService } from './portal-auth.service';
import { PortalCreativeNotifyService } from './portal-creative-notify.service';
import { PortalJwtGuard } from './portal-jwt.guard';
import { PortalSettingsController } from './portal-settings.controller';
import { PortalSettingsRepository } from './portal-settings.repository';
import { PortalSettingsService } from './portal-settings.service';

@Module({
  controllers: [PortalAuthController, PortalSettingsController],
  providers: [
    PortalAuthService,
    PortalJwtGuard,
    PortalSettingsRepository,
    PortalSettingsService,
    PortalCreativeNotifyService,
  ],
  exports: [
    PortalAuthService,
    PortalJwtGuard,
    PortalSettingsService,
    PortalCreativeNotifyService,
  ],
})
export class PortalModule {}
