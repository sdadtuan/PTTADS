import { Injectable, NotFoundException } from '@nestjs/common';
import { EmailMarketingCampaignRepository } from './email-marketing-campaign.repository';
import { EmailMarketingEnterpriseRepository } from './email-marketing-enterprise.repository';
import { EmailMarketingExperimentRepository } from './email-marketing-experiment.repository';
import { EmailMarketingOpsRepository } from './email-marketing-ops.repository';
import { EmailMarketingRepository } from './email-marketing.repository';
import { EmailJobQueueService } from './email-job-queue.service';
import { EmailSendOrchestratorService } from './email-send-orchestrator.service';
import { TemporalEmailJourneyService } from './temporal-email-journey.service';
import {
  EmailGovernanceResponse,
  EmailHubResponse,
  EmailImportResult,
  EmailListResponse,
  EmailPreferencePublicView,
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
  EmailEngagementSeriesPoint,
  EmailReportScheduleRow,
  EmailClickhouseExportResult,
} from './email-marketing.types';

@Injectable()
export class EmailMarketingService {
  constructor(
    private readonly repo: EmailMarketingRepository,
    private readonly ops: EmailMarketingOpsRepository,
    private readonly campaign: EmailMarketingCampaignRepository,
    private readonly enterprise: EmailMarketingEnterpriseRepository,
    private readonly experiments: EmailMarketingExperimentRepository,
    private readonly sendOrchestrator: EmailSendOrchestratorService,
    private readonly jobQueue: EmailJobQueueService,
    private readonly temporalJourney: TemporalEmailJourneyService,
  ) {}

  async hub(params: {
    clientId?: string;
    days?: number;
    domain?: string;
  }): Promise<EmailHubResponse> {
    const days = params.days ?? 28;
    const safeDays = Number.isFinite(days) && days > 0 ? Math.min(days, 365) : 28;
    return this.repo.hubSummary({
      clientId: params.clientId?.trim() || undefined,
      days: safeDays,
      domain: params.domain?.trim() || undefined,
    });
  }

  async governance(params: { scope?: string }): Promise<EmailGovernanceResponse> {
    return this.repo.governance({
      scope: params.scope?.trim() || undefined,
    });
  }

  async listClients(params: {
    q?: string;
    has_workspace?: boolean;
    limit?: number;
    offset?: number;
  }): Promise<EmailListResponse<EmailClientListRow>> {
    const page = EmailMarketingOpsRepository.pagination(params.limit, params.offset);
    return this.ops.listEmailClients({
      q: params.q,
      hasWorkspace: params.has_workspace,
      ...page,
    });
  }

  async listWorkspaces(params: {
    clientId?: string;
    limit?: number;
    offset?: number;
  }): Promise<EmailListResponse<EmailWorkspaceRow>> {
    const page = EmailMarketingOpsRepository.pagination(params.limit, params.offset);
    return this.ops.listWorkspaces({
      clientId: params.clientId?.trim() || undefined,
      ...page,
    });
  }

  async createWorkspace(params: {
    clientId: string;
    name?: string;
    defaultFromName?: string;
    defaultFromEmail?: string;
    defaultReplyTo?: string;
    espProvider?: string;
    dailySendCap?: number;
    frequencyCap7d?: number;
    timezone?: string;
    actor: string;
  }): Promise<EmailWorkspaceRow> {
    return this.ops.createWorkspace({
      ...params,
      name: params.name?.trim() || '',
    });
  }

  async updateWorkspace(params: {
    workspaceId: string;
    patch: Record<string, unknown>;
    actor: string;
  }): Promise<EmailWorkspaceRow> {
    return this.ops.updateWorkspace({
      workspaceId: params.workspaceId,
      patch: params.patch,
      actor: params.actor,
    });
  }

  async listContacts(params: {
    clientId?: string;
    q?: string;
    limit?: number;
    offset?: number;
  }): Promise<EmailListResponse<EmailContactRow>> {
    const page = EmailMarketingOpsRepository.pagination(params.limit, params.offset);
    return this.ops.listContacts({
      clientId: params.clientId?.trim() || undefined,
      q: params.q,
      ...page,
    });
  }

  async importContacts(params: {
    clientId: string;
    rows: Array<{ email: string; first_name?: string; last_name?: string; lifecycle_stage?: string }>;
    actor: string;
  }): Promise<EmailImportResult> {
    return this.ops.importContacts(params);
  }

  async listConsent(params: {
    clientId?: string;
    contactId?: string;
    topic?: string;
    limit?: number;
    offset?: number;
  }): Promise<EmailListResponse<EmailConsentRow>> {
    const page = EmailMarketingOpsRepository.pagination(params.limit, params.offset);
    return this.ops.listConsent({
      clientId: params.clientId?.trim() || undefined,
      contactId: params.contactId?.trim() || undefined,
      topic: params.topic?.trim() || undefined,
      ...page,
    });
  }

  async recordConsent(params: {
    clientId: string;
    contactId?: string;
    email?: string;
    topic?: string;
    status: string;
    source?: string;
    consentVersion?: string;
    recordedBy: string;
  }): Promise<{ ok: boolean; consent_id: string; contact_id: string; preference_token?: string }> {
    return this.ops.recordConsent({
      clientId: params.clientId,
      contactId: params.contactId,
      email: params.email,
      topic: params.topic?.trim() || 'marketing',
      status: params.status,
      source: params.source?.trim() || 'manual',
      consentVersion: params.consentVersion,
      recordedBy: params.recordedBy,
    });
  }

  async listSuppression(params: {
    clientId?: string;
    q?: string;
    limit?: number;
    offset?: number;
  }): Promise<EmailListResponse<EmailSuppressionRow>> {
    const page = EmailMarketingOpsRepository.pagination(params.limit, params.offset);
    return this.ops.listSuppression({
      clientId: params.clientId?.trim() || undefined,
      q: params.q,
      ...page,
    });
  }

  async addSuppression(params: {
    clientId?: string;
    email: string;
    reason: string;
    scope?: string;
    createdBy: string;
  }): Promise<{ ok: boolean; id: string }> {
    return this.ops.addSuppression(params);
  }

  async capture(params: {
    client_id: string;
    email: string;
    first_name?: string;
    source?: string;
  }): Promise<{ ok: boolean; contact_id: string; confirm_token?: string }> {
    return this.ops.captureLead({
      clientId: params.client_id,
      email: params.email,
      firstName: params.first_name,
      source: params.source,
    });
  }

  async publicPreferences(token: string): Promise<EmailPreferencePublicView> {
    return this.ops.getPublicPreferences(token);
  }

  async updatePublicPreferences(
    token: string,
    body: { marketing?: boolean; topics?: Array<{ topic: string; opted_in: boolean }> },
  ): Promise<{ ok: boolean }> {
    return this.ops.updatePublicPreferences(token, body);
  }

  async publicUnsubscribe(token: string): Promise<{ ok: boolean; email: string }> {
    return this.ops.publicUnsubscribe(token);
  }

  async publicConfirm(token: string): Promise<{ ok: boolean; email: string }> {
    return this.ops.publicConfirm(token);
  }

  async listSegments(params: {
    clientId?: string;
    limit?: number;
    offset?: number;
  }): Promise<EmailListResponse<EmailSegmentRow>> {
    return this.campaign.listSegments({
      clientId: params.clientId?.trim() || undefined,
      ...EmailMarketingCampaignRepository.pagination(params.limit, params.offset),
    });
  }

  async createSegment(params: {
    clientId: string;
    name: string;
    segmentType?: string;
    definitionJson?: Record<string, unknown>;
    actor: string;
  }): Promise<EmailSegmentRow> {
    return this.campaign.createSegment(params);
  }

  async getSegment(id: string): Promise<EmailSegmentRow> {
    const row = await this.campaign.getSegment(id);
    if (!row) throw new NotFoundException({ error: 'segment_not_found' });
    return row;
  }

  async updateSegment(params: {
    id: string;
    name?: string;
    segmentType?: string;
    definitionJson?: Record<string, unknown>;
    actor: string;
  }): Promise<EmailSegmentRow> {
    return this.campaign.updateSegment(params);
  }

  async computeSegment(id: string, actor: string): Promise<EmailSegmentComputeResult> {
    return this.campaign.computeSegment(id, actor);
  }

  async listTemplates(params: {
    clientId?: string;
    limit?: number;
    offset?: number;
  }): Promise<EmailListResponse<EmailTemplateRow>> {
    return this.campaign.listTemplates({
      clientId: params.clientId?.trim() || undefined,
      ...EmailMarketingCampaignRepository.pagination(params.limit, params.offset),
    });
  }

  async createTemplate(params: {
    clientId: string;
    name: string;
    subjectTemplate: string;
    htmlBody: string;
    textBody?: string;
    actor: string;
  }): Promise<EmailTemplateRow> {
    return this.campaign.createTemplate(params);
  }

  async getTemplate(id: string): Promise<EmailTemplateRow> {
    const row = await this.campaign.getTemplate(id);
    if (!row) throw new NotFoundException({ error: 'template_not_found' });
    return row;
  }

  async updateTemplate(
    id: string,
    patch: {
      name?: string;
      subject_template?: string;
      html_body?: string;
      text_body?: string;
      status?: string;
    },
    actor: string,
  ): Promise<EmailTemplateRow> {
    return this.campaign.updateTemplate(id, patch, actor);
  }

  async preflightTemplate(id: string): Promise<EmailPreflightResponse> {
    return this.campaign.preflightTemplate(id);
  }

  async listCampaigns(params: {
    clientId?: string;
    status?: string;
    limit?: number;
    offset?: number;
  }): Promise<EmailListResponse<EmailCampaignRow>> {
    return this.campaign.listCampaigns({
      clientId: params.clientId?.trim() || undefined,
      status: params.status?.trim() || undefined,
      ...EmailMarketingCampaignRepository.pagination(params.limit, params.offset),
    });
  }

  async createCampaign(params: {
    clientId: string;
    name: string;
    templateId: string;
    segmentId?: string;
    campaignType?: string;
    actor: string;
  }): Promise<EmailCampaignRow> {
    return this.campaign.createCampaign(params);
  }

  async getCampaign(id: string): Promise<EmailCampaignRow> {
    const row = await this.campaign.getCampaign(id);
    if (!row) throw new NotFoundException({ error: 'campaign_not_found' });
    return row;
  }

  async submitCampaign(id: string, actor: string): Promise<EmailCampaignRow> {
    const row = await this.campaign.submitCampaign(id, actor);
    await this.sendOrchestrator.onCampaignSubmitted({
      campaignId: row.id,
      clientId: row.client_id,
      campaignName: row.name,
      submittedBy: actor,
    });
    return row;
  }

  async approveCampaign(
    id: string,
    actor: string,
    options?: { scheduledAt?: string | null; note?: string },
  ): Promise<EmailCampaignRow & { prepare_job_id?: string | null }> {
    const row = await this.campaign.approveCampaign(id, actor, {
      scheduledAt: options?.scheduledAt,
    });
    const out = await this.sendOrchestrator.onCampaignApproved({
      campaignId: row.id,
      clientId: row.client_id,
      reviewedBy: actor,
      note: options?.note,
      scheduledAt: row.scheduled_at,
    });
    return { ...row, prepare_job_id: out.prepare_job_id };
  }

  async scheduleCampaign(
    id: string,
    actor: string,
    scheduledAt: string,
  ): Promise<EmailCampaignRow> {
    return this.campaign.scheduleCampaign(id, actor, scheduledAt);
  }

  async preflightCampaign(id: string): Promise<EmailPreflightResponse> {
    return this.campaign.preflightCampaign(id);
  }

  async listJourneys(params: {
    clientId?: string;
    status?: string;
    limit?: number;
    offset?: number;
  }): Promise<EmailListResponse<EmailJourneyRow>> {
    return this.enterprise.listJourneys({
      clientId: params.clientId?.trim() || undefined,
      status: params.status?.trim() || undefined,
      ...EmailMarketingEnterpriseRepository.pagination(params.limit, params.offset),
    });
  }

  async getJourney(id: string): Promise<EmailJourneyRow> {
    const row = await this.enterprise.getJourney(id);
    if (!row) throw new NotFoundException({ error: 'journey_not_found' });
    return row;
  }

  async createJourney(params: {
    clientId: string;
    name: string;
    triggerType?: string;
    entrySegmentId?: string;
    graphJson?: Record<string, unknown>;
    actor: string;
  }): Promise<EmailJourneyRow> {
    return this.enterprise.createJourney(params);
  }

  async updateJourney(
    id: string,
    patch: {
      name?: string;
      graph_json?: Record<string, unknown>;
      entry_segment_id?: string | null;
      status?: string;
    },
    actor: string,
  ): Promise<EmailJourneyRow> {
    return this.enterprise.updateJourney(id, patch, actor);
  }

  async activateJourney(id: string, actor: string): Promise<EmailJourneyRow> {
    const row = await this.enterprise.activateJourney(id, actor);
    await this.temporalJourney.start({
      journeyId: row.id,
      clientId: row.client_id,
      journeyName: row.name,
      activatedBy: actor,
    });
    return row;
  }

  async listExperiments(params: {
    clientId?: string;
    campaignId?: string;
    status?: string;
    limit?: number;
    offset?: number;
  }): Promise<EmailListResponse<EmailExperimentRow>> {
    return this.experiments.listExperiments({
      clientId: params.clientId?.trim() || undefined,
      campaignId: params.campaignId?.trim() || undefined,
      status: params.status?.trim() || undefined,
      ...EmailMarketingExperimentRepository.pagination(params.limit, params.offset),
    });
  }

  async getExperiment(id: string): Promise<EmailExperimentRow> {
    const row = await this.experiments.getExperiment(id);
    if (!row) throw new NotFoundException({ error: 'experiment_not_found' });
    return row;
  }

  async getCampaignExperiment(campaignId: string): Promise<EmailExperimentRow | null> {
    return this.experiments.getRunningExperimentForCampaign(campaignId);
  }

  async createExperiment(params: {
    clientId: string;
    campaignId: string;
    name: string;
    hypothesis?: string;
    experimentType?: string;
    winnerMetric?: string;
    minSample?: number;
    variants: Array<{ variant_key: string; label: string; subject?: string; split_pct?: number }>;
    actor: string;
  }): Promise<EmailExperimentRow> {
    return this.experiments.createExperiment(params);
  }

  async startExperiment(id: string, actor: string): Promise<EmailExperimentRow> {
    return this.experiments.startExperiment(id, actor);
  }

  async declareExperimentWinner(
    id: string,
    variantKey: string,
    actor: string,
    rationale?: string,
  ): Promise<EmailExperimentRow> {
    return this.experiments.declareWinner(id, variantKey, actor, rationale);
  }

  async rollupExperiment(id: string): Promise<EmailExperimentRollupResult> {
    const row = await this.getExperiment(id);
    const queued = await this.jobQueue.enqueueExperimentRollup(id, row.client_id);
    return {
      ok: true,
      experiment_id: id,
      variants: [],
      winner_metric: String(row.config_json?.winner_metric ?? 'open_rate'),
      winner_variant_key: row.winner_variant_key,
      min_sample: Number(row.config_json?.min_sample ?? 100),
      job_id: queued.job_id,
    };
  }

  async listDeliverabilityDomains(params: {
    clientId?: string;
    limit?: number;
    offset?: number;
  }): Promise<EmailListResponse<EmailDeliverabilityDomainRow>> {
    return this.enterprise.listDomains({
      clientId: params.clientId?.trim() || undefined,
      ...EmailMarketingEnterpriseRepository.pagination(params.limit, params.offset),
    });
  }

  async registerDomain(params: {
    clientId: string;
    domain: string;
    actor: string;
  }): Promise<EmailDeliverabilityDomainRow> {
    return this.enterprise.registerDomain(params);
  }

  async verifyDomain(id: string, actor: string): Promise<EmailDeliverabilityDomainRow> {
    const updated = await this.enterprise.verifyDomain(id, actor);
    await this.jobQueue.enqueueDnsVerify(id, updated.client_id, actor);
    return updated;
  }

  async pauseDomain(id: string, actor: string): Promise<EmailDeliverabilityDomainRow> {
    return this.enterprise.pauseDomain(id, actor);
  }

  async reportsSummary(params: { clientId?: string; days?: number }): Promise<EmailReportsSummary> {
    const days = params.days ?? 28;
    const safeDays = Number.isFinite(days) && days > 0 ? Math.min(days, 365) : 28;
    return this.enterprise.reportsSummary({
      clientId: params.clientId?.trim() || undefined,
      days: safeDays,
    });
  }

  async campaignReport(campaignId: string): Promise<EmailReportsCampaignStats> {
    return this.enterprise.campaignReport(campaignId);
  }

  async deliverabilityReport(params: {
    clientId?: string;
    days?: number;
  }): Promise<EmailDeliverabilityReport> {
    const days = params.days ?? 30;
    const safeDays = Number.isFinite(days) && days > 0 ? Math.min(days, 365) : 30;
    return this.enterprise.deliverabilityReport({
      clientId: params.clientId?.trim() || undefined,
      days: safeDays,
    });
  }

  async engagementSeries(params: {
    clientId?: string;
    days?: number;
  }): Promise<{ ok: boolean; points: EmailEngagementSeriesPoint[] }> {
    const days = params.days ?? 28;
    const safeDays = Number.isFinite(days) && days > 0 ? Math.min(days, 365) : 28;
    return this.enterprise.engagementSeries({
      clientId: params.clientId?.trim() || undefined,
      days: safeDays,
    });
  }

  async exportClickhouse(params?: {
    factDate?: string;
    clientId?: string;
  }): Promise<EmailClickhouseExportResult> {
    const out = await this.jobQueue.enqueueClickhouseExport({
      factDate: params?.factDate,
      clientId: params?.clientId?.trim() || undefined,
    });
    return { ok: true, job_id: out.job_id, mode: out.mode };
  }

  async listReportSchedules(params: {
    clientId: string;
    limit?: number;
    offset?: number;
  }): Promise<EmailListResponse<EmailReportScheduleRow>> {
    return this.enterprise.listReportSchedules({
      clientId: params.clientId.trim(),
      limit: params.limit,
      offset: params.offset,
    });
  }

  async createReportSchedule(params: {
    clientId: string;
    reportType?: string;
    cadence?: string;
    dayOfWeek?: number;
    dayOfMonth?: number;
    recipientEmails?: string[];
    ccEmails?: string[];
    bccEmails?: string[];
    actor: string;
  }): Promise<EmailReportScheduleRow> {
    return this.enterprise.createReportSchedule(params);
  }

  async updateReportSchedule(
    id: string,
    patch: Record<string, unknown>,
    actor: string,
  ): Promise<EmailReportScheduleRow> {
    return this.enterprise.updateReportSchedule(id, patch, actor);
  }

  async deleteReportSchedule(id: string, actor: string): Promise<{ ok: boolean }> {
    return this.enterprise.deleteReportSchedule(id, actor);
  }

  async runReportSchedule(id: string): Promise<{ ok: boolean; job_id: string | null }> {
    const schedule = await this.enterprise.getReportSchedule(id);
    const job = await this.jobQueue.enqueueReportScheduleRun(id, schedule.client_id);
    return { ok: true, job_id: job.job_id };
  }

  async runDueReportSchedules(asOf?: string): Promise<{ ok: boolean; job_id: string | null }> {
    const job = await this.jobQueue.enqueueDueReportSchedules(asOf);
    return { ok: true, job_id: job.job_id };
  }
}
