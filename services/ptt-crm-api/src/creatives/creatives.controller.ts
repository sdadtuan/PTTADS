import { Body, Controller, Get, Param, Post, Query, UseGuards } from '@nestjs/common';
import { InternalKeyGuard } from '../auth/internal-key.guard';
import { PortalJwtGuard, PortalUser } from '../portal/portal-jwt.guard';
import { PortalJwtPayload } from '../portal/portal-jwt.util';
import { CreativesService } from './creatives.service';
import {
  CreateCreativeBody,
  CreateCreativeResponse,
  CreativeDecisionResponse,
  CreativeHistoryResponse,
  CreativePendingResponse,
  RejectCreativeBody,
} from './creatives.types';

@Controller('api/v1/creatives')
export class CreativesController {
  constructor(private readonly creatives: CreativesService) {}

  @Post()
  @UseGuards(InternalKeyGuard)
  async submit(@Body() body: CreateCreativeBody): Promise<CreateCreativeResponse> {
    return this.creatives.submit(body);
  }

  @Get('pending')
  @UseGuards(PortalJwtGuard)
  async listPending(@PortalUser() user: PortalJwtPayload): Promise<CreativePendingResponse> {
    return this.creatives.listPending(user.client_id);
  }

  @Get('history')
  @UseGuards(PortalJwtGuard)
  async listHistory(
    @PortalUser() user: PortalJwtPayload,
    @Query('days') days?: string,
  ): Promise<CreativeHistoryResponse> {
    return this.creatives.listHistory(user.client_id, Number(days) || 30);
  }

  @Get('pending/count')
  @UseGuards(PortalJwtGuard)
  async pendingCount(@PortalUser() user: PortalJwtPayload): Promise<{ ok: boolean; count: number }> {
    return this.creatives.pendingCount(user.client_id);
  }

  @Post(':id/approve')
  @UseGuards(PortalJwtGuard)
  async approve(
    @PortalUser() user: PortalJwtPayload,
    @Param('id') id: string,
  ): Promise<CreativeDecisionResponse> {
    return this.creatives.approve(user, id.trim());
  }

  @Post(':id/reject')
  @UseGuards(PortalJwtGuard)
  async reject(
    @PortalUser() user: PortalJwtPayload,
    @Param('id') id: string,
    @Body() body: RejectCreativeBody,
  ): Promise<CreativeDecisionResponse> {
    return this.creatives.reject(user, id.trim(), body?.note);
  }
}
