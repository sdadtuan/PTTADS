import {
  Body,
  Controller,
  Get,
  Param,
  ParseIntPipe,
  Post,
  Query,
  UseGuards,
} from '@nestjs/common';
import { StaffSeoViewGuard, StaffSeoWriteGuard } from '../seo-admin/guards/staff-seo-view.guard';
import { StaffOrInternalKeyGuard } from '../staff-auth/staff-or-internal-key.guard';
import { SeoFreshnessService } from './seo-freshness.service';

@Controller('api/v1/seo')
@UseGuards(StaffOrInternalKeyGuard, StaffSeoViewGuard)
export class SeoFreshnessController {
  constructor(private readonly freshness: SeoFreshnessService) {}

  @Get('clients/:id/freshness/queue')
  async queue(
    @Param('id', ParseIntPipe) id: number,
    @Query('min_priority') minPriority?: string,
  ) {
    const items = await this.freshness.listQueue(id, minPriority);
    return { ok: true, items };
  }

  @Post('clients/:id/freshness/rescore')
  @UseGuards(StaffSeoWriteGuard)
  async rescoreAll(@Param('id', ParseIntPipe) id: number) {
    return this.freshness.scoreAll(id);
  }

  @Post('clients/:id/freshness/rescore/:contentId')
  @UseGuards(StaffSeoWriteGuard)
  async rescoreOne(
    @Param('id', ParseIntPipe) id: number,
    @Param('contentId', ParseIntPipe) contentId: number,
  ) {
    return this.freshness.scoreContent(id, contentId);
  }

  @Post('freshness/:contentId/refresh')
  @UseGuards(StaffSeoWriteGuard)
  async flagRefresh(@Param('contentId', ParseIntPipe) contentId: number) {
    return this.freshness.flagRefresh(contentId);
  }
}
