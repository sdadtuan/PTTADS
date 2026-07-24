import {
  BadRequestException,
  Injectable,
  NotFoundException,
  ServiceUnavailableException,
} from '@nestjs/common';
import { AppConfigService } from '../config/app-config.service';
import { CampaignWritesRepository } from '../campaign-writes/campaign-writes.repository';
import { CampaignWritesService } from '../campaign-writes/campaign-writes.service';
import { checkCampaignWritePilot } from '../campaign-writes/meta-campaign-write-pilot.util';
import { CreativesRepository } from '../creatives/creatives.repository';
import { CreativesService } from '../creatives/creatives.service';
import { WorkflowsService } from '../workflows/workflows.service';
import { LaunchQaAutoStartService } from './launch-qa-auto-start.service';
import { LaunchQaMetaBridgeService } from '../launch-qa/launch-qa-meta-bridge.service';
import { LaunchQaPgRepository } from './launch-qa-pg.repository';
import { isMetaLaunchQaItemKey } from '../meta-tracking/launch-qa-meta.util';
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
    private readonly campaignWrites: CampaignWritesService,
    private readonly campaignWritesRepo: CampaignWritesRepository,
    private readonly workflows: WorkflowsService,
    private readonly config: AppConfigService,
    private readonly metaBridge: LaunchQaMetaBridgeService,
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

    let run = await this.repo.findLatestRun(ctx.clientId!, ctx.campaignCode!);
    if (run) {
      const synced = await this.metaBridge.syncRun(run);
      if (synced.run_id) {
        run = (await this.repo.findById(synced.run_id)) ?? run;
      }
    }
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
    if (isMetaLaunchQaItemKey(key)) {
      throw new BadRequestException({
        error: 'meta_checklist_auto_only',
        hint: 'Meta checklist items are auto-evaluated — refresh Launch QA or run preflight on /meta/tracking',
      });
    }
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
    const latestRejected = creatives.find((c) => c.status === 'rejected');
    const pending = creatives.find((c) => c.status === 'pending_client');
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
      pending_creative: pending ?? null,
      latest_rejected: latestRejected ?? null,
      portal_hint: ctx.clientId
        ? 'Client duyệt creative trên portal — approve sẽ auto-tick checklist creative_approved.'
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
      resubmit?: boolean;
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

    let version = 1;
    if (body.resubmit && (await this.creativesRepo.pgCreativesReady())) {
      version =
        (await this.creativesRepo.maxVersionForCampaign(ctx.clientId!, ctx.campaignCode!)) + 1;
    }

    return this.creatives.submit({
      client_id: ctx.clientId!,
      title,
      description: body.description?.trim() || brief.suggested_brief.description || undefined,
      external_campaign_id: ctx.campaignCode!,
      external_campaign_name: ctx.campaignName,
      version,
      asset_url: body.asset_url?.trim(),
      asset_type: body.asset_type?.trim() || 'image',
      submitted_by: body.submitted_by?.trim() || 'am@pttads.vn',
    });
  }

  async budgetBrief(lifecycleId: number) {
    const ctx = this.resolveLaunchContext(lifecycleId);
    const plan = this.sqlite.getOfficialMarketingPlan(lifecycleId);
    const sf = this.parseJson(
      plan?.strategy_framework_json != null ? String(plan.strategy_framework_json) : undefined,
    );
    const suggestedBudget = this.extractSuggestedBudgetVnd(sf);
    let writes: Awaited<ReturnType<CampaignWritesRepository['listForCampaign']>> = [];
    if (ctx.ok && (await this.campaignWritesRepo.tableReady())) {
      writes = await this.campaignWritesRepo.listForCampaign(ctx.clientId!, ctx.campaignCode!, 10);
    }
    const pending = writes.find((w) => w.status === 'pending_approval');
    const latestFailed = writes.find((w) => w.status === 'execution_failed');
    const executed = writes.find((w) => w.status === 'executed' && w.change_type === 'daily_budget');
    const pilot =
      ctx.ok && ctx.clientId && ctx.campaignCode
        ? checkCampaignWritePilot(ctx.clientId, ctx.campaignCode)
        : null;
    return {
      lifecycle_id: lifecycleId,
      has_context: ctx.ok,
      client_id: ctx.clientId,
      external_campaign_id: ctx.campaignCode,
      campaign_name: ctx.campaignName,
      suggested_budget_vnd: suggestedBudget,
      from_tmmt: suggestedBudget != null,
      writes,
      has_executed_budget: Boolean(executed),
      pending_write: pending ?? null,
      latest_execution_failed: latestFailed ?? null,
      pilot_check: pilot,
      hint: ctx.clientId
        ? 'GDKD duyệt trên Campaign Write Hub — executed sẽ auto-tick budget_confirmed.'
        : null,
      message: ctx.ok ? null : ctx.message,
    };
  }

  async submitBudget(
    lifecycleId: number,
    body: {
      daily_budget_vnd?: number;
      submitted_by?: string;
    },
  ) {
    const ctx = this.resolveLaunchContext(lifecycleId);
    if (!ctx.ok) {
      throw new BadRequestException({ error: ctx.message ?? 'missing_context' });
    }
    const brief = await this.budgetBrief(lifecycleId);
    const budget = Number(body.daily_budget_vnd ?? brief.suggested_budget_vnd);
    if (!Number.isFinite(budget) || budget < 0) {
      throw new BadRequestException({ error: 'daily_budget_vnd required' });
    }
    const pilot = checkCampaignWritePilot(ctx.clientId!, ctx.campaignCode!);
    const out = await this.campaignWrites.submit({
      client_id: ctx.clientId!,
      external_campaign_id: ctx.campaignCode!,
      external_campaign_name: ctx.campaignName,
      change_type: 'daily_budget',
      new_value: { daily_budget_vnd: Math.round(budget) },
      submitted_by: body.submitted_by?.trim() || 'am@pttads.vn',
    });
    return {
      ...out,
      pilot_check: pilot,
    };
  }

  private extractSuggestedBudgetVnd(sf: Record<string, string>): number | null {
    for (const key of ['daily_budget', 'daily_budget_vnd', 'budget', 'monthly_budget']) {
      const raw = sf[key];
      if (raw == null || raw === '') continue;
      const n = Number(String(raw).replace(/[^\d.-]/g, ''));
      if (Number.isFinite(n) && n >= 0) return Math.round(n);
    }
    return null;
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
