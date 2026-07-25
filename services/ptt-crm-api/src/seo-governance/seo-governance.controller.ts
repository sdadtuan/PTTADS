import {
  Body,
  Controller,
  Get,
  Param,
  ParseIntPipe,
  Post,
  Put,
  Query,
  Req,
  UseGuards,
} from '@nestjs/common';
import { Request } from 'express';
import {
  StaffSeoApproveGuard,
  StaffSeoSettingsGuard,
  StaffSeoViewGuard,
} from '../seo-admin/guards/staff-seo-view.guard';
import { StaffOrInternalKeyGuard } from '../staff-auth/staff-or-internal-key.guard';
import { StaffJwtPayload } from '../staff-auth/staff-jwt.util';
import { SeoGovernanceService } from './seo-governance.service';

type StaffReq = Request & { staffUser?: StaffJwtPayload; staffAuthVia?: 'internal' | 'jwt' };

function actorId(req: StaffReq): string {
  if (req.staffAuthVia === 'internal') return 'internal';
  return String(req.staffUser?.sub ?? req.staffUser?.email ?? 'staff');
}

@Controller('api/v1/seo')
@UseGuards(StaffOrInternalKeyGuard, StaffSeoViewGuard)
export class SeoGovernanceController {
  constructor(private readonly governance: SeoGovernanceService) {}

  @Get('governance/status')
  status() {
    return { ok: true, enabled: this.governance.isEnabled() };
  }

  @Get('clients/:id/governance/policies')
  policies(@Param('id', ParseIntPipe) id: number) {
    return this.governance.listPolicies(id).then((policies) => ({ ok: true, policies }));
  }

  @Get('governance/policies')
  globalPolicies() {
    return this.governance.listPolicies(null).then((policies) => ({ ok: true, policies }));
  }

  @Put('governance/policies')
  @UseGuards(StaffSeoSettingsGuard)
  upsertPolicy(@Body() body: Record<string, unknown>) {
    return this.governance.upsertPolicy(body).then((policy) => ({ ok: true, policy }));
  }

  @Get('governance/compliance')
  compliance(@Query('customer_id') customerId?: string, @Query('days') days?: string) {
    const cid = customerId ? Number.parseInt(customerId, 10) : null;
    const d = days ? Number.parseInt(days, 10) : 7;
    return this.governance.complianceSummary(cid, d).then((summary) => ({ ok: true, summary }));
  }

  @Post('content/:id/governance/evaluate')
  evaluate(@Param('id', ParseIntPipe) id: number, @Body() body: { action?: string }) {
    return this.governance.evaluateContent(id, body.action).then((result) => ({ ...result }));
  }

  @Post('governance/overrides')
  @UseGuards(StaffSeoApproveGuard)
  override(@Req() req: StaffReq, @Body() body: { evaluation_id: number; policy_key: string; reason?: string }) {
    return this.governance.recordOverride({
      evaluationId: Number(body.evaluation_id),
      policyKey: body.policy_key,
      actorId: actorId(req),
      reason: body.reason ?? '',
    });
  }
}
