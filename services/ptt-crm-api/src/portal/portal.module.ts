import { Module } from '@nestjs/common';
import { PortalAuthController } from './portal-auth.controller';
import { PortalAuthService } from './portal-auth.service';
import { PortalJwtGuard } from './portal-jwt.guard';

@Module({
  controllers: [PortalAuthController],
  providers: [PortalAuthService, PortalJwtGuard],
  exports: [PortalAuthService, PortalJwtGuard],
})
export class PortalModule {}
