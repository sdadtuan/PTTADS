import {
  BadRequestException,
  Injectable,
  NotFoundException,
  ServiceUnavailableException,
} from '@nestjs/common';
import { CampaignWritesService } from '../campaign-writes/campaign-writes.service';
import { evaluateMetaLaunchQaItems } from '../meta-tracking/launch-qa-meta.util';
import { MetaTrackingRepository } from '../meta-tracking/meta-tracking.repository';
import { checkMetaAdsOpsPilot, metaAdsManagerDeepLink } from './meta-ads-ops-pilot.util';
import { MetaAdsOpsRepository } from './meta-ads-ops.repository';
import type {
  MetaAdsOpsEditSnapshotResponse,
  MetaAdsOpsEditSubmitBody,
  MetaAdsOpsLaunchBody,
  MetaAdsOpsPreflightResponse,
  MetaAdsOpsSubmitResponse,
  MetaAdsOpsTemplate,
} from './meta-ads-ops.types';

const TEMPLATES: MetaAdsOpsTemplate[] = [
  {
    id: 're_lead_default',
    label: 'RE Lead — mặc định',
    objective: 'OUTCOME_LEADS',
    optimization_goal: 'LEAD_GENERATION',
    billing_event: 'IMPRESSIONS',
    default_daily_budget_vnd: 500_000,
    description: 'Template Lead Gen cho BĐS',
  },
  {
    id: 're_traffic_warm',
    label: 'RE Traffic warm-up',
    objective: 'OUTCOME_TRAFFIC',
    optimization_goal: 'LINK_CLICKS',
    billing_event: 'IMPRESSIONS',
    default_daily_budget_vnd: 300_000,
    description: 'Traffic warm trước Lead',
  },
];

@Injectable()
export class MetaAdsOpsService {
  constructor(
    private readonly repo: MetaAdsOpsRepository,
    private readonly trackingRepo: MetaTrackingRepository,
    private readonly writes: CampaignWritesService,
  ) {}

  isEnabled(): boolean {
    return ['1', 'true', 'yes', 'on'].includes(
      (process.env.PTT_META_ADS_OPS_ENABLED ?? '0').trim().toLowerCase(),
    );
  }

  listTemplates(): { ok: boolean; disabled?: boolean; templates: MetaAdsOpsTemplate[] } {
    if (!this.isEnabled()) {
      return { ok: true, disabled: true, templates: [] };
    }
    return { ok: true, templates: TEMPLATES };
  }

  async getPreflight(clientId: string): Promise<MetaAdsOpsPreflightResponse> {
    const cid = clientId.trim();
    if (!cid) throw new BadRequestException({ error: 'client_id_required' });
    const pilot = checkMetaAdsOpsPilot(cid);
    if (!this.isEnabled()) {
      return {
        ok: true,
        disabled: true,
        client_id: cid,
        ready: false,
        items: [],
        pilot,
      };
    }
    if (!(await this.repo.clientExists(cid))) {
      throw new NotFoundException({ error: 'client_not_found' });
    }
    if (await this.repo.isTenantLocked(cid)) {
      return {
        ok: true,
        client_id: cid,
        ready: false,
        items: [
          {
            key: 'tenant_locked',
            label: 'Client tenant locked',
            passed: false,
            note: 'Client đang offboard — không thể launch/edit',
          },
        ],
        pilot,
      };
    }

    const items = await evaluateMetaLaunchQaItems(this.trackingRepo, cid);
    const creativeItem = {
      key: 'creative_approved',
      label: 'Creative approved (wizard step 3)',
      passed: true,
      note: 'Kiểm tra khi chọn creative trong wizard',
    };
    const mapped = [...items, creativeItem].map((item) => ({
      key: item.key,
      label:
        item.key === 'meta_pixel_configured'
          ? 'Pixel configured'
          : item.key === 'meta_capi_test_ok'
            ? 'CAPI test OK'
            : item.key === 'meta_hub_map_coverage'
              ? 'Hub map coverage'
              : item.key === 'meta_capi_recent_sent'
                ? 'CAPI recent sent'
                : item.key,
      passed: item.passed,
      note: item.note,
    }));
    const ready = mapped.every((i) => i.passed) && pilot.allowed;
    return { ok: true, client_id: cid, ready, items: mapped, pilot };
  }

  async uploadCreative(body: {
    client_id: string;
    creative_submission_id: string;
    external_account_id?: string;
  }) {
    if (!this.isEnabled()) {
      return { ok: true, disabled: true, stub: true };
    }
    const cid = body.client_id?.trim();
    const creativeId = body.creative_submission_id?.trim();
    if (!cid || !creativeId) {
      throw new BadRequestException({ error: 'client_id and creative_submission_id required' });
    }
    const creative = await this.repo.fetchApprovedCreative(cid, creativeId);
    if (!creative) throw new NotFoundException({ error: 'creative_not_found' });
    if (creative.not_approved) {
      throw new BadRequestException({ error: 'creative_not_approved', status: creative.status });
    }
    const externalCreativeId = `graph_creative_${creativeId.replace(/-/g, '').slice(0, 12)}`;
    return {
      ok: true,
      client_id: cid,
      creative_submission_id: creativeId,
      external_creative_id: externalCreativeId,
      creative_title: creative.title,
      note: 'Graph upload stub — wire Marketing API in pilot',
    };
  }

  async submitLaunch(body: MetaAdsOpsLaunchBody): Promise<MetaAdsOpsSubmitResponse> {
    if (!this.isEnabled()) {
      throw new ServiceUnavailableException({ ok: false, error: 'PTT_META_ADS_OPS_ENABLED=0' });
    }
    const cid = body.client_id?.trim();
    const accountId = body.external_account_id?.trim();
    const creativeId = body.creative_submission_id?.trim();
    if (!cid || !accountId || !creativeId) {
      throw new BadRequestException({ error: 'client_id, external_account_id, creative_submission_id required' });
    }
    const pilot = checkMetaAdsOpsPilot(cid);
    if (!pilot.allowed) {
      throw new BadRequestException({ error: pilot.reason ?? 'pilot_blocked', pilot });
    }
    if (await this.repo.isTenantLocked(cid)) {
      throw new BadRequestException({ error: 'tenant_locked' });
    }

    const preflight = await this.getPreflight(cid);
    if (!preflight.ready && !body.preflight_ack) {
      throw new BadRequestException({ error: 'preflight_not_ready', preflight });
    }

    const creative = await this.repo.fetchApprovedCreative(cid, creativeId);
    if (!creative || creative.not_approved) {
      throw new BadRequestException({ error: 'creative_not_approved' });
    }

    const template = TEMPLATES.find((t) => t.id === (body.template_id ?? 're_lead_default')) ?? TEMPLATES[0];
    const newValue = {
      action: 'create_campaign',
      template_id: template.id,
      external_account_id: accountId,
      campaign_name: body.campaign_name?.trim(),
      adset_name: body.adset_name?.trim(),
      ad_name: body.ad_name?.trim(),
      objective: template.objective,
      daily_budget_vnd: Math.round(Number(body.daily_budget_vnd)),
      creative_submission_id: creativeId,
      external_creative_id: body.external_creative_id ?? null,
    };

    const out = await this.writes.submit({
      client_id: cid,
      channel: 'meta',
      external_account_id: accountId,
      external_campaign_id: `pending:${body.campaign_name?.trim() || 'new'}`,
      external_campaign_name: body.campaign_name?.trim() || undefined,
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

  async getRequestStatus(id: string) {
    const row = await this.repo.findWriteRequest(id.trim());
    if (!row) throw new NotFoundException({ error: 'request_not_found' });
    return { ok: true, request: row };
  }

  getDeepLink(query: {
    client_id: string;
    external_campaign_id?: string;
    external_ad_id?: string;
  }) {
    const cid = query.client_id?.trim();
    if (!cid) throw new BadRequestException({ error: 'client_id_required' });
    return this.repo.fetchMetaAccount(cid).then((account) => {
      const act = String(account?.external_account_id ?? 'act_unknown');
      return {
        ok: true,
        url: metaAdsManagerDeepLink({
          externalAccountId: act,
          externalCampaignId: query.external_campaign_id?.trim(),
          externalAdId: query.external_ad_id?.trim(),
        }),
        external_account_id: act,
      };
    });
  }

  async getEditSnapshot(clientId: string, adId: string): Promise<MetaAdsOpsEditSnapshotResponse> {
    const cid = clientId.trim();
    const externalAdId = adId.trim();
    if (!cid || !externalAdId) {
      throw new BadRequestException({ error: 'client_id and external_ad_id required' });
    }
    if (!(await this.repo.clientExists(cid))) {
      throw new NotFoundException({ error: 'client_not_found' });
    }
    return {
      ok: true,
      stub: true,
      client_id: cid,
      external_ad_id: externalAdId,
      effective_status: 'ACTIVE',
      headline: 'Headline hiện tại (Graph cache stub)',
      primary_text: 'Primary text hiện tại',
      description: '',
      call_to_action: 'LEARN_MORE',
      creative_submission_id: null,
      external_creative_id: `creative_${externalAdId.slice(-8)}`,
    };
  }

  async getEditPreflight(query: {
    client_id: string;
    external_ad_id: string;
    action?: string;
    creative_submission_id?: string;
    disapproved_ack?: string;
    effective_status?: string;
  }) {
    const cid = query.client_id?.trim();
    const adId = query.external_ad_id?.trim();
    if (!cid || !adId) throw new BadRequestException({ error: 'client_id and external_ad_id required' });

    const items: Array<{ key: string; passed: boolean; note: string }> = [];
    const locked = await this.repo.isTenantLocked(cid);
    items.push({
      key: 'tenant_unlocked',
      passed: !locked,
      note: locked ? 'Client tenant locked' : 'OK',
    });
    const pilot = checkMetaAdsOpsPilot(cid);
    items.push({
      key: 'pilot_allowlist',
      passed: pilot.allowed,
      note: pilot.reason ?? 'Pilot OK',
    });
    if (query.action === 'update_ad_creative' && query.creative_submission_id) {
      const creative = await this.repo.fetchApprovedCreative(cid, query.creative_submission_id.trim());
      items.push({
        key: 'creative_approved',
        passed: Boolean(creative && !creative.not_approved),
        note: creative ? String(creative.status ?? 'approved') : 'Creative not found',
      });
    }
    const status = String(query.effective_status ?? '').toUpperCase();
    if (status === 'DISAPPROVED') {
      items.push({
        key: 'disapproved_ack',
        passed: ['1', 'true', 'yes', 'on'].includes(String(query.disapproved_ack ?? '').toLowerCase()),
        note: 'Cần ack checkbox khi ad bị disapproved',
      });
    }
    return { ok: true, ready: items.every((i) => i.passed), items };
  }

  async submitEdit(body: MetaAdsOpsEditSubmitBody): Promise<MetaAdsOpsSubmitResponse> {
    if (!this.isEnabled()) {
      throw new ServiceUnavailableException({ ok: false, error: 'PTT_META_ADS_OPS_ENABLED=0' });
    }
    const cid = body.client_id?.trim();
    const adId = body.external_ad_id?.trim();
    const action = body.action;
    if (!cid || !adId || !action) {
      throw new BadRequestException({ error: 'client_id, external_ad_id, action required' });
    }
    const pilot = checkMetaAdsOpsPilot(cid);
    if (!pilot.allowed) {
      throw new BadRequestException({ error: pilot.reason ?? 'pilot_blocked', pilot });
    }

    const snapshot = await this.getEditSnapshot(cid, adId);
    const preflight = await this.getEditPreflight({
      client_id: cid,
      external_ad_id: adId,
      action,
      creative_submission_id: String(body.new_value?.creative_submission_id ?? ''),
      disapproved_ack: body.disapproved_ack ? '1' : '0',
      effective_status: snapshot.effective_status,
    });
    if (!preflight.ready) {
      throw new BadRequestException({ error: 'edit_preflight_failed', preflight });
    }

    const diff = {
      changes: Object.keys(body.new_value).filter(
        (key) => JSON.stringify(body.old_value?.[key]) !== JSON.stringify(body.new_value?.[key]),
      ),
    };

    const out = await this.writes.submit({
      client_id: cid,
      channel: 'meta',
      external_campaign_id: body.external_campaign_id?.trim() || adId,
      change_type: action,
      old_value: body.old_value ?? {},
      new_value: body.new_value,
      submitted_by: body.submitted_by?.trim() || 'am@pttads.vn',
    });

    return {
      ok: true,
      request_id: String(out.request?.id ?? ''),
      workflow_id: out.workflow_id ?? null,
      change_type: action,
      pilot,
      diff,
    };
  }
}
