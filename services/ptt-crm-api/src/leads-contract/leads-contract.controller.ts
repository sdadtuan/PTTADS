import {
  Body,
  Controller,
  Get,
  HttpCode,
  HttpException,
  HttpStatus,
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
import { StaffLeadsViewGuard } from '../leads/guards/staff-leads-view.guard';
import { StaffLeadsWriteGuard } from '../leads/guards/staff-leads-write.guard';
import { PresalesOnLeadGuard } from '../leads-funnel/guards/leads-funnel-enabled.guard';
import { LeadNotInReviewQueueGuard } from '../leads-funnel/guards/lead-not-in-review-queue.guard';
import { StaffLeadsGdkdGuard } from '../leads-funnel/guards/staff-leads-gdkd.guard';
import { LeadsFunnelEnabledGuard } from '../leads-funnel/guards/leads-funnel-enabled.guard';
import { ServiceDeliveryNestGuard } from './guards/service-delivery-nest.guard';
import { LeadsContractService } from './leads-contract.service';
import type { CreateContractBody, PatchContractBody, RejectApprovalBody, SubmitContractBody } from './contract.types';

@Controller('api/v1/leads')
@UseGuards(ServiceDeliveryNestGuard, LeadsFunnelEnabledGuard)
export class LeadsContractController {
  constructor(private readonly contracts: LeadsContractService) {}

  private actor(req: Request & { staffUser?: StaffJwtPayload }): string {
    return String(req.staffUser?.email ?? req.headers['x-ptt-actor'] ?? 'staff');
  }

  private badRequest(err: unknown): never {
    const msg = err instanceof Error ? err.message : String(err);
    throw new HttpException({ error: msg, message: msg }, HttpStatus.BAD_REQUEST);
  }

  @Get(':id/contract/readiness')
  @UseGuards(StaffOrInternalKeyGuard, StaffLeadsViewGuard, PresalesOnLeadGuard)
  readiness(@Param('id', ParseIntPipe) id: number) {
    return this.contracts.getReadiness(id);
  }

  @Get(':id/contract')
  @UseGuards(StaffOrInternalKeyGuard, StaffLeadsViewGuard, PresalesOnLeadGuard)
  getContract(@Param('id', ParseIntPipe) id: number) {
    return this.contracts.getContractForLead(id);
  }

  @Post(':id/contract')
  @HttpCode(HttpStatus.CREATED)
  @UseGuards(StaffOrInternalKeyGuard, StaffLeadsWriteGuard, PresalesOnLeadGuard, LeadNotInReviewQueueGuard)
  createContract(
    @Param('id', ParseIntPipe) id: number,
    @Body() body: CreateContractBody,
    @Req() req: Request & { staffUser?: StaffJwtPayload },
  ) {
    try {
      return this.contracts.createDraft(id, body, this.actor(req));
    } catch (err) {
      this.badRequest(err);
    }
  }

  @Patch(':id/contract/:contractId')
  @UseGuards(StaffOrInternalKeyGuard, StaffLeadsWriteGuard, PresalesOnLeadGuard, LeadNotInReviewQueueGuard)
  patchContract(
    @Param('id', ParseIntPipe) id: number,
    @Param('contractId', ParseIntPipe) contractId: number,
    @Body() body: PatchContractBody,
  ) {
    try {
      return this.contracts.patchContract(contractId, id, body);
    } catch (err) {
      this.badRequest(err);
    }
  }

  @Post(':id/contract/:contractId/submit')
  @HttpCode(HttpStatus.OK)
  @UseGuards(StaffOrInternalKeyGuard, StaffLeadsWriteGuard, PresalesOnLeadGuard, LeadNotInReviewQueueGuard)
  submitContract(
    @Param('id', ParseIntPipe) id: number,
    @Param('contractId', ParseIntPipe) contractId: number,
    @Body() body: SubmitContractBody,
    @Req() req: Request & { staffUser?: StaffJwtPayload },
  ) {
    try {
      return this.contracts.submit(contractId, id, this.actor(req), String(body.notes ?? ''));
    } catch (err) {
      this.badRequest(err);
    }
  }
}

@Controller('api/v1/contracts')
@UseGuards(ServiceDeliveryNestGuard)
export class ContractsApprovalController {
  constructor(private readonly contracts: LeadsContractService) {}

  private actor(req: Request & { staffUser?: StaffJwtPayload }): string {
    return String(req.staffUser?.email ?? req.headers['x-ptt-actor'] ?? 'staff');
  }

  private badRequest(err: unknown): never {
    const msg = err instanceof Error ? err.message : String(err);
    throw new HttpException({ error: msg, message: msg }, HttpStatus.BAD_REQUEST);
  }

  @Get('approvals/pending')
  @UseGuards(StaffOrInternalKeyGuard, StaffLeadsGdkdGuard)
  listPending(@Query('limit') limit?: string) {
    const lim = limit ? Number(limit) : 50;
    return this.contracts.listPendingApprovals(Number.isFinite(lim) ? lim : 50);
  }

  @Post('approvals/:id/approve')
  @HttpCode(HttpStatus.OK)
  @UseGuards(StaffOrInternalKeyGuard, StaffLeadsGdkdGuard)
  approve(@Param('id', ParseIntPipe) id: number, @Req() req: Request & { staffUser?: StaffJwtPayload }) {
    try {
      return this.contracts.approve(id, this.actor(req));
    } catch (err) {
      this.badRequest(err);
    }
  }

  @Post('approvals/:id/reject')
  @HttpCode(HttpStatus.OK)
  @UseGuards(StaffOrInternalKeyGuard, StaffLeadsGdkdGuard)
  reject(
    @Param('id', ParseIntPipe) id: number,
    @Body() body: RejectApprovalBody,
    @Req() req: Request & { staffUser?: StaffJwtPayload },
  ) {
    try {
      return this.contracts.reject(id, this.actor(req), String(body.decision_notes ?? ''));
    } catch (err) {
      this.badRequest(err);
    }
  }
}

@Controller('api/v1/agency/clients')
@UseGuards(ServiceDeliveryNestGuard, StaffOrInternalKeyGuard, StaffLeadsViewGuard)
export class AgencyContractsController {
  constructor(private readonly contracts: LeadsContractService) {}

  @Get(':clientId/contracts')
  listClientContracts(@Param('clientId') clientId: string, @Query('limit') limit?: string) {
    const lim = limit ? Number(limit) : 50;
    return this.contracts.listByClient(clientId, Number.isFinite(lim) ? lim : 50);
  }
}
