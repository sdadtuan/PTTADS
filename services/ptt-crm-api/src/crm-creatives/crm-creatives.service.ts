import { BadRequestException, Injectable, ServiceUnavailableException } from '@nestjs/common';
import { CreativesRepository } from '../creatives/creatives.repository';
import { CreativesService } from '../creatives/creatives.service';
import { LaunchQaLifecycleLookupService } from '../launch-qa/launch-qa-lifecycle-lookup.service';

const VALID_STATUS = new Set(['all', 'pending_client', 'approved', 'rejected', 'withdrawn']);

@Injectable()
export class CrmCreativesService {
  constructor(
    private readonly repo: CreativesRepository,
    private readonly creatives: CreativesService,
    private readonly lifecycleLookup: LaunchQaLifecycleLookupService,
  ) {}

  async stats() {
    await this.ensureReady();
    const stats = await this.repo.countByStatus();
    return {
      ok: true,
      stats: {
        ...stats,
        pending_creatives: stats.pending_client ?? 0,
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
    title?: string;
    description?: string;
    asset_url?: string;
    asset_type?: string;
    version?: number;
    resubmit?: boolean;
    submitted_by?: string;
  }) {
    await this.ensureReady();
    const clientId = body.client_id?.trim();
    const campaignId = body.external_campaign_id?.trim();
    const title = body.title?.trim();
    if (!clientId || !campaignId || !title) {
      throw new BadRequestException({ error: 'client_id, external_campaign_id, title required' });
    }

    let version = Math.max(1, Number(body.version) || 1);
    if (body.resubmit) {
      const maxV = await this.repo.maxVersionForCampaign(clientId, campaignId);
      version = maxV + 1;
    }

    return this.creatives.submit({
      client_id: clientId,
      title,
      description: body.description,
      external_campaign_id: campaignId,
      external_campaign_name: body.external_campaign_name,
      version,
      asset_url: body.asset_url,
      asset_type: body.asset_type,
      submitted_by: body.submitted_by,
    });
  }

  private async ensureReady(): Promise<void> {
    if (!(await this.repo.pgCreativesReady())) {
      throw new ServiceUnavailableException({ error: 'creatives_tables_not_ready' });
    }
  }
}
