import { Module } from '@nestjs/common';
import { ConfigModule } from '../config/config.module';
import { StaffEmailSettingsGuard } from '../email-marketing/guards/staff-email-settings.guard';
import { StaffEmailViewGuard } from '../email-marketing/guards/staff-email-view.guard';
import { StaffAuthModule } from '../staff-auth/staff-auth.module';
import { EmailGateAController } from './email-gate-a.controller';
import { EmailGateAService } from './email-gate-a.service';

@Module({
  imports: [ConfigModule, StaffAuthModule],
  controllers: [EmailGateAController],
  providers: [EmailGateAService, StaffEmailViewGuard, StaffEmailSettingsGuard],
  exports: [EmailGateAService],
})
export class EmailGateAModule {}
