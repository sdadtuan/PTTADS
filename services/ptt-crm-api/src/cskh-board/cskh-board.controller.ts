import {
  Body,
  Controller,
  Get,
  Header,
  HttpCode,
  HttpStatus,
  Post,
  Query,
  Req,
  UseGuards,
} from '@nestjs/common';
import { Request } from 'express';
import { StaffOrInternalKeyGuard } from '../staff-auth/staff-or-internal-key.guard';
import { StaffJwtPayload } from '../staff-auth/staff-jwt.util';
import { StaffLeadsWriteGuard } from '../leads/guards/staff-leads-write.guard';
import { StaffLeadsViewGuard } from '../leads/guards/staff-leads-view.guard';
import { CskhBoardService } from './cskh-board.service';
import { CskhBulkAssignBody, CskhBulkRescheduleBody } from './cskh-board.types';

@Controller('api/crm/cskh-board')
@UseGuards(StaffOrInternalKeyGuard, StaffLeadsViewGuard)
export class CskhBoardController {
  constructor(private readonly board: CskhBoardService) {}

  private actor(req: Request & { staffUser?: StaffJwtPayload }): string {
    return String(req.staffUser?.email ?? req.headers['x-ptt-actor'] ?? 'staff');
  }

  @Get()
  list(
    @Query('owner_id') ownerId?: string,
    @Query('status') status?: string,
    @Query('source') source?: string,
    @Query('channel') channel?: string,
    @Query('q') q?: string,
    @Query('sla_filter') slaFilter?: string,
    @Query('limit') limit?: string,
    @Query('offset') offset?: string,
  ) {
    const filter =
      slaFilter === 'breach' || slaFilter === 'warning' || slaFilter === 'open' ? slaFilter : 'all';
    return this.board.getBoard({
      owner_id: ownerId ? Number(ownerId) : undefined,
      status,
      source,
      channel,
      q,
      sla_filter: filter,
      limit: limit ? Number(limit) : undefined,
      offset: offset ? Number(offset) : undefined,
    });
  }

  @Get('export')
  @Header('Content-Type', 'text/csv; charset=utf-8')
  async export(
    @Query('owner_id') ownerId?: string,
    @Query('status') status?: string,
    @Query('source') source?: string,
    @Query('channel') channel?: string,
    @Query('q') q?: string,
    @Query('sla_filter') slaFilter?: string,
  ) {
    const filter =
      slaFilter === 'breach' || slaFilter === 'warning' || slaFilter === 'open' ? slaFilter : 'all';
    const csv = await this.board.exportCsv({
      owner_id: ownerId ? Number(ownerId) : undefined,
      status,
      source,
      channel,
      q,
      sla_filter: filter,
    });
    return csv;
  }

  @Post('bulk-assign')
  @HttpCode(HttpStatus.OK)
  @UseGuards(StaffLeadsWriteGuard)
  bulkAssign(
    @Body() body: CskhBulkAssignBody,
    @Req() req: Request & { staffUser?: StaffJwtPayload },
  ) {
    return this.board.bulkAssign(body, this.actor(req));
  }

  @Post('bulk-reschedule')
  @HttpCode(HttpStatus.OK)
  @UseGuards(StaffLeadsWriteGuard)
  bulkReschedule(
    @Body() body: CskhBulkRescheduleBody,
    @Req() req: Request & { staffUser?: StaffJwtPayload },
  ) {
    const userId = req.staffUser?.sub ? Number(req.staffUser.sub) : null;
    return this.board.bulkReschedule(body, this.actor(req), userId);
  }
}
