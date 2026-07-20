import { Module } from '@nestjs/common';
import { StaffAuthController } from './staff-auth.controller';
import { StaffAuthService } from './staff-auth.service';
import { StaffJwtGuard } from './staff-jwt.guard';
import { StaffOrInternalKeyGuard } from './staff-or-internal-key.guard';

@Module({
  controllers: [StaffAuthController],
  providers: [StaffAuthService, StaffJwtGuard, StaffOrInternalKeyGuard],
  exports: [StaffAuthService, StaffJwtGuard, StaffOrInternalKeyGuard],
})
export class StaffAuthModule {}
