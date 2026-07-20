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
} from './agency.types';

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

    return {
      ok: true,
      pg_ready: true,
      date_from: dateFrom,
      date_to: dateEnd,
      window_days: windowDays,
      summary,
      clients,
      alerts,
    };
  }
}
