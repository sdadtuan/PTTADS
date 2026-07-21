import { BadRequestException, Injectable, NotFoundException, ServiceUnavailableException } from '@nestjs/common';
import { AgencyRepository } from './agency.repository';
import {
  AgencyClientsListResponse,
  AgencyClientDetail,
  AgencyStatsResponse,
  FacebookHubResponse,
  HubCampaignMapsResponse,
  HubCampaignGlobalRow,
  JobsListResponse,
  NotificationsListResponse,
  OnboardingResponse,
  KpiDefinitionRow,
  AddChannelAccountBody,
  UpdateClientBody,
  PatchHubCampaignMapBody,
} from './agency.types';

const META_CAMPAIGN_ID_RE = /^[0-9]{5,20}$/;
const VALID_CHANNELS = new Set(['meta', 'zalo', 'google', 'email']);

function strictOnboardingEnabled(): boolean {
  const raw = (process.env.PTT_CLIENT_STRICT_ONBOARDING ?? '1').trim().toLowerCase();
  return raw === '1' || raw === 'true' || raw === 'yes';
}

function normalizeMetaCampaignId(raw: string): string {
  return raw.replace(/\D/g, '').trim();
}

@Injectable()
export class AgencyService {
  constructor(private readonly repo: AgencyRepository) {}

  private async ensurePg(): Promise<void> {
    if (!(await this.repo.pgReady())) {
      throw new ServiceUnavailableException({
        error: 'pg_not_ready',
        hint: 'Kiểm tra DATABASE_URL và DDL agency',
      });
    }
  }

  async stats(): Promise<AgencyStatsResponse> {
    const pgReady = await this.repo.pgReady();
    if (!pgReady) {
      return { pg_ready: false, clients: {}, jobs: {} };
    }
    const [clients, jobs] = await Promise.all([this.repo.clientCounts(), this.repo.jobStats()]);
    return { pg_ready: true, clients, jobs };
  }

  async listClients(query: {
    status?: string;
    q?: string;
    owner_am_id?: string;
    industry?: string;
    limit?: number;
    offset?: number;
  }): Promise<AgencyClientsListResponse> {
    await this.ensurePg();
    const clients = await this.repo.listClients({
      status: query.status?.trim() || undefined,
      q: query.q?.trim() || undefined,
      ownerAmId: query.owner_am_id?.trim() || undefined,
      industrySlug: query.industry?.trim() || undefined,
      limit: Math.min(Math.max(query.limit ?? 100, 1), 200),
      offset: Math.max(query.offset ?? 0, 0),
    });
    return { clients };
  }

  async getClient(clientId: string): Promise<AgencyClientDetail> {
    await this.ensurePg();
    const client = await this.repo.fetchClient(clientId);
    if (!client) {
      throw new NotFoundException({ error: 'Not found' });
    }
    return client;
  }

  async createClient(body: {
    code: string;
    name: string;
    industry_slug?: string;
    owner_am_id?: string;
    notes?: string;
  }): Promise<AgencyClientDetail> {
    await this.ensurePg();
    const code = body.code?.trim() ?? '';
    const name = body.name?.trim() ?? '';
    if (!/^[A-Za-z0-9][A-Za-z0-9_-]{1,30}$/.test(code)) {
      throw new BadRequestException({ error: 'invalid_code' });
    }
    if (!name) {
      throw new BadRequestException({ error: 'name_required' });
    }
    const row = await this.repo.createClient({
      code,
      name,
      industry_slug: body.industry_slug,
      owner_am_id: body.owner_am_id,
      notes: body.notes,
    });
    return { ...row, channel_accounts: [] };
  }

  async listJobs(query: {
    status?: string;
    limit?: number;
    offset?: number;
  }): Promise<JobsListResponse> {
    await this.ensurePg();
    const [stats, jobs] = await Promise.all([
      this.repo.jobStats(),
      this.repo.listJobs({
        status: query.status?.trim() || undefined,
        limit: Math.min(Math.max(query.limit ?? 50, 1), 200),
        offset: Math.max(query.offset ?? 0, 0),
      }),
    ]);
    return { stats, jobs };
  }

  async listNotifications(query: {
    recipient_id?: string;
    unread?: string;
    limit?: number;
  }): Promise<NotificationsListResponse> {
    await this.ensurePg();
    const recipientId = (query.recipient_id ?? 'ops').trim() || 'ops';
    const { rows, unread } = await this.repo.listNotifications({
      recipientId,
      unreadOnly: query.unread === '1',
      limit: Math.min(Math.max(query.limit ?? 50, 1), 200),
    });
    return { notifications: rows, unread };
  }

  async hubCampaignMaps(
    clientId: string,
    query: { channel?: string; include_inactive?: string; limit?: number },
  ): Promise<HubCampaignMapsResponse> {
    await this.ensurePg();
    const client = await this.repo.fetchClient(clientId);
    if (!client) {
      throw new NotFoundException({ error: 'Not found' });
    }
    const activeOnly = query.include_inactive?.trim() !== '1';
    const maps = await this.repo.listHubCampaignMaps(clientId, {
      channel: query.channel?.trim() || undefined,
      activeOnly,
      limit: Math.min(Math.max(query.limit ?? 100, 1), 200),
    });
    return { ok: true, client_id: clientId, maps, count: maps.length };
  }

  async hubCampaignMapsGlobal(query: {
    client_id?: string;
    campaign_id?: string;
    limit?: number;
  }): Promise<{ ok: boolean; maps: HubCampaignGlobalRow[]; count: number }> {
    await this.ensurePg();
    const campaignId =
      query.campaign_id?.trim() ? Math.trunc(Number(query.campaign_id)) : undefined;
    const maps = await this.repo.listHubCampaignMapsGlobal({
      clientId: query.client_id?.trim() || undefined,
      campaignId: Number.isFinite(campaignId) ? campaignId : undefined,
      limit: Math.min(Math.max(query.limit ?? 200, 1), 500),
    });
    return { ok: true, maps, count: maps.length };
  }

  async facebookHub(query: {
    days?: string;
    to?: string;
    date_to?: string;
    status?: string;
  }): Promise<FacebookHubResponse> {
    await this.ensurePg();
    const windowDays = Math.min(Math.max(Number(query.days ?? 7) || 7, 1), 90);
    const dateTo = (query.to ?? query.date_to ?? '').trim() || undefined;
    const { clients, summary, dateFrom, dateTo: dateEnd } = await this.repo.facebookHubSummary({
      windowDays,
      dateTo,
      status: query.status?.trim() || undefined,
    });

    const alerts: string[] = [];
    if (Number(summary.unmapped_campaigns ?? 0) > 0) {
      alerts.push(`${summary.unmapped_campaigns} campaign chưa map Hub`);
    }
    if (Number(summary.over_target_rows ?? 0) > 0) {
      alerts.push(`${summary.over_target_rows} dòng CPL vượt target`);
    }

    return { ok: true, pg_ready: true, date_from: dateFrom, date_to: dateEnd, window_days: windowDays, summary, clients, alerts };
  }

  private onboardingProgressFromItems(
    items: Array<{ completed: boolean }>,
  ): { total: number; completed: number; percent: number } {
    const total = items.length;
    const completed = items.filter((i) => i.completed).length;
    const percent = total ? Math.round((completed / total) * 100) : 0;
    return { total, completed, percent };
  }

  async updateClient(clientId: string, body: UpdateClientBody): Promise<AgencyClientDetail> {
    await this.ensurePg();
    const row = await this.repo.updateClient(clientId, body);
    if (!row) {
      throw new NotFoundException({ error: 'Not found' });
    }
    return this.getClient(clientId);
  }

  async getOnboarding(clientId: string): Promise<OnboardingResponse> {
    await this.ensurePg();
    const client = await this.repo.fetchClient(clientId);
    if (!client) {
      throw new NotFoundException({ error: 'Not found' });
    }
    const items = await this.repo.listOnboardingItems(clientId);
    return { items, progress: this.onboardingProgressFromItems(items) };
  }

  async patchOnboardingItem(
    clientId: string,
    itemKey: string,
    body: { completed: boolean; completed_by?: string; note?: string },
  ): Promise<OnboardingResponse> {
    await this.ensurePg();
    const client = await this.repo.fetchClient(clientId);
    if (!client) {
      throw new NotFoundException({ error: 'Not found' });
    }
    const ok = await this.repo.setOnboardingItem(clientId, itemKey, body);
    if (!ok) {
      throw new NotFoundException({ error: 'item_not_found' });
    }
    return this.getOnboarding(clientId);
  }

  async activateClient(clientId: string, force = false): Promise<AgencyClientDetail> {
    await this.ensurePg();
    const client = await this.repo.fetchClient(clientId);
    if (!client) {
      throw new NotFoundException({ error: 'Not found' });
    }
    const onboarding = await this.getOnboarding(clientId);
    if (strictOnboardingEnabled() && !force && onboarding.progress.percent < 100) {
      throw new BadRequestException({
        error: 'checklist_incomplete',
        progress: onboarding.progress,
      });
    }
    const row = await this.repo.updateClient(clientId, { status: 'active' });
    if (!row) {
      throw new NotFoundException({ error: 'Not found' });
    }
    return this.getClient(clientId);
  }

  async addChannelAccount(clientId: string, body: AddChannelAccountBody): Promise<AgencyClientDetail> {
    await this.ensurePg();
    const client = await this.repo.fetchClient(clientId);
    if (!client) {
      throw new NotFoundException({ error: 'Not found' });
    }
    const channel = body.channel?.trim().toLowerCase() ?? '';
    if (!VALID_CHANNELS.has(channel)) {
      throw new BadRequestException({ error: 'invalid_channel' });
    }
    const ext = body.external_account_id?.trim() ?? '';
    if (!ext) {
      throw new BadRequestException({ error: 'external_account_id_required' });
    }
    await this.repo.addChannelAccount(clientId, {
      channel,
      external_account_id: ext,
      display_name: body.display_name,
    });
    return this.getClient(clientId);
  }

  async replayJob(jobId: string): Promise<{ id: string; status: string; replayed: boolean }> {
    await this.ensurePg();
    const out = await this.repo.replayJob(jobId);
    if (!out) {
      throw new BadRequestException({ error: 'job_not_replayable', hint: 'Chỉ replay job status=dead' });
    }
    return out;
  }

  async markNotificationRead(notificationId: string, recipientId: string): Promise<{ ok: boolean }> {
    await this.ensurePg();
    const ok = await this.repo.markNotificationRead(notificationId, recipientId);
    if (!ok) {
      throw new NotFoundException({ error: 'not_found' });
    }
    return { ok: true };
  }

  async markAllNotificationsRead(recipientId: string): Promise<{ marked: number }> {
    await this.ensurePg();
    const marked = await this.repo.markAllNotificationsRead(recipientId);
    return { marked };
  }

  async listKpiDefinitions(): Promise<{ definitions: KpiDefinitionRow[] }> {
    await this.ensurePg();
    const definitions = await this.repo.listKpiDefinitions();
    return { definitions };
  }

  async patchHubCampaignMap(body: PatchHubCampaignMapBody): Promise<{ ok: boolean; map_id: string; external_campaign_id: string }> {
    await this.ensurePg();
    const clientId = body.client_id?.trim() ?? '';
    const hubCampaignId = Math.trunc(Number(body.hub_campaign_id));
    const externalId = normalizeMetaCampaignId(body.external_campaign_id ?? '');
    if (!clientId || !Number.isFinite(hubCampaignId) || hubCampaignId <= 0) {
      throw new BadRequestException({ error: 'invalid_payload' });
    }
    if (!META_CAMPAIGN_ID_RE.test(externalId)) {
      throw new BadRequestException({ error: 'invalid_meta_campaign_id' });
    }
    const client = await this.repo.fetchClient(clientId);
    if (!client) {
      throw new NotFoundException({ error: 'client_not_found' });
    }
    const out = await this.repo.updateHubCampaignMap({
      clientId,
      hubCampaignId,
      externalCampaignId: externalId,
    });
    if (!out) {
      throw new NotFoundException({ error: 'map_not_found' });
    }
    return { ok: true, ...out };
  }
}
