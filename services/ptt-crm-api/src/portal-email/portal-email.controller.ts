import { Body, Controller, Get, Param, Post, Query, UseGuards } from '@nestjs/common';
import { PortalJwtGuard, PortalUser } from '../portal/portal-jwt.guard';
import { PortalJwtPayload } from '../portal/portal-jwt.util';
import { PortalEmailService } from './portal-email.service';
import { PortalEmailApprovalDecision } from './portal-email.types';

@Controller('api/v1/portal/email')
@UseGuards(PortalJwtGuard)
export class PortalEmailController {
  constructor(private readonly email: PortalEmailService) {}

  @Get('dashboard')
  dashboard(@PortalUser() user: PortalJwtPayload) {
    return this.email.dashboard(user);
  }

  @Get('campaigns')
  campaigns(@PortalUser() user: PortalJwtPayload) {
    return this.email.listCampaigns(user);
  }

  @Get('campaigns/:id/stats')
  campaignStats(@PortalUser() user: PortalJwtPayload, @Param('id') id: string) {
    return this.email.campaignStats(user, id.trim());
  }

  @Get('approvals/pending')
  pendingApprovals(@PortalUser() user: PortalJwtPayload) {
    return this.email.pendingApprovals(user);
  }

  @Get('approvals/:id/preview')
  approvalPreview(@PortalUser() user: PortalJwtPayload, @Param('id') id: string) {
    return this.email.approvalPreview(user, id.trim());
  }

  @Post('approvals/:id/approve')
  approve(@PortalUser() user: PortalJwtPayload, @Param('id') id: string) {
    return this.email.approveCampaign(user, id.trim());
  }

  @Post('approvals/:id/reject')
  reject(
    @PortalUser() user: PortalJwtPayload,
    @Param('id') id: string,
    @Body() body: PortalEmailApprovalDecision,
  ) {
    return this.email.rejectCampaign(user, id.trim(), body ?? {});
  }

  @Get('reports/summary')
  reportsSummary(@PortalUser() user: PortalJwtPayload, @Query('days') days?: string) {
    const parsed = days ? Number.parseInt(days, 10) : undefined;
    return this.email.reportsSummary(user, Number.isFinite(parsed) ? parsed : undefined);
  }
}
