import {
  BadRequestException,
  Injectable,
  NotFoundException,
  ServiceUnavailableException,
} from '@nestjs/common';
import { CampaignWritesService } from '../campaign-writes/campaign-writes.service';
import { CampaignWritesRepository } from '../campaign-writes/campaign-writes.repository';
import { checkZaloCampaignWritePilot } from '../campaign-writes/zalo-campaign-write-pilot.util';
import { ZaloAdsOpsRepository } from './zalo-ads-ops.repository';
import type {
  ZaloAdsOpsLaunchBody,
  ZaloAdsOpsStatusBody,
  ZaloAdsOpsSubmitResponse,
} from './zalo-ads-ops.types';

@Injectable()
export class ZaloAdsOpsService {
  constructor(
    private readonly repo: ZaloAdsOpsRepository,
    private readonly writes: CampaignWritesService,
    private readonly writeRepo: CampaignWritesRepository,
  ) {}

  isEnabled(): boolean {
    return ['1', 'true', 'yes', 'on'].includes(
      (process.env.PTT_ZALO_ADS_OPS_ENABLED ?? '0').trim().toLowerCase(),
    );
  }

  async getPreflight(clientId: string) {
    const cid = clientId.trim();
    if (!cid) throw new BadRequestException({ error: 'client_id_required' });
    const pilot = checkZaloCampaignWritePilot(cid, 'pending:new');
    if (!this.isEnabled()) {
      return { ok: true, disabled: true, client_id: cid, ready: false, pilot };
    }
    if (!(await this.repo.clientExists(cid))) {
      throw new NotFoundException({ error: 'client_not_found' });
    }
    if (await this.repo.isTenantLocked(cid)) {
      return {
        ok: true,
        client_id: cid,
        ready: false,
        items: [{ key: 'tenant_locked', passed: false, note: 'Client offboard' }],
        pilot,
      };
    }
    const accountId = await this.repo.fetchZaloAccountId(cid);
    const items = [
      {
        key: 'zalo_account',
        passed: Boolean(accountId),
        note: accountId ? `Account ${accountId}` : 'Chưa có Zalo account active',
      },
      {
        key: 'zalo_write_pilot',
        passed: pilot.allowed,
        note: pilot.warning ?? 'Pilot OK',
      },
    ];
    return {
      ok: true,
      client_id: cid,
      ready: items.every((i) => i.passed),
      external_account_id: accountId,
      items,
      pilot,
    };
  }

  async submitLaunch(body: ZaloAdsOpsLaunchBody): Promise<ZaloAdsOpsSubmitResponse> {
    if (!this.isEnabled()) {
      throw new ServiceUnavailableException({ ok: false, error: 'PTT_ZALO_ADS_OPS_ENABLED=0' });
    }
    const cid = body.client_id?.trim();
    let accountId = body.external_account_id?.trim();
    if (!cid) {
      throw new BadRequestException({ error: 'client_id required' });
    }
    if (!accountId) {
      accountId = (await this.repo.fetchZaloAccountId(cid)) ?? '';
    }
    if (!accountId) {
      throw new BadRequestException({ error: 'external_account_id_required' });
    }
    const campaignName = body.campaign_name?.trim() || 'PTT Zalo Campaign';
    const pilot = checkZaloCampaignWritePilot(cid, `pending:${campaignName}`);
    if (!pilot.allowed && !pilot.stub_mode) {
      throw new BadRequestException({ error: pilot.reason ?? 'pilot_blocked', pilot });
    }
    if (await this.repo.isTenantLocked(cid)) {
      throw new BadRequestException({ error: 'tenant_locked' });
    }

    const preflight = await this.getPreflight(cid);
    if (!preflight.ready && !body.preflight_ack) {
      throw new BadRequestException({ error: 'preflight_not_ready', preflight });
    }

    const newValue = {
      action: 'create_campaign',
      external_account_id: accountId,
      campaign_name: campaignName,
      objective: body.objective?.trim() || 'LEAD_GENERATION',
      daily_budget_vnd: Math.round(Number(body.daily_budget_vnd)),
      creative_submission_id: body.creative_submission_id?.trim() || null,
    };

    const out = await this.writes.submit({
      client_id: cid,
      channel: 'zalo',
      external_account_id: accountId,
      external_campaign_id: `pending:${campaignName}`,
      external_campaign_name: campaignName,
      change_type: 'create_campaign',
      old_value: {},
      new_value: newValue,
      submitted_by: body.submitted_by?.trim() || 'am@pttads.vn',
    });

    return {
      ok: true,
      request_id: String(out.request?.id ?? ''),
      workflow_id: out.workflow_id ?? null,
      change_type: 'create_campaign',
      pilot,
    };
  }

  async submitStatus(body: ZaloAdsOpsStatusBody): Promise<ZaloAdsOpsSubmitResponse> {
    if (!this.isEnabled()) {
      throw new ServiceUnavailableException({ ok: false, error: 'PTT_ZALO_ADS_OPS_ENABLED=0' });
    }
    const cid = body.client_id?.trim();
    const campaignId = body.external_campaign_id?.trim();
    const status = body.status?.trim().toUpperCase();
    if (!cid || !campaignId || !status) {
      throw new BadRequestException({ error: 'client_id, external_campaign_id, status required' });
    }
    const pilot = checkZaloCampaignWritePilot(cid, campaignId);
    if (!pilot.allowed && !pilot.stub_mode) {
      throw new BadRequestException({ error: pilot.reason ?? 'pilot_blocked', pilot });
    }

    const out = await this.writes.submit({
      client_id: cid,
      channel: 'zalo',
      external_campaign_id: campaignId,
      change_type: 'status',
      old_value: {},
      new_value: { status },
      submitted_by: body.submitted_by?.trim() || 'am@pttads.vn',
    });

    return {
      ok: true,
      request_id: String(out.request?.id ?? ''),
      workflow_id: out.workflow_id ?? null,
      change_type: 'status',
      pilot,
    };
  }

  async getRequestStatus(id: string) {
    const row = await this.writeRepo.findById(id.trim());
    if (!row) throw new NotFoundException({ error: 'request_not_found' });
    return { ok: true, request: row };
  }
}
