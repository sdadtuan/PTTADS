import {
  Body,
  Controller,
  Get,
  HttpCode,
  HttpStatus,
  NotFoundException,
  Param,
  ParseIntPipe,
  Patch,
  Post,
  Query,
  Req,
  UseGuards,
} from '@nestjs/common';
import { Request } from 'express';
import { StaffOrInternalKeyGuard } from '../staff-auth/staff-or-internal-key.guard';
import { StaffJwtPayload } from '../staff-auth/staff-jwt.util';
import { StaffLeadsWriteGuard } from '../leads/guards/staff-leads-write.guard';
import { LeadNotInReviewQueueGuard } from '../leads-funnel/guards/lead-not-in-review-queue.guard';
import { StaffLeadsViewGuard } from '../leads/guards/staff-leads-view.guard';
import { LeadsRepository } from '../leads/leads.repository';
import { LeadsWriteService } from '../leads/leads-write.service';
import { PatchLeadV1Body } from '../leads/leads.types';
import { CrmLeadsLegacyService } from './crm-leads-legacy.service';
import { AssignLeadBody, CreateLeadActivityBody } from './crm-leads-legacy.types';

@Controller('api/crm/leads')
@UseGuards(StaffOrInternalKeyGuard, StaffLeadsViewGuard)
export class CrmLeadsLegacyController {
  constructor(
    private readonly legacy: CrmLeadsLegacyService,
    private readonly leadsRepo: LeadsRepository,
    private readonly leadsWrite: LeadsWriteService,
  ) {}

  private actor(req: Request & { staffUser?: StaffJwtPayload }): string {
    return String(req.staffUser?.email ?? req.headers['x-ptt-actor'] ?? 'staff');
  }

  @Get(':id/activities')
  listActivities(
    @Param('id', ParseIntPipe) id: number,
    @Query('limit') limit?: string,
  ) {
    const lim = limit ? Number(limit) : 100;
    return this.legacy.listActivities(id, Number.isFinite(lim) ? lim : 100).then((activities) => ({
      activities,
    }));
  }

  @Post(':id/activities')
  @HttpCode(HttpStatus.CREATED)
  @UseGuards(StaffLeadsWriteGuard, LeadNotInReviewQueueGuard)
  createActivity(
    @Param('id', ParseIntPipe) id: number,
    @Body() body: CreateLeadActivityBody,
    @Req() req: Request & { staffUser?: StaffJwtPayload },
  ) {
    const userId = req.staffUser?.sub ? Number(req.staffUser.sub) : null;
    return this.legacy.createActivity(id, body, this.actor(req), userId);
  }

  @Get(':id/audit')
  audit(@Param('id', ParseIntPipe) id: number) {
    return this.legacy.auditLogs(id);
  }

  @Post(':id/assign')
  @UseGuards(StaffLeadsWriteGuard, LeadNotInReviewQueueGuard)
  assign(
    @Param('id', ParseIntPipe) id: number,
    @Body() body: AssignLeadBody,
    @Req() req: Request & { staffUser?: StaffJwtPayload },
  ) {
    return this.legacy.assignLead(id, body, this.actor(req));
  }

  @Patch(':id')
  @UseGuards(StaffLeadsWriteGuard, LeadNotInReviewQueueGuard)
  async patchLead(
    @Param('id', ParseIntPipe) id: number,
    @Body() body: PatchLeadV1Body & { audit_note?: string },
    @Req() req: Request & { staffUser?: StaffJwtPayload },
  ) {
    const prev = await this.leadsRepo.getLeadById(id);
    if (!prev) {
      throw new NotFoundException({ error: 'Not found' });
    }
    const lead = await this.leadsWrite.patchLead(id, body, this.actor(req));
    await this.legacy.mirrorPatchAudit(id, prev, lead, this.actor(req), body.audit_note ?? '');
    return { lead };
  }
}
