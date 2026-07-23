import { BadRequestException, Injectable, ServiceUnavailableException } from '@nestjs/common';
import { CampaignWritesService } from '../campaign-writes/campaign-writes.service';
import { CampaignWritesRepository } from '../campaign-writes/campaign-writes.repository';
import { checkCampaignWritePilot } from '../campaign-writes/meta-campaign-write-pilot.util';
import { LaunchQaLifecycleLookupService } from '../launch-qa/launch-qa-lifecycle-lookup.service';

const VALID_STATUS = new Set([
  'all',
  'pending_approval',
  'approved',
  'rejected',
  'executed',
  'execution_failed',
  'withdrawn',
]);

@Injectable()
export class CrmCampaignWritesService {
  constructor(
    private readonly repo: CampaignWritesRepository,
    private readonly writes: CampaignWritesService,
    private readonly lifecycleLookup: LaunchQaLifecycleLookupService,
  ) {}

  async stats() {
    await this.ensureReady();
    const stats = await this.repo.countByStatus();
    return {
      ok: true,
      stats: {
        ...stats,
        pending_campaign_writes: stats.pending_approval ?? 0,
      },
    };
  }

  async list(input: { status?: string; clientId?: string; externalCampaignId?: string; limit?: number }) {
    await this.ensureReady();
    const status = VALID_STATUS.has(String(input.status ?? 'all').trim())
      ? String(input.status ?? 'all').trim()
      : 'all';
    const rows = await this.repo.listForStaff({
      status: status === 'all' ? undefined : status,
      clientId: input.clientId,
      externalCampaignId: input.externalCampaignId,
      limit: input.limit,
    });
    const index = this.lifecycleLookup.buildLifecycleIndex();
    return {
      ok: true,
      status,
      count: rows.length,
      rows: rows.map((row) => ({
        ...row,
        lifecycle_id: this.lifecycleLookup.resolveLifecycleId(
          index,
          row.client_id,
          row.external_campaign_id ?? '',
        ),
      })),
    };
  }

  async submit(body: {
    client_id?: string;
    external_campaign_id?: string;
    external_campaign_name?: string;
    daily_budget_vnd?: number;
    change_type?: string;
    submitted_by?: string;
  }) {
    await this.ensureReady();
    const clientId = body.client_id?.trim();
    const campaignId = body.external_campaign_id?.trim();
    const budget = Number(body.daily_budget_vnd);
    if (!clientId || !campaignId || !Number.isFinite(budget) || budget < 0) {
      throw new BadRequestException({
        error: 'client_id, external_campaign_id, daily_budget_vnd required',
      });
    }
    const pilot = checkCampaignWritePilot(clientId, campaignId);
    const out = await this.writes.submit({
      client_id: clientId,
      external_campaign_id: campaignId,
      external_campaign_name: body.external_campaign_name,
      change_type: (body.change_type as 'daily_budget') ?? 'daily_budget',
      new_value: { daily_budget_vnd: Math.round(budget) },
      submitted_by: body.submitted_by,
    });
    return {
      ...out,
      pilot_check: pilot,
    };
  }

  async approve(id: string, body: { approved_by?: string; note?: string }) {
    await this.ensureReady();
    return this.writes.approve(id, body);
  }

  async reject(id: string, body: { approved_by?: string; note?: string }) {
    await this.ensureReady();
    return this.writes.reject(id, body);
  }

  private async ensureReady(): Promise<void> {
    if (!(await this.repo.tableReady())) {
      throw new ServiceUnavailableException({ error: 'campaign_write_table_not_ready' });
    }
  }
}
