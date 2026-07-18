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
import { WriteEnabledGuard } from './guards/write-enabled.guard';
import { LeadsService } from './leads.service';
import { LeadsWriteService } from './leads-write.service';
import {
  CreateLeadV1Body,
  LeadV1,
  LeadsListResponseV1,
  PatchLeadV1Body,
} from './leads.types';

@Controller('api/v1/leads')
@UseGuards(InternalKeyGuard)
export class LeadsController {
  constructor(
    private readonly leadsService: LeadsService,
    private readonly leadsWriteService: LeadsWriteService,
  ) {}

  @Post()
  @HttpCode(HttpStatus.CREATED)
  @UseGuards(WriteEnabledGuard)
  async createLead(@Body() body: CreateLeadV1Body): Promise<LeadV1> {
    return this.leadsWriteService.createLead(body);
  }

  @Patch(':id')
  @UseGuards(WriteEnabledGuard)
  async patchLead(
    @Param('id', ParseIntPipe) id: number,
    @Body() body: PatchLeadV1Body,
    @Headers('x-ptt-actor') actor?: string,
  ): Promise<LeadV1> {
    return this.leadsWriteService.patchLead(id, body, actor);
  }

  @Get()
  async listLeads(
    @Query('client_id') clientId?: string,
    @Query('status') status?: string,
    @Query('source') source?: string,
    @Query('channel') channel?: string,
    @Query('q') q?: string,
    @Query('limit') limit?: string,
    @Query('offset') offset?: string,
  ): Promise<LeadsListResponseV1> {
    return this.leadsService.listLeads({
      client_id: clientId,
      status,
      source,
      channel,
      q,
      limit: limit !== undefined ? Number(limit) : undefined,
      offset: offset !== undefined ? Number(offset) : undefined,
    });
  }

  @Get(':id')
  async getLead(@Param('id', ParseIntPipe) id: number): Promise<LeadV1> {
    const lead = await this.leadsService.getLead(id);
    if (!lead) {
      throw new HttpException({ error: 'Not found' }, HttpStatus.NOT_FOUND);
    }
    return lead;
  }
}
