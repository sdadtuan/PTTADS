import { Controller, Get, UseGuards } from '@nestjs/common';
import {
  StaffSeoSettingsGuard,
  StaffSeoViewGuard,
} from '../seo-admin/guards/staff-seo-view.guard';
import { StaffOrInternalKeyGuard } from '../staff-auth/staff-or-internal-key.guard';
import { SeoGateAService } from './seo-gate-a.service';

@Controller('api/v1/seo/gate-a')
@UseGuards(StaffOrInternalKeyGuard, StaffSeoViewGuard)
export class SeoGateAController {
  constructor(private readonly gateA: SeoGateAService) {}

  @Get('status')
  status() {
    return this.gateA.readiness();
  }

  @Get('readiness')
  @UseGuards(StaffSeoSettingsGuard)
  readiness() {
    return this.gateA.readiness();
  }

  @Get('signoff-template')
  @UseGuards(StaffSeoSettingsGuard)
  signoffTemplate() {
    return { ok: true, template: this.gateA.signoffTemplate() };
  }
}
