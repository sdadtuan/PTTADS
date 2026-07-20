import {
  Body,
  Controller,
  Get,
  HttpCode,
  HttpStatus,
  Param,
  Patch,
  Post,
  Query,
  Req,
  UseGuards,
} from '@nestjs/common';
import { Request } from 'express';
import { StaffOrInternalKeyGuard } from '../staff-auth/staff-or-internal-key.guard';
import { StaffJwtPayload } from '../staff-auth/staff-jwt.util';
import { EmailMarketingService } from './email-marketing.service';
import {
  EmailGovernanceResponse,
  EmailHubResponse,
  EmailImportResult,
  EmailListResponse,
  EmailClientListRow,
  EmailConsentRow,
  EmailContactRow,
  EmailSuppressionRow,
  EmailWorkspaceRow,
  EmailSegmentRow,
  EmailTemplateRow,
  EmailCampaignRow,
  EmailPreflightResponse,
  EmailSegmentComputeResult,
  EmailJourneyRow,
  EmailExperimentRow,
  EmailExperimentRollupResult,
  EmailDeliverabilityDomainRow,
  EmailReportsSummary,
  EmailReportsCampaignStats,
  EmailDeliverabilityReport,
  EmailReportScheduleRow,
  EmailClickhouseExportResult,
} from './email-marketing.types';
import { StaffEmailApproveGuard } from './guards/staff-email-approve.guard';
import { StaffEmailDeliverabilityGuard } from './guards/staff-email-deliverability.guard';
import { StaffEmailReportsGuard } from './guards/staff-email-reports.guard';
import { StaffEmailComplianceGuard } from './guards/staff-email-compliance.guard';
import { StaffEmailSettingsGuard } from './guards/staff-email-settings.guard';
import { StaffEmailViewGuard } from './guards/staff-email-view.guard';
import { StaffEmailWriteGuard } from './guards/staff-email-write.guard';

type StaffReq = Request & { staffUser?: StaffJwtPayload; staffAuthVia?: 'internal' | 'jwt' };

function actorFromReq(req: StaffReq): string {
  if (req.staffAuthVia === 'internal') return 'internal_key';
  return req.staffUser?.email ?? 'staff';
}

@Controller('api/v1/email')
@UseGuards(StaffOrInternalKeyGuard, StaffEmailViewGuard)
export class EmailMarketingController {
  constructor(private readonly email: EmailMarketingService) {}

  @Get('hub')
  async hub(
    @Query('client_id') clientId?: string,
    @Query('days') days?: string,
    @Query('domain') domain?: string,
  ): Promise<EmailHubResponse> {
    const parsedDays = days ? Number.parseInt(days, 10) : undefined;
    return this.email.hub({
      clientId,
      days: Number.isFinite(parsedDays) ? parsedDays : undefined,
      domain,
    });
  }

  @Get('governance')
  async governance(@Query('scope') scope?: string): Promise<EmailGovernanceResponse> {
    return this.email.governance({ scope });
  }

  @Get('clients')
  async clients(
    @Query('q') q?: string,
    @Query('has_workspace') hasWorkspace?: string,
    @Query('limit') limit?: string,
    @Query('offset') offset?: string,
  ): Promise<EmailListResponse<EmailClientListRow>> {
    const hw =
      hasWorkspace === '1' || hasWorkspace === 'true'
        ? true
        : hasWorkspace === '0' || hasWorkspace === 'false'
          ? false
          : undefined;
    return this.email.listClients({
      q,
      has_workspace: hw,
      limit: limit ? Number.parseInt(limit, 10) : undefined,
      offset: offset ? Number.parseInt(offset, 10) : undefined,
    });
  }

  @Get('workspaces')
  async workspaces(
    @Query('client_id') clientId?: string,
    @Query('limit') limit?: string,
    @Query('offset') offset?: string,
  ): Promise<EmailListResponse<EmailWorkspaceRow>> {
    return this.email.listWorkspaces({
      clientId,
      limit: limit ? Number.parseInt(limit, 10) : undefined,
      offset: offset ? Number.parseInt(offset, 10) : undefined,
    });
  }

  @Post('workspaces')
  @HttpCode(HttpStatus.CREATED)
  @UseGuards(StaffEmailSettingsGuard)
  async createWorkspace(
    @Req() req: StaffReq,
    @Body()
    body: {
      client_id: string;
      name?: string;
      default_from_name?: string;
      default_from_email?: string;
      default_reply_to?: string;
      esp_provider?: string;
      daily_send_cap?: number;
      frequency_cap_7d?: number;
      timezone?: string;
    },
  ): Promise<EmailWorkspaceRow> {
    return this.email.createWorkspace({
      clientId: body.client_id,
      name: body.name ?? '',
      defaultFromName: body.default_from_name,
      defaultFromEmail: body.default_from_email,
      defaultReplyTo: body.default_reply_to,
      espProvider: body.esp_provider,
      dailySendCap: body.daily_send_cap,
      frequencyCap7d: body.frequency_cap_7d,
      timezone: body.timezone,
      actor: actorFromReq(req),
    });
  }

  @Patch('workspaces/:id')
  @UseGuards(StaffEmailSettingsGuard)
  async patchWorkspace(
    @Req() req: StaffReq,
    @Param('id') id: string,
    @Body() body: Record<string, unknown>,
  ): Promise<EmailWorkspaceRow> {
    return this.email.updateWorkspace({
      workspaceId: id,
      patch: body,
      actor: actorFromReq(req),
    });
  }

  @Get('contacts')
  async contacts(
    @Query('client_id') clientId?: string,
    @Query('q') q?: string,
    @Query('limit') limit?: string,
    @Query('offset') offset?: string,
  ): Promise<EmailListResponse<EmailContactRow>> {
    return this.email.listContacts({
      clientId,
      q,
      limit: limit ? Number.parseInt(limit, 10) : undefined,
      offset: offset ? Number.parseInt(offset, 10) : undefined,
    });
  }

  @Post('contacts/import')
  @HttpCode(HttpStatus.OK)
  @UseGuards(StaffEmailWriteGuard)
  async importContacts(
    @Req() req: StaffReq,
    @Body()
    body: {
      client_id: string;
      rows: Array<{ email: string; first_name?: string; last_name?: string; lifecycle_stage?: string }>;
    },
  ): Promise<EmailImportResult> {
    return this.email.importContacts({
      clientId: body.client_id,
      rows: body.rows ?? [],
      actor: actorFromReq(req),
    });
  }

  @Get('consent')
  async consent(
    @Query('client_id') clientId?: string,
    @Query('contact_id') contactId?: string,
    @Query('topic') topic?: string,
    @Query('limit') limit?: string,
    @Query('offset') offset?: string,
  ): Promise<EmailListResponse<EmailConsentRow>> {
    return this.email.listConsent({
      clientId,
      contactId,
      topic,
      limit: limit ? Number.parseInt(limit, 10) : undefined,
      offset: offset ? Number.parseInt(offset, 10) : undefined,
    });
  }

  @Post('consent')
  @HttpCode(HttpStatus.CREATED)
  @UseGuards(StaffEmailComplianceGuard)
  async recordConsent(
    @Req() req: StaffReq,
    @Body()
    body: {
      client_id: string;
      contact_id?: string;
      email?: string;
      topic?: string;
      status: string;
      source?: string;
      consent_version?: string;
    },
  ): Promise<{ ok: boolean; consent_id: string; contact_id: string; preference_token?: string }> {
    return this.email.recordConsent({
      clientId: body.client_id,
      contactId: body.contact_id,
      email: body.email,
      topic: body.topic,
      status: body.status,
      source: body.source,
      consentVersion: body.consent_version,
      recordedBy: actorFromReq(req),
    });
  }

  @Get('suppression')
  async suppression(
    @Query('client_id') clientId?: string,
    @Query('q') q?: string,
    @Query('limit') limit?: string,
    @Query('offset') offset?: string,
  ): Promise<EmailListResponse<EmailSuppressionRow>> {
    return this.email.listSuppression({
      clientId,
      q,
      limit: limit ? Number.parseInt(limit, 10) : undefined,
      offset: offset ? Number.parseInt(offset, 10) : undefined,
    });
  }

  @Post('suppression')
  @HttpCode(HttpStatus.CREATED)
  @UseGuards(StaffEmailComplianceGuard)
  async addSuppression(
    @Req() req: StaffReq,
    @Body()
    body: {
      client_id?: string;
      email: string;
      reason: string;
      scope?: string;
    },
  ): Promise<{ ok: boolean; id: string }> {
    return this.email.addSuppression({
      clientId: body.client_id,
      email: body.email,
      reason: body.reason,
      scope: body.scope,
      createdBy: actorFromReq(req),
    });
  }

  @Get('segments')
  async segments(
    @Query('client_id') clientId?: string,
    @Query('limit') limit?: string,
    @Query('offset') offset?: string,
  ): Promise<EmailListResponse<EmailSegmentRow>> {
    return this.email.listSegments({
      clientId,
      limit: limit ? Number.parseInt(limit, 10) : undefined,
      offset: offset ? Number.parseInt(offset, 10) : undefined,
    });
  }

  @Post('segments')
  @HttpCode(HttpStatus.CREATED)
  @UseGuards(StaffEmailWriteGuard)
  async createSegment(
    @Req() req: StaffReq,
    @Body()
    body: {
      client_id: string;
      name: string;
      segment_type?: string;
      definition_json?: Record<string, unknown>;
    },
  ): Promise<EmailSegmentRow> {
    return this.email.createSegment({
      clientId: body.client_id,
      name: body.name,
      segmentType: body.segment_type,
      definitionJson: body.definition_json,
      actor: actorFromReq(req),
    });
  }

  @Get('segments/:id')
  async getSegment(@Param('id') id: string): Promise<EmailSegmentRow> {
    return this.email.getSegment(id);
  }

  @Patch('segments/:id')
  @UseGuards(StaffEmailWriteGuard)
  async patchSegment(
    @Req() req: StaffReq,
    @Param('id') id: string,
    @Body()
    body: {
      name?: string;
      segment_type?: string;
      definition_json?: Record<string, unknown>;
    },
  ): Promise<EmailSegmentRow> {
    return this.email.updateSegment({
      id,
      name: body.name,
      segmentType: body.segment_type,
      definitionJson: body.definition_json,
      actor: actorFromReq(req),
    });
  }

  @Post('segments/:id/compute')
  @HttpCode(HttpStatus.OK)
  @UseGuards(StaffEmailWriteGuard)
  async computeSegment(
    @Req() req: StaffReq,
    @Param('id') id: string,
  ): Promise<EmailSegmentComputeResult> {
    return this.email.computeSegment(id, actorFromReq(req));
  }

  @Get('templates')
  async templates(
    @Query('client_id') clientId?: string,
    @Query('limit') limit?: string,
    @Query('offset') offset?: string,
  ): Promise<EmailListResponse<EmailTemplateRow>> {
    return this.email.listTemplates({
      clientId,
      limit: limit ? Number.parseInt(limit, 10) : undefined,
      offset: offset ? Number.parseInt(offset, 10) : undefined,
    });
  }

  @Post('templates')
  @HttpCode(HttpStatus.CREATED)
  @UseGuards(StaffEmailWriteGuard)
  async createTemplate(
    @Req() req: StaffReq,
    @Body()
    body: {
      client_id: string;
      name: string;
      subject_template: string;
      html_body: string;
      text_body?: string;
    },
  ): Promise<EmailTemplateRow> {
    return this.email.createTemplate({
      clientId: body.client_id,
      name: body.name,
      subjectTemplate: body.subject_template,
      htmlBody: body.html_body,
      textBody: body.text_body,
      actor: actorFromReq(req),
    });
  }

  @Get('templates/:id')
  async getTemplate(@Param('id') id: string): Promise<EmailTemplateRow> {
    return this.email.getTemplate(id);
  }

  @Patch('templates/:id')
  @UseGuards(StaffEmailWriteGuard)
  async patchTemplate(
    @Req() req: StaffReq,
    @Param('id') id: string,
    @Body() body: Record<string, unknown>,
  ): Promise<EmailTemplateRow> {
    return this.email.updateTemplate(id, body, actorFromReq(req));
  }

  @Post('templates/:id/preflight')
  @HttpCode(HttpStatus.OK)
  async preflightTemplate(@Param('id') id: string): Promise<EmailPreflightResponse> {
    return this.email.preflightTemplate(id);
  }

  @Get('campaigns')
  async campaigns(
    @Query('client_id') clientId?: string,
    @Query('status') status?: string,
    @Query('limit') limit?: string,
    @Query('offset') offset?: string,
  ): Promise<EmailListResponse<EmailCampaignRow>> {
    return this.email.listCampaigns({
      clientId,
      status,
      limit: limit ? Number.parseInt(limit, 10) : undefined,
      offset: offset ? Number.parseInt(offset, 10) : undefined,
    });
  }

  @Post('campaigns')
  @HttpCode(HttpStatus.CREATED)
  @UseGuards(StaffEmailWriteGuard)
  async createCampaign(
    @Req() req: StaffReq,
    @Body()
    body: {
      client_id: string;
      name: string;
      template_id: string;
      segment_id?: string;
      campaign_type?: string;
    },
  ): Promise<EmailCampaignRow> {
    return this.email.createCampaign({
      clientId: body.client_id,
      name: body.name,
      templateId: body.template_id,
      segmentId: body.segment_id,
      campaignType: body.campaign_type,
      actor: actorFromReq(req),
    });
  }

  @Get('campaigns/:id')
  async getCampaign(@Param('id') id: string): Promise<EmailCampaignRow> {
    return this.email.getCampaign(id);
  }

  @Post('campaigns/:id/submit')
  @HttpCode(HttpStatus.OK)
  @UseGuards(StaffEmailWriteGuard)
  async submitCampaign(@Req() req: StaffReq, @Param('id') id: string): Promise<EmailCampaignRow> {
    return this.email.submitCampaign(id, actorFromReq(req));
  }

  @Post('campaigns/:id/approve')
  @HttpCode(HttpStatus.OK)
  @UseGuards(StaffEmailApproveGuard)
  async approveCampaign(
    @Req() req: StaffReq,
    @Param('id') id: string,
    @Body() body: { scheduled_at?: string; note?: string },
  ) {
    return this.email.approveCampaign(id, actorFromReq(req), {
      scheduledAt: body.scheduled_at,
      note: body.note,
    });
  }

  @Post('campaigns/:id/schedule')
  @HttpCode(HttpStatus.OK)
  @UseGuards(StaffEmailApproveGuard)
  async scheduleCampaign(
    @Req() req: StaffReq,
    @Param('id') id: string,
    @Body() body: { scheduled_at: string },
  ): Promise<EmailCampaignRow> {
    return this.email.scheduleCampaign(id, actorFromReq(req), body.scheduled_at);
  }

  @Post('campaigns/:id/preflight')
  @HttpCode(HttpStatus.OK)
  async preflightCampaign(@Param('id') id: string): Promise<EmailPreflightResponse> {
    return this.email.preflightCampaign(id);
  }

  @Get('journeys')
  async journeys(
    @Query('client_id') clientId?: string,
    @Query('status') status?: string,
    @Query('limit') limit?: string,
    @Query('offset') offset?: string,
  ): Promise<EmailListResponse<EmailJourneyRow>> {
    return this.email.listJourneys({
      clientId,
      status,
      limit: limit ? Number.parseInt(limit, 10) : undefined,
      offset: offset ? Number.parseInt(offset, 10) : undefined,
    });
  }

  @Post('journeys')
  @HttpCode(HttpStatus.CREATED)
  @UseGuards(StaffEmailWriteGuard)
  async createJourney(
    @Req() req: StaffReq,
    @Body()
    body: {
      client_id: string;
      name: string;
      trigger_type?: string;
      entry_segment_id?: string;
      graph_json?: Record<string, unknown>;
    },
  ): Promise<EmailJourneyRow> {
    return this.email.createJourney({
      clientId: body.client_id,
      name: body.name,
      triggerType: body.trigger_type,
      entrySegmentId: body.entry_segment_id,
      graphJson: body.graph_json,
      actor: actorFromReq(req),
    });
  }

  @Get('journeys/:id')
  async getJourney(@Param('id') id: string): Promise<EmailJourneyRow> {
    return this.email.getJourney(id);
  }

  @Patch('journeys/:id')
  @UseGuards(StaffEmailWriteGuard)
  async patchJourney(
    @Req() req: StaffReq,
    @Param('id') id: string,
    @Body() body: Record<string, unknown>,
  ): Promise<EmailJourneyRow> {
    return this.email.updateJourney(id, body, actorFromReq(req));
  }

  @Post('journeys/:id/activate')
  @HttpCode(HttpStatus.OK)
  @UseGuards(StaffEmailWriteGuard)
  async activateJourney(@Req() req: StaffReq, @Param('id') id: string): Promise<EmailJourneyRow> {
    return this.email.activateJourney(id, actorFromReq(req));
  }

  @Get('experiments')
  async experiments(
    @Query('client_id') clientId?: string,
    @Query('campaign_id') campaignId?: string,
    @Query('status') status?: string,
    @Query('limit') limit?: string,
    @Query('offset') offset?: string,
  ): Promise<EmailListResponse<EmailExperimentRow>> {
    return this.email.listExperiments({
      clientId,
      campaignId,
      status,
      limit: limit ? Number.parseInt(limit, 10) : undefined,
      offset: offset ? Number.parseInt(offset, 10) : undefined,
    });
  }

  @Post('experiments')
  @HttpCode(HttpStatus.CREATED)
  @UseGuards(StaffEmailWriteGuard)
  async createExperiment(
    @Req() req: StaffReq,
    @Body()
    body: {
      client_id: string;
      campaign_id: string;
      name: string;
      hypothesis?: string;
      experiment_type?: string;
      winner_metric?: string;
      min_sample?: number;
      variants: Array<{ variant_key: string; label: string; subject?: string; split_pct?: number }>;
    },
  ): Promise<EmailExperimentRow> {
    return this.email.createExperiment({
      clientId: body.client_id,
      campaignId: body.campaign_id,
      name: body.name,
      hypothesis: body.hypothesis,
      experimentType: body.experiment_type,
      winnerMetric: body.winner_metric,
      minSample: body.min_sample,
      variants: body.variants,
      actor: actorFromReq(req),
    });
  }

  @Get('experiments/:id')
  async getExperiment(@Param('id') id: string): Promise<EmailExperimentRow> {
    return this.email.getExperiment(id);
  }

  @Get('campaigns/:id/experiment')
  async getCampaignExperiment(@Param('id') id: string): Promise<EmailExperimentRow | null> {
    return this.email.getCampaignExperiment(id);
  }

  @Post('experiments/:id/start')
  @HttpCode(HttpStatus.OK)
  @UseGuards(StaffEmailWriteGuard)
  async startExperiment(@Req() req: StaffReq, @Param('id') id: string): Promise<EmailExperimentRow> {
    return this.email.startExperiment(id, actorFromReq(req));
  }

  @Post('experiments/:id/rollup')
  @HttpCode(HttpStatus.OK)
  @UseGuards(StaffEmailWriteGuard)
  async rollupExperiment(@Param('id') id: string): Promise<EmailExperimentRollupResult> {
    return this.email.rollupExperiment(id);
  }

  @Post('experiments/:id/declare-winner')
  @HttpCode(HttpStatus.OK)
  @UseGuards(StaffEmailWriteGuard)
  async declareExperimentWinner(
    @Req() req: StaffReq,
    @Param('id') id: string,
    @Body() body: { variant_key: string; rationale?: string },
  ): Promise<EmailExperimentRow> {
    return this.email.declareExperimentWinner(id, body.variant_key, actorFromReq(req), body.rationale);
  }

  @Get('deliverability/domains')
  async deliverabilityDomains(
    @Query('client_id') clientId?: string,
    @Query('limit') limit?: string,
    @Query('offset') offset?: string,
  ): Promise<EmailListResponse<EmailDeliverabilityDomainRow>> {
    return this.email.listDeliverabilityDomains({
      clientId,
      limit: limit ? Number.parseInt(limit, 10) : undefined,
      offset: offset ? Number.parseInt(offset, 10) : undefined,
    });
  }

  @Post('deliverability/domains')
  @HttpCode(HttpStatus.CREATED)
  @UseGuards(StaffEmailDeliverabilityGuard)
  async registerDomain(
    @Req() req: StaffReq,
    @Body() body: { client_id: string; domain: string },
  ): Promise<EmailDeliverabilityDomainRow> {
    return this.email.registerDomain({
      clientId: body.client_id,
      domain: body.domain,
      actor: actorFromReq(req),
    });
  }

  @Post('deliverability/domains/:id/verify')
  @HttpCode(HttpStatus.OK)
  @UseGuards(StaffEmailDeliverabilityGuard)
  async verifyDomain(
    @Req() req: StaffReq,
    @Param('id') id: string,
  ): Promise<EmailDeliverabilityDomainRow> {
    return this.email.verifyDomain(id, actorFromReq(req));
  }

  @Post('deliverability/domains/:id/pause')
  @HttpCode(HttpStatus.OK)
  @UseGuards(StaffEmailDeliverabilityGuard)
  async pauseDomain(
    @Req() req: StaffReq,
    @Param('id') id: string,
  ): Promise<EmailDeliverabilityDomainRow> {
    return this.email.pauseDomain(id, actorFromReq(req));
  }

  @Get('reports/summary')
  @UseGuards(StaffEmailReportsGuard)
  async reportsSummary(
    @Query('client_id') clientId?: string,
    @Query('days') days?: string,
  ): Promise<EmailReportsSummary> {
    const parsedDays = days ? Number.parseInt(days, 10) : undefined;
    return this.email.reportsSummary({
      clientId,
      days: Number.isFinite(parsedDays) ? parsedDays : undefined,
    });
  }

  @Get('reports/campaigns/:id')
  @UseGuards(StaffEmailReportsGuard)
  async campaignReport(@Param('id') id: string): Promise<EmailReportsCampaignStats> {
    return this.email.campaignReport(id);
  }

  @Get('reports/deliverability')
  @UseGuards(StaffEmailReportsGuard)
  async deliverabilityReport(
    @Query('client_id') clientId?: string,
    @Query('days') days?: string,
  ): Promise<EmailDeliverabilityReport> {
    const parsedDays = days ? Number.parseInt(days, 10) : undefined;
    return this.email.deliverabilityReport({
      clientId,
      days: Number.isFinite(parsedDays) ? parsedDays : undefined,
    });
  }

  @Get('reports/engagement')
  @UseGuards(StaffEmailReportsGuard)
  async engagementSeries(
    @Query('client_id') clientId?: string,
    @Query('days') days?: string,
  ) {
    const parsedDays = days ? Number.parseInt(days, 10) : undefined;
    return this.email.engagementSeries({
      clientId,
      days: Number.isFinite(parsedDays) ? parsedDays : undefined,
    });
  }

  @Post('reports/export-clickhouse')
  @HttpCode(HttpStatus.ACCEPTED)
  @UseGuards(StaffEmailReportsGuard)
  async exportClickhouse(
    @Query('fact_date') factDate?: string,
    @Query('client_id') clientId?: string,
  ): Promise<EmailClickhouseExportResult> {
    return this.email.exportClickhouse({
      factDate: factDate?.trim() || undefined,
      clientId: clientId?.trim() || undefined,
    });
  }

  @Get('reports/schedules')
  @UseGuards(StaffEmailReportsGuard)
  async listReportSchedules(
    @Query('client_id') clientId: string,
    @Query('limit') limit?: string,
    @Query('offset') offset?: string,
  ): Promise<EmailListResponse<EmailReportScheduleRow>> {
    return this.email.listReportSchedules({
      clientId,
      limit: limit ? Number.parseInt(limit, 10) : undefined,
      offset: offset ? Number.parseInt(offset, 10) : undefined,
    });
  }

  @Post('reports/schedules')
  @HttpCode(HttpStatus.CREATED)
  @UseGuards(StaffEmailReportsGuard)
  async createReportSchedule(
    @Req() req: StaffReq,
    @Body()
    body: {
      client_id: string;
      report_type?: string;
      cadence?: string;
      day_of_week?: number;
      day_of_month?: number;
      recipient_emails?: string[];
      cc_emails?: string[];
      bcc_emails?: string[];
    },
  ): Promise<EmailReportScheduleRow> {
    return this.email.createReportSchedule({
      clientId: body.client_id,
      reportType: body.report_type,
      cadence: body.cadence,
      dayOfWeek: body.day_of_week,
      dayOfMonth: body.day_of_month,
      recipientEmails: body.recipient_emails,
      ccEmails: body.cc_emails,
      bccEmails: body.bcc_emails,
      actor: actorFromReq(req),
    });
  }

  @Patch('reports/schedules/:id')
  @UseGuards(StaffEmailReportsGuard)
  async patchReportSchedule(
    @Req() req: StaffReq,
    @Param('id') id: string,
    @Body() body: Record<string, unknown>,
  ): Promise<EmailReportScheduleRow> {
    return this.email.updateReportSchedule(id, body, actorFromReq(req));
  }

  @Post('reports/schedules/:id/run')
  @HttpCode(HttpStatus.ACCEPTED)
  @UseGuards(StaffEmailReportsGuard)
  async runReportSchedule(@Param('id') id: string) {
    return this.email.runReportSchedule(id);
  }

  @Post('reports/schedules/run-due')
  @HttpCode(HttpStatus.ACCEPTED)
  @UseGuards(StaffEmailReportsGuard)
  async runDueReportSchedules(@Query('as_of') asOf?: string) {
    return this.email.runDueReportSchedules(asOf?.trim() || undefined);
  }

  @Post('reports/schedules/:id/delete')
  @HttpCode(HttpStatus.OK)
  @UseGuards(StaffEmailReportsGuard)
  async deleteReportSchedule(@Req() req: StaffReq, @Param('id') id: string) {
    return this.email.deleteReportSchedule(id, actorFromReq(req));
  }
}
