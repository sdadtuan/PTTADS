import {
  Body,
  Controller,
  Delete,
  Get,
  Param,
  ParseIntPipe,
  Post,
  UseGuards,
} from '@nestjs/common';
import {
  StaffSeoViewGuard,
  StaffSeoWriteGuard,
} from '../seo-admin/guards/staff-seo-view.guard';
import { StaffOrInternalKeyGuard } from '../staff-auth/staff-or-internal-key.guard';
import { SeoAeoService } from './seo-aeo.service';

@Controller('api/v1/seo')
@UseGuards(StaffOrInternalKeyGuard, StaffSeoViewGuard)
export class SeoAeoController {
  constructor(private readonly aeo: SeoAeoService) {}

  @Get('clients/:id/aeo/queries')
  async listQueries(@Param('id', ParseIntPipe) id: number) {
    const queries = await this.aeo.listQueries(id);
    const coverage = await this.aeo.coverage(id);
    return { ok: true, queries, coverage };
  }

  @Post('clients/:id/aeo/queries')
  @UseGuards(StaffSeoWriteGuard)
  async addQuery(@Param('id', ParseIntPipe) id: number, @Body() body: Record<string, unknown>) {
    const query = await this.aeo.addQuery(id, body);
    return { ok: true, query };
  }

  @Delete('aeo/queries/:questionId')
  @UseGuards(StaffSeoWriteGuard)
  async archiveQuery(@Param('questionId', ParseIntPipe) questionId: number) {
    return this.aeo.archiveQuery(questionId);
  }

  @Get('aeo/queries/:questionId/mentions')
  async listMentions(@Param('questionId', ParseIntPipe) questionId: number) {
    const mentions = await this.aeo.listMentions(questionId);
    return { ok: true, mentions };
  }

  @Get('clients/:id/aeo/coverage')
  async coverage(@Param('id', ParseIntPipe) id: number) {
    const coverage = await this.aeo.coverage(id);
    return { ok: true, coverage };
  }

  @Post('clients/:id/aeo/scan')
  @UseGuards(StaffSeoWriteGuard)
  async enqueueScan(@Param('id', ParseIntPipe) id: number, @Body() body: Record<string, unknown>) {
    const queryIds = Array.isArray(body.query_ids)
      ? body.query_ids.map((v) => Number(v)).filter((n) => !Number.isNaN(n))
      : undefined;
    return this.aeo.enqueueScan(id, queryIds);
  }

  @Post('clients/:id/aeo/scan/sync')
  @UseGuards(StaffSeoWriteGuard)
  async scanSync(@Param('id', ParseIntPipe) id: number, @Body() body: Record<string, unknown>) {
    const queryIds = Array.isArray(body.query_ids)
      ? body.query_ids.map((v) => Number(v)).filter((n) => !Number.isNaN(n))
      : undefined;
    const outcome = await this.aeo.scanBatchSync(id, queryIds);
    return { ok: outcome.ok, outcome };
  }
}
