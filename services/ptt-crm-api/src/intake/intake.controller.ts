import {
  Body,
  Controller,
  Get,
  HttpCode,
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
import { StaffIntakeViewGuard, StaffIntakeWriteGuard } from './guards/staff-intake.guard';
import { IntakeService } from './intake.service';
import { CreateIntakeSessionBody, PatchIntakeSessionBody } from './intake.types';

@Controller('api/crm/intake')
@UseGuards(StaffOrInternalKeyGuard, StaffIntakeViewGuard)
export class IntakeController {
  constructor(private readonly intake: IntakeService) {}

  @Get('definitions')
  definitions() {
    return this.intake.getDefinitions();
  }

  @Get('definitions/:slug')
  definition(@Param('slug') slug: string) {
    return this.intake.getDefinition(slug);
  }

  @Get('stats')
  stats(@Query('am_id') amId?: string, @Query('by_am') byAm?: string) {
    const aid = amId ? Number(amId) : undefined;
    const byAmFlag = ['1', 'true', 'yes'].includes(String(byAm ?? '').toLowerCase());
    return this.intake.getStats(
      aid && Number.isFinite(aid) ? aid : undefined,
      byAmFlag,
    );
  }

  @Get('entry')
  entry(
    @Query('lead_id') leadId?: string,
    @Query('mode') mode?: string,
    @Query('form') form?: string,
  ) {
    const lid = leadId ? Number(leadId) : undefined;
    return this.intake.resolveEntry(lid, mode, form);
  }

  @Get('sessions')
  listSessions(
    @Query('lead_id') leadId?: string,
    @Query('lifecycle_id') lifecycleId?: string,
  ) {
    const lid = leadId ? Number(leadId) : undefined;
    const lcid = lifecycleId ? Number(lifecycleId) : undefined;
    return this.intake.listSessions(
      lid && Number.isFinite(lid) ? lid : undefined,
      lcid && Number.isFinite(lcid) ? lcid : undefined,
    );
  }

  @Post('sessions')
  @HttpCode(HttpStatus.CREATED)
  @UseGuards(StaffIntakeWriteGuard)
  createSession(@Body() body: CreateIntakeSessionBody) {
    return this.intake.createSession(body);
  }

  @Post('sessions/:id/reopen')
  @UseGuards(StaffIntakeWriteGuard)
  reopenSession(@Param('id', ParseIntPipe) id: number) {
    return this.intake.reopenSession(id);
  }

  @Post('sessions/:id/ai-summary')
  @UseGuards(StaffIntakeWriteGuard)
  aiSummary(@Param('id', ParseIntPipe) id: number) {
    return this.intake.generateAiSummary(id);
  }

  @Get('sessions/:id')
  getSession(@Param('id', ParseIntPipe) id: number) {
    return this.intake.getSession(id);
  }

  @Patch('sessions/:id')
  @UseGuards(StaffIntakeWriteGuard)
  patchSession(@Param('id', ParseIntPipe) id: number, @Body() body: PatchIntakeSessionBody) {
    return this.intake.updateSession(id, body);
  }

  @Post('sessions/:id/complete')
  @UseGuards(StaffIntakeWriteGuard)
  completeSession(
    @Param('id', ParseIntPipe) id: number,
    @Req() req: Request & { staffUser?: StaffJwtPayload },
  ) {
    const actorId = req.staffUser?.sub ? Number(req.staffUser.sub) : null;
    return this.intake.completeSession(id, Number.isFinite(actorId) ? actorId : null);
  }
}
