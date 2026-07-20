import { Body, Controller, Get, Param, Post, Query, UseGuards } from '@nestjs/common';
import { PortalJwtGuard, PortalUser } from '../portal/portal-jwt.guard';
import { PortalJwtPayload } from '../portal/portal-jwt.util';
import { PortalSeoService } from './portal-seo.service';
import { PortalSeoReportType, PortalSeoReviewBody } from './portal-seo.types';

const REPORT_TYPES = new Set<PortalSeoReportType>(['executive', 'seo', 'aeo', 'technical', 'content']);

@Controller('api/v1/portal/seo')
@UseGuards(PortalJwtGuard)
export class PortalSeoController {
  constructor(private readonly seo: PortalSeoService) {}

  @Get('summary')
  summary(@PortalUser() user: PortalJwtPayload) {
    return this.seo.summary(user);
  }

  @Get('widgets')
  widgets(@PortalUser() user: PortalJwtPayload) {
    return this.seo.widgets(user);
  }

  @Get('reports/executive')
  executiveReport(
    @PortalUser() user: PortalJwtPayload,
    @Query('type') type?: string,
  ) {
    const dashboardType = REPORT_TYPES.has(type as PortalSeoReportType)
      ? (type as PortalSeoReportType)
      : 'executive';
    return this.seo.executiveReport(user, dashboardType);
  }

  @Get('content/pending')
  pending(@PortalUser() user: PortalJwtPayload) {
    return this.seo.pendingContent(user);
  }

  @Get('content/:id')
  detail(@PortalUser() user: PortalJwtPayload, @Param('id') id: string) {
    return this.seo.contentDetail(user, id.trim());
  }

  @Post('content/:id/review')
  review(
    @PortalUser() user: PortalJwtPayload,
    @Param('id') id: string,
    @Body() body: PortalSeoReviewBody,
  ) {
    return this.seo.reviewContent(user, id.trim(), body ?? { approved: true });
  }
}
