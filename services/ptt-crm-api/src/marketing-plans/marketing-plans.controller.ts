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
  UseGuards,
} from '@nestjs/common';
import { StaffOrInternalKeyGuard } from '../staff-auth/staff-or-internal-key.guard';
import {
  StaffMarketingPlansViewGuard,
  StaffMarketingPlansWriteGuard,
} from './guards/staff-marketing-plans.guard';
import { MarketingPlansService } from './marketing-plans.service';
import { CreateMarketingPlanBody, PatchMarketingPlanBody } from './marketing-plans.types';

@Controller('api/crm/marketing-plans')
@UseGuards(StaffOrInternalKeyGuard, StaffMarketingPlansViewGuard)
export class MarketingPlansController {
  constructor(private readonly marketingPlans: MarketingPlansService) {}

  @Get()
  list(
    @Query('fiscal_year') fiscalYear?: string,
    @Query('status') status?: string,
    @Query('q') q?: string,
  ) {
    let fy: number | undefined;
    if (fiscalYear) {
      const parsed = Number(fiscalYear);
      if (Number.isFinite(parsed)) {
        fy = Math.max(1990, Math.min(2120, parsed));
      }
    }
    return this.marketingPlans.list(fy, status, q);
  }

  @Get(':id/segment-refs')
  segmentRefs(@Param('id', ParseIntPipe) id: number) {
    return this.marketingPlans.segmentRefs(id);
  }

  @Get(':id')
  detail(@Param('id', ParseIntPipe) id: number) {
    return this.marketingPlans.detail(id);
  }

  @Post()
  @HttpCode(HttpStatus.CREATED)
  @UseGuards(StaffMarketingPlansWriteGuard)
  create(@Body() body: CreateMarketingPlanBody) {
    return this.marketingPlans.create(body);
  }

  @Patch(':id')
  @UseGuards(StaffMarketingPlansWriteGuard)
  patch(@Param('id', ParseIntPipe) id: number, @Body() body: PatchMarketingPlanBody) {
    return this.marketingPlans.patch(id, body);
  }
}
