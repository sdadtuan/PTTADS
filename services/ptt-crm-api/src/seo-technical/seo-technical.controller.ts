import {
  Body,
  Controller,
  Get,
  Param,
  ParseIntPipe,
  Patch,
  Post,
  Put,
  Query,
  UseGuards,
} from '@nestjs/common';
import {
  StaffSeoTechnicalGuard,
  StaffSeoViewGuard,
} from '../seo-admin/guards/staff-seo-view.guard';
import { StaffOrInternalKeyGuard } from '../staff-auth/staff-or-internal-key.guard';
import { SeoTechnicalService } from './seo-technical.service';

@Controller('api/v1/seo')
@UseGuards(StaffOrInternalKeyGuard, StaffSeoViewGuard)
export class SeoTechnicalController {
  constructor(private readonly technical: SeoTechnicalService) {}

  @Get('clients/:id/issues')
  async issues(
    @Param('id', ParseIntPipe) id: number,
    @Query('severity') severity?: string,
    @Query('status') status?: string,
  ) {
    const items = await this.technical.listIssues(id, { severity, status });
    const matrix = await this.technical.severityMatrix(id);
    return { ok: true, issues: items, severity_matrix: matrix };
  }

  @Get('clients/:id/issues/severity-matrix')
  async matrix(@Param('id', ParseIntPipe) id: number) {
    const severity_matrix = await this.technical.severityMatrix(id);
    return { ok: true, severity_matrix };
  }

  @Post('clients/:id/issues')
  @UseGuards(StaffSeoTechnicalGuard)
  async createIssue(@Param('id', ParseIntPipe) id: number, @Body() body: Record<string, unknown>) {
    const issue = await this.technical.createIssue(id, body);
    return { ok: true, issue };
  }

  @Post('clients/:id/issues/import')
  @UseGuards(StaffSeoTechnicalGuard)
  async importIssues(@Param('id', ParseIntPipe) id: number, @Body() body: { csv?: string }) {
    return this.technical.importCrawlCsv(id, String(body.csv ?? ''));
  }

  @Patch('issues/:id')
  @UseGuards(StaffSeoTechnicalGuard)
  async patchIssue(@Param('id', ParseIntPipe) id: number, @Body() body: Record<string, unknown>) {
    const issue = await this.technical.updateIssue(id, body);
    return { ok: true, issue };
  }

  @Get('clients/:id/cwv')
  async cwv(@Param('id', ParseIntPipe) id: number) {
    const data = await this.technical.listCwv(id);
    return { ok: true, ...data };
  }

  @Post('clients/:id/cwv/capture')
  @UseGuards(StaffSeoTechnicalGuard)
  async captureCwv(@Param('id', ParseIntPipe) id: number) {
    const result = await this.technical.captureCwv(id);
    return { ok: true, ...result };
  }

  @Get('clients/:id/crawl-schedule')
  crawlSchedule(@Param('id', ParseIntPipe) id: number) {
    return this.technical.getCrawlSchedule(id);
  }

  @Put('clients/:id/crawl-schedule')
  @UseGuards(StaffSeoTechnicalGuard)
  upsertCrawlSchedule(@Param('id', ParseIntPipe) id: number, @Body() body: Record<string, unknown>) {
    return this.technical.upsertCrawlSchedule(id, body);
  }
}
