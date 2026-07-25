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
import { SeoRanksService } from './seo-ranks.service';

@Controller('api/v1/seo')
@UseGuards(StaffOrInternalKeyGuard, StaffSeoViewGuard)
export class SeoRanksController {
  constructor(private readonly ranks: SeoRanksService) {}

  @Get('clients/:id/ranks/keywords')
  async listKeywords(@Param('id', ParseIntPipe) id: number) {
    const keywords = await this.ranks.listKeywords(id);
    const sov = await this.ranks.shareOfVoice(id);
    return { ok: true, keywords, sov };
  }

  @Post('clients/:id/ranks/keywords')
  @UseGuards(StaffSeoWriteGuard)
  async addKeyword(@Param('id', ParseIntPipe) id: number, @Body() body: Record<string, unknown>) {
    const keyword = await this.ranks.addKeyword(id, body);
    return { ok: true, keyword };
  }

  @Post('clients/:id/ranks/import')
  @UseGuards(StaffSeoWriteGuard)
  async importCsv(@Param('id', ParseIntPipe) id: number, @Body() body: Record<string, unknown>) {
    const csvText = String(body.csv_text ?? body.csv ?? '');
    return this.ranks.importCsv(id, csvText);
  }

  @Post('clients/:id/ranks/capture')
  @UseGuards(StaffSeoWriteGuard)
  async capture(@Param('id', ParseIntPipe) id: number) {
    return this.ranks.captureRanks(id);
  }

  @Get('clients/:id/ranks/sov')
  async sov(@Param('id', ParseIntPipe) id: number, @Query('top_n') topN?: string) {
    const n = topN ? Number.parseInt(topN, 10) : 10;
    const sov = await this.ranks.shareOfVoice(id, Number.isNaN(n) ? 10 : n);
    return { ok: true, sov };
  }
}
