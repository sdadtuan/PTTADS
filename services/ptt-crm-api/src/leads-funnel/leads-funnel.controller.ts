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
import { InternalKeyGuard } from '../auth/internal-key.guard';
import { StaffOrInternalKeyGuard } from '../staff-auth/staff-or-internal-key.guard';
import { StaffJwtPayload } from '../staff-auth/staff-jwt.util';
import { StaffLeadsViewGuard } from '../leads/guards/staff-leads-view.guard';
import { StaffLeadsWriteGuard } from '../leads/guards/staff-leads-write.guard';
import {
  CompleteCareStageBody,
  EnsurePresalesBody,
  PatchMarketingPlanBody,
  PatchPresalesTaskBody,
  ReleaseReviewQueueBody,
} from './leads-funnel.types';
import { LeadsFunnelEnabledGuard, PresalesOnLeadGuard } from './guards/leads-funnel-enabled.guard';
import { StaffLeadsGdkdGuard } from './guards/staff-leads-gdkd.guard';
import { LeadsFunnelService } from './leads-funnel.service';

@Controller('api/v1/leads')
@UseGuards(LeadsFunnelEnabledGuard)
export class LeadsFunnelController {
  constructor(private readonly funnel: LeadsFunnelService) {}

  private actor(req: Request & { staffUser?: StaffJwtPayload }): string {
    return String(req.staffUser?.email ?? req.headers['x-ptt-actor'] ?? 'staff');
  }

  private userId(req: Request & { staffUser?: StaffJwtPayload }): number | null {
    const sub = req.staffUser?.sub;
    return sub ? Number(sub) : null;
  }

  private badRequest(err: unknown): never {
    const msg = err instanceof Error ? err.message : String(err);
    throw new HttpException({ error: msg, message: msg }, HttpStatus.BAD_REQUEST);
  }

  @Get('review-queue/count')
  @UseGuards(StaffOrInternalKeyGuard, StaffLeadsViewGuard, StaffLeadsGdkdGuard)
  reviewQueueCount() {
    return this.funnel.reviewQueueCount();
  }

  @Get('review-queue')
  @UseGuards(StaffOrInternalKeyGuard, StaffLeadsViewGuard, StaffLeadsGdkdGuard)
  listReviewQueue(@Query('limit') limit?: string) {
    const lim = limit ? Number(limit) : 50;
    return this.funnel.listReviewQueue(Number.isFinite(lim) ? lim : 50);
  }

  @Post('review-queue/sync')
  @HttpCode(HttpStatus.OK)
  @UseGuards(InternalKeyGuard)
  syncReviewQueue(
    @Query('dry_run') dryRun?: string,
    @Req() req?: Request & { staffUser?: StaffJwtPayload },
  ) {
    const actor = req ? this.actor(req) : 'system:b2_review';
    return this.funnel.syncReviewQueue(actor, dryRun === '1' || dryRun === 'true');
  }

  @Get(':id/funnel')
  @UseGuards(StaffOrInternalKeyGuard, StaffLeadsViewGuard)
  getFunnel(@Param('id', ParseIntPipe) id: number) {
    return this.funnel.getFunnel(id);
  }

  @Get(':id/care-pipeline')
  @UseGuards(StaffOrInternalKeyGuard, StaffLeadsViewGuard)
  getCarePipeline(@Param('id', ParseIntPipe) id: number) {
    return this.funnel.getCarePipeline(id);
  }

  @Post(':id/care-pipeline/report')
  @HttpCode(HttpStatus.OK)
  @UseGuards(StaffOrInternalKeyGuard, StaffLeadsWriteGuard)
  submitCareReport(
    @Param('id', ParseIntPipe) id: number,
    @Body() body: CompleteCareStageBody,
    @Req() req: Request & { staffUser?: StaffJwtPayload },
  ) {
    try {
      return this.funnel.submitCareReport(id, body, this.actor(req), this.userId(req));
    } catch (err) {
      this.badRequest(err);
    }
  }

  @Post(':id/care-pipeline/complete')
  @HttpCode(HttpStatus.OK)
  @UseGuards(StaffOrInternalKeyGuard, StaffLeadsWriteGuard)
  completeCareStage(
    @Param('id', ParseIntPipe) id: number,
    @Body() body: CompleteCareStageBody,
    @Req() req: Request & { staffUser?: StaffJwtPayload },
  ) {
    try {
      return this.funnel.completeCareStage(id, body, this.actor(req));
    } catch (err) {
      this.badRequest(err);
    }
  }

  @Post(':id/review-queue/release')
  @HttpCode(HttpStatus.OK)
  @UseGuards(StaffOrInternalKeyGuard, StaffLeadsGdkdGuard)
  releaseReviewQueue(
    @Param('id', ParseIntPipe) id: number,
    @Body() body: ReleaseReviewQueueBody,
    @Req() req: Request & { staffUser?: StaffJwtPayload },
  ) {
    try {
      return this.funnel.releaseReviewQueue(id, body, this.actor(req));
    } catch (err) {
      this.badRequest(err);
    }
  }

  @Get(':id/presales')
  @UseGuards(StaffOrInternalKeyGuard, StaffLeadsViewGuard, PresalesOnLeadGuard)
  getPresales(@Param('id', ParseIntPipe) id: number) {
    return this.funnel.getPresales(id);
  }

  @Post(':id/presales')
  @HttpCode(HttpStatus.CREATED)
  @UseGuards(StaffOrInternalKeyGuard, StaffLeadsWriteGuard, PresalesOnLeadGuard)
  ensurePresales(
    @Param('id', ParseIntPipe) id: number,
    @Body() body: EnsurePresalesBody,
    @Req() req: Request & { staffUser?: StaffJwtPayload },
  ) {
    try {
      return this.funnel.ensurePresales(id, body, this.actor(req));
    } catch (err) {
      this.badRequest(err);
    }
  }

  @Post(':id/presales/advance')
  @HttpCode(HttpStatus.OK)
  @UseGuards(StaffOrInternalKeyGuard, StaffLeadsWriteGuard, PresalesOnLeadGuard)
  advancePresales(@Param('id', ParseIntPipe) id: number) {
    try {
      return this.funnel.advancePresales(id);
    } catch (err) {
      this.badRequest(err);
    }
  }

  @Patch(':id/presales/tasks/:taskId')
  @UseGuards(StaffOrInternalKeyGuard, StaffLeadsWriteGuard, PresalesOnLeadGuard)
  patchPresalesTask(
    @Param('id', ParseIntPipe) id: number,
    @Param('taskId', ParseIntPipe) taskId: number,
    @Body() body: PatchPresalesTaskBody,
    @Req() req: Request & { staffUser?: StaffJwtPayload },
  ) {
    return this.funnel.patchPresalesTask(id, taskId, body, this.userId(req));
  }

  @Get(':id/presales/marketing-plan')
  @UseGuards(StaffOrInternalKeyGuard, StaffLeadsViewGuard, PresalesOnLeadGuard)
  getMarketingPlan(@Param('id', ParseIntPipe) id: number) {
    return this.funnel.getMarketingPlan(id);
  }

  @Patch(':id/presales/marketing-plan')
  @UseGuards(StaffOrInternalKeyGuard, StaffLeadsWriteGuard, PresalesOnLeadGuard)
  patchMarketingPlan(@Param('id', ParseIntPipe) id: number, @Body() body: PatchMarketingPlanBody) {
    return this.funnel.patchMarketingPlan(id, body);
  }
}
