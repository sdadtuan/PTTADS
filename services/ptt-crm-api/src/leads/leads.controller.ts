import {
  Body,
  Controller,
  Get,
  Headers,
  HttpCode,
  HttpException,
  HttpStatus,
  Param,
  ParseIntPipe,
  Patch,
  Post,
  Query,
  UseGuards,
} from '@nestjs/common';
import { InternalKeyGuard } from '../auth/internal-key.guard';
import { StaffOrInternalKeyGuard } from '../staff-auth/staff-or-internal-key.guard';
import { WriteEnabledGuard } from './guards/write-enabled.guard';
import { StaffLeadsWriteGuard } from './guards/staff-leads-write.guard';
import { LeadNotInReviewQueueGuard } from '../leads-funnel/guards/lead-not-in-review-queue.guard';
import { LeadsService } from './leads.service';
import { LeadsWriteService } from './leads-write.service';
import {
  CreateLeadV1Body,
  LeadV1,
  LeadsListResponseV1,
  PatchLeadV1Body,
} from './leads.types';

@Controller('api/v1/leads')
export class LeadsController {
  constructor(
    private readonly leadsService: LeadsService,
    private readonly leadsWriteService: LeadsWriteService,
  ) {}

  @Post()
  @HttpCode(HttpStatus.CREATED)
  @UseGuards(InternalKeyGuard, WriteEnabledGuard)
  async createLead(@Body() body: CreateLeadV1Body): Promise<LeadV1> {
    return this.leadsWriteService.createLead(body);
  }

  @Patch(':id')
  @UseGuards(StaffOrInternalKeyGuard, StaffLeadsWriteGuard, WriteEnabledGuard, LeadNotInReviewQueueGuard)
  async patchLead(
    @Param('id', ParseIntPipe) id: number,
    @Body() body: PatchLeadV1Body,
    @Headers('x-ptt-actor') actor?: string,
  ): Promise<LeadV1> {
    return this.leadsWriteService.patchLead(id, body, actor);
  }

  @Get()
  @UseGuards(StaffOrInternalKeyGuard)
  async listLeads(
    @Query('client_id') clientId?: string,
    @Query('status') status?: string,
    @Query('source') source?: string,
    @Query('channel') channel?: string,
    @Query('q') q?: string,
    @Query('limit') limit?: string,
    @Query('offset') offset?: string,
    @Query('review_queue_only') reviewQueueOnly?: string,
    @Query('hide_review_queue') hideReviewQueue?: string,
  ): Promise<LeadsListResponseV1> {
    const truthy = (v?: string) => v === '1' || v === 'true';
    const hideExplicitFalse = hideReviewQueue === '0' || hideReviewQueue === 'false';
    return this.leadsService.listLeads({
      client_id: clientId,
      status,
      source,
      channel,
      q,
      limit: limit !== undefined ? Number(limit) : undefined,
      offset: offset !== undefined ? Number(offset) : undefined,
      review_queue_only: truthy(reviewQueueOnly),
      hide_review_queue: hideExplicitFalse ? false : undefined,
    });
  }

  @Get(':id')
  @UseGuards(StaffOrInternalKeyGuard)
  async getLead(@Param('id', ParseIntPipe) id: number): Promise<LeadV1> {
    const lead = await this.leadsService.getLead(id);
    if (!lead) {
      throw new HttpException({ error: 'Not found' }, HttpStatus.NOT_FOUND);
    }
    return lead;
  }
}
