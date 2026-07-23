import {
  BadRequestException,
  Injectable,
  NotFoundException,
  ServiceUnavailableException,
} from '@nestjs/common';
import { AppConfigService } from '../config/app-config.service';
import { CreativesRepository } from '../creatives/creatives.repository';
import { CreativesService } from '../creatives/creatives.service';
import { WorkflowsService } from '../workflows/workflows.service';
import { LaunchQaAutoStartService } from './launch-qa-auto-start.service';
import { LaunchQaPgRepository } from './launch-qa-pg.repository';
import { launchQaGateFromRun, launchQaProgress } from './lifecycle-launch-gate.util';
import { launchQaHandoverGateFromRun } from './lifecycle-launch-handover-gate.util';
import { ServiceLifecycleSqliteRepository } from './service-lifecycle-sqlite.repository';

@Injectable()
export class LifecycleLaunchQaService {
  constructor(
    private readonly sqlite: ServiceLifecycleSqliteRepository,
    private readonly repo: LaunchQaPgRepository,
    private readonly autoStart: LaunchQaAutoStartService,
    private readonly creatives: CreativesService,
    private readonly creativesRepo: CreativesRepository,
    private readonly workflows: WorkflowsService,
    private readonly config: AppConfigService,
  ) {}

  async launchQa(lifecycleId: number) {
    const ctx = this.resolveLaunchContext(lifecycleId);
    const autoStartEnabled = this.config.launchQaAutoStartOnDeliver;
    if (!ctx.ok) {
      return {
        lifecycle_id: lifecycleId,
        auto_start_enabled: autoStartEnabled,
        has_context: false,
        run: null,
        progress: { total: 0, completed: 0, percent: 0 },
        gate: launchQaGateFromRun({ run: null, hasContext: false }),
        message: ctx.message,
      };
    }

    const run = await this.repo.findLatestRun(ctx.clientId!, ctx.campaignCode!);
    const progress = launchQaProgress(run?.checklist ?? null);
    return {
      lifecycle_id: lifecycleId,
      auto_start_enabled: autoStartEnabled,
      has_context: true,
      client_id: ctx.clientId,
      external_campaign_id: ctx.campaignCode,
      campaign_name: ctx.campaignName,
      run,
      progress,
      gate: launchQaGateFromRun({ run, hasContext: true }),
      message: run
        ? null
        : autoStartEnabled
          ? 'Chưa có Launch QA run — sẽ tạo khi vào Deliver (auto-start).'
          : 'PTT_LAUNCH_QA_AUTO_START_ON_DELIVER đang tắt.',
    };
  }

  async startLaunchQa(lifecycleId: number, startedBy?: string) {
    const ctx = this.resolveLaunchContext(lifecycleId);
    if (!ctx.ok) {
      throw new BadRequestException({ error: ctx.message ?? 'missing_context' });
    }
    const result = await this.autoStart.maybeStartOnDeliverEnter({
      agencyClientId: ctx.clientId!,
      externalCampaignId: ctx.campaignCode!,
      campaignName: ctx.campaignName,
      startedBy,
    });
    const payload = await this.launchQa(lifecycleId);
    return { ...payload, start: result };
  }

  async patchChecklistItem(
    lifecycleId: number,
    itemKey: string,
    body: { completed?: boolean; note?: string },
    completedBy?: string,
  ) {
    const ctx = this.resolveLaunchContext(lifecycleId);
    if (!ctx.ok) {
      throw new BadRequestException({ error: ctx.message ?? 'missing_context' });
    }
    if (!(await this.repo.pgReady())) {
      throw new ServiceUnavailableException({ error: 'launch_qa_pg_unavailable' });
    }

    let run = await this.repo.findLatestRun(ctx.clientId!, ctx.campaignCode!);
    if (!run) {
      const started = await this.autoStart.maybeStartOnDeliverEnter({
        agencyClientId: ctx.clientId!,
        externalCampaignId: ctx.campaignCode!,
        campaignName: ctx.campaignName,
        startedBy: completedBy,
      });
      if (!started.run_id) {
        throw new BadRequestException({ error: started.reason ?? 'cannot_start_run' });
      }
      run = await this.repo.findById(started.run_id);
    }
    if (!run) {
      throw new NotFoundException({ error: 'run_not_found' });
    }

    const key = itemKey.trim();
    try {
      const updated = await this.repo.updateChecklistItem(run.id, key, {
        completed: Boolean(body.completed),
        completedBy,
        note: body.note?.trim(),
      });
      if (this.temporalNudgeEnabled()) {
        try {
          await this.workflows.nudgeLaunchQa(updated.id);
        } catch {
          /* optional */
        }
      }
      return {
        lifecycle_id: lifecycleId,
        run: updated,
        progress: launchQaProgress(updated.checklist),
        gate: launchQaGateFromRun({ run: updated, hasContext: true }),
      };
    } catch (err) {
      const msg = err instanceof Error ? err.message : 'update_failed';
      if (msg === 'invalid_item') {
        throw new BadRequestException({ error: 'invalid_checklist_item' });
      }
      if (msg === 'run_not_in_progress') {
        throw new BadRequestException({ error: 'run_not_in_progress' });
      }
      throw new BadRequestException({ error: msg });
    }
  }

  async creativeBrief(lifecycleId: number) {
    const ctx = this.resolveLaunchContext(lifecycleId);
    const plan = this.sqlite.getOfficialMarketingPlan(lifecycleId);
    let creatives: Awaited<ReturnType<CreativesRepository['listForCampaign']>> = [];
    if (ctx.ok && (await this.creativesRepo.pgCreativesReady())) {
      creatives = await this.creativesRepo.listForCampaign(ctx.clientId!, ctx.campaignCode!, 10);
    }
    const sf = this.parseJson(
      plan?.strategy_framework_json != null ? String(plan.strategy_framework_json) : undefined,
    );
    const headline = String(sf.headline ?? sf.key_message ?? '').trim();
    const cta = String(sf.cta ?? sf.call_to_action ?? '').trim();
    const approved = creatives.find((c) => c.status === 'approved');
    return {
      lifecycle_id: lifecycleId,
      has_context: ctx.ok,
      client_id: ctx.clientId,
      external_campaign_id: ctx.campaignCode,
      campaign_name: ctx.campaignName,
      suggested_brief: {
        title: ctx.campaignName ? `Creative — ${ctx.campaignName}` : 'Launch creative v1',
        description: [headline && `Headline: ${headline}`, cta && `CTA: ${cta}`]
          .filter(Boolean)
          .join('\n'),
        from_tmmt: Boolean(headline || cta),
      },
      creatives,
      has_approved_creative: Boolean(approved),
      portal_hint: ctx.clientId
        ? 'Client duyệt creative trên portal — checklist mục creative_approved cần approved.'
        : null,
      message: ctx.ok ? null : ctx.message,
    };
  }

  async submitCreative(
    lifecycleId: number,
    body: {
      title?: string;
      description?: string;
      asset_url?: string;
      asset_type?: string;
      submitted_by?: string;
    },
  ) {
    const ctx = this.resolveLaunchContext(lifecycleId);
    if (!ctx.ok) {
      throw new BadRequestException({ error: ctx.message ?? 'missing_context' });
    }
    const brief = await this.creativeBrief(lifecycleId);
    const title = String(body.title ?? brief.suggested_brief.title ?? '').trim();
    if (!title) {
      throw new BadRequestException({ error: 'title required' });
    }
    return this.creatives.submit({
      client_id: ctx.clientId!,
      title,
      description: body.description?.trim() || brief.suggested_brief.description || undefined,
      external_campaign_id: ctx.campaignCode!,
      external_campaign_name: ctx.campaignName,
      asset_url: body.asset_url?.trim(),
      asset_type: body.asset_type?.trim() || 'image',
      submitted_by: body.submitted_by?.trim() || 'am@pttads.vn',
    });
  }

  async launchQaGateForLifecycle(lifecycleId: number, launchQaConfirm?: boolean) {
    const payload = await this.launchQa(lifecycleId);
    const ctx = this.resolveLaunchContext(lifecycleId);
    return launchQaHandoverGateFromRun({
      run: payload.run,
      hasContext: ctx.ok,
      launchQaConfirm,
    });
  }

  async maybeAutoStartOnDeliver(lifecycleId: number, startedBy?: string) {
    const ctx = this.resolveLaunchContext(lifecycleId);
    if (!ctx.ok) return { started: false, reason: ctx.message };
    return this.autoStart.maybeStartOnDeliverEnter({
      agencyClientId: ctx.clientId!,
      externalCampaignId: ctx.campaignCode!,
      campaignName: ctx.campaignName,
      startedBy,
    });
  }

  private resolveLaunchContext(lifecycleId: number): {
    ok: boolean;
    clientId?: string;
    campaignCode?: string;
    campaignName?: string;
    message?: string;
  } {
    const ctx = this.sqlite.getLifecycleContext(lifecycleId);
    if (!ctx) {
      return { ok: false, message: 'Không tìm thấy lifecycle' };
    }
    const clientId = String(ctx.contract.agency_client_id ?? '').trim();
    const campaignCode = String(ctx.campaign.code ?? '').trim();
    if (!clientId) {
      return { ok: false, message: 'HĐ chưa có agency_client_id — liên kết client trước khi Launch QA' };
    }
    if (!campaignCode) {
      return { ok: false, message: 'Chưa có campaign code trên HĐ — gán campaign trước khi Launch QA' };
    }
    return {
      ok: true,
      clientId,
      campaignCode,
      campaignName: String(ctx.campaign.name ?? '').trim() || undefined,
    };
  }

  private parseJson(raw: string | null | undefined): Record<string, string> {
    try {
      const v = JSON.parse(String(raw ?? '{}'));
      return v && typeof v === 'object' ? (v as Record<string, string>) : {};
    } catch {
      return {};
    }
  }

  private temporalNudgeEnabled(): boolean {
    return Boolean(this.config.temporalAddress);
  }
}
