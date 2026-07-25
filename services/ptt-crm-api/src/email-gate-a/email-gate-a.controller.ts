import { Controller, Get, UseGuards } from '@nestjs/common';
import { StaffEmailSettingsGuard } from '../email-marketing/guards/staff-email-settings.guard';
import { StaffEmailViewGuard } from '../email-marketing/guards/staff-email-view.guard';
import { StaffOrInternalKeyGuard } from '../staff-auth/staff-or-internal-key.guard';
import { EmailGateAService } from './email-gate-a.service';

@Controller('api/v1/email/gate-a')
@UseGuards(StaffOrInternalKeyGuard, StaffEmailViewGuard)
export class EmailGateAController {
  constructor(private readonly gateA: EmailGateAService) {}

  @Get('status')
  status() {
    return this.gateA.readiness();
  }

  @Get('readiness')
  @UseGuards(StaffEmailSettingsGuard)
  readiness() {
    return this.gateA.readiness();
  }

  @Get('signoff-template')
  @UseGuards(StaffEmailSettingsGuard)
  signoffTemplate() {
    return { ok: true, template: this.gateA.signoffTemplate() };
  }
}
