import {
  Body,
  Controller,
  Delete,
  Get,
  HttpCode,
  HttpStatus,
  Param,
  ParseIntPipe,
  Post,
  Query,
  UseGuards,
} from '@nestjs/common';
import { StaffOrInternalKeyGuard } from '../staff-auth/staff-or-internal-key.guard';
import {
  StaffProposalsViewGuard,
  StaffProposalsWriteGuard,
} from './guards/staff-proposals.guard';
import { ProposalsService } from './proposals.service';
import { CreateProposalBody } from './proposals.types';

@Controller('api/crm/proposals')
@UseGuards(StaffOrInternalKeyGuard, StaffProposalsViewGuard)
export class ProposalsController {
  constructor(private readonly proposals: ProposalsService) {}

  @Get()
  list(@Query('customer_id') customerId?: string) {
    return this.proposals.list(customerId);
  }

  @Get(':id')
  detail(@Param('id', ParseIntPipe) id: number) {
    return this.proposals.detail(id);
  }

  @Post()
  @HttpCode(HttpStatus.CREATED)
  @UseGuards(StaffProposalsWriteGuard)
  create(@Body() body: CreateProposalBody) {
    return this.proposals.create(body);
  }

  @Post(':id/generate')
  @UseGuards(StaffProposalsWriteGuard)
  generate(@Param('id', ParseIntPipe) id: number) {
    return this.proposals.generate(id);
  }

  @Delete(':id')
  @UseGuards(StaffProposalsWriteGuard)
  remove(@Param('id', ParseIntPipe) id: number) {
    return this.proposals.remove(id);
  }
}
