import {
  Controller,
  ForbiddenException,
  Get,
  Query,
  Res,
  UseGuards,
} from '@nestjs/common';
import type { Response } from 'express';
import { PortalJwtGuard, PortalUser } from '../portal/portal-jwt.guard';
import { PortalJwtPayload } from '../portal/portal-jwt.util';
import {
  performanceExportFilename,
  performancePdfStub,
  performanceRowsToCsv,
} from './performance-export.util';
import { PerformanceService } from './performance.service';
import { PerformanceListResponse, PerformanceQuery } from './performance.types';

@Controller('api/v1/performance')
export class PerformanceController {
  constructor(private readonly performance: PerformanceService) {}

  @Get()
  @UseGuards(PortalJwtGuard)
  async list(
    @PortalUser() user: PortalJwtPayload,
    @Query() query: PerformanceQuery,
  ): Promise<PerformanceListResponse> {
    const requestedClient = query.client_id?.trim();
    if (requestedClient && requestedClient !== user.client_id) {
      throw new ForbiddenException({ error: 'client_id_mismatch' });
    }
    return this.performance.listForClient(user.client_id, query);
  }

  @Get('export.csv')
  @UseGuards(PortalJwtGuard)
  async exportCsv(
    @PortalUser() user: PortalJwtPayload,
    @Query() query: PerformanceQuery,
    @Res() res: Response,
  ): Promise<void> {
    const data = await this.performance.listForClient(user.client_id, query);
    const csv = performanceRowsToCsv(data.rows, data.group_by);
    const filename = performanceExportFilename(user.client_id, data.date_from, data.date_to);
    res.setHeader('Content-Type', 'text/csv; charset=utf-8');
    res.setHeader('Content-Disposition', `attachment; filename="${filename}"`);
    res.send(csv);
  }

  @Get('export.pdf')
  @UseGuards(PortalJwtGuard)
  async exportPdf(
    @PortalUser() user: PortalJwtPayload,
    @Query() query: PerformanceQuery,
    @Res() res: Response,
  ): Promise<void> {
    const data = await this.performance.listForClient(user.client_id, query);
    const pdf = performancePdfStub(user.client_id, data.date_from, data.date_to);
    const filename = performanceExportFilename(user.client_id, data.date_from, data.date_to).replace(
      '.csv',
      '.pdf',
    );
    res.setHeader('Content-Type', 'application/pdf');
    res.setHeader('Content-Disposition', `attachment; filename="${filename}"`);
    res.setHeader('X-PTT-Export-Stub', '1');
    res.send(pdf);
  }
}
