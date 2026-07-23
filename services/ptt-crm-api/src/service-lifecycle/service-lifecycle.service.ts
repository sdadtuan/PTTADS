import {
  BadRequestException,
  Injectable,
  NotFoundException,
} from '@nestjs/common';
import { SvcFinanceService } from '../svc-finance/svc-finance.service';
import { LifecycleConsultService } from './lifecycle-consult.service';
import {
  buildOfficialPlanPayload,
  mergeStrategyFramework,
  mergeTargetMarketProf,
  validateOfficialTmmt,
} from './lifecycle-marketing-plan.util';
import { paymentGateFromSummary } from './lifecycle-payment-gate.util';
import { getStageAdvanceInfo, StageAdvanceError, validateStageAdvance } from './lifecycle-stage.util';
import { LifecycleTasksRepository } from './lifecycle-tasks.repository';
import { ServiceLifecycleSqliteRepository } from './service-lifecycle-sqlite.repository';
import {
  CreateServiceLifecycleBody,
  isValidSlug,
  isValidStage,
  PatchServiceLifecycleBody,
} from './service-lifecycle.types';

@Injectable()
export class ServiceLifecycleService {
  constructor(
    private readonly sqlite: ServiceLifecycleSqliteRepository,
    private readonly tasks: LifecycleTasksRepository,
    private readonly svcFinance: SvcFinanceService,
    private readonly consult: LifecycleConsultService,
  ) {}

  list(serviceSlug?: string, amId?: string, includeDraft?: string) {
    const am = amId ? Number(amId) : undefined;
    const lifecycles = this.sqlite.listLifecycles({
      serviceSlug: serviceSlug || undefined,
      amId: am && Number.isFinite(am) && am > 0 ? am : undefined,
      includeDraft: includeDraft === '1',
    });
    return { lifecycles, funnel_stats: this.sqlite.funnelStats() };
  }

  detail(id: number) {
    const lifecycle = this.sqlite.getLifecycleById(id);
    if (!lifecycle) {
      throw new NotFoundException({ error: 'Không tìm thấy lifecycle' });
    }
    const events = this.sqlite.listEvents(id);
    return { ...lifecycle, events };
  }

  events(id: number) {
    this.requireLifecycle(id);
    return { events: this.sqlite.listEvents(id) };
  }

  create(body: CreateServiceLifecycleBody) {
    const serviceSlug = String(body.service_slug ?? '').trim();
    if (!serviceSlug) {
      throw new BadRequestException({ error: 'Cần service_slug' });
    }
    if (!isValidSlug(serviceSlug)) {
      throw new BadRequestException({ error: 'service_slug không hợp lệ' });
    }
    return this.sqlite.createDraft(body);
  }

  patch(id: number, body: PatchServiceLifecycleBody) {
    const existing = this.sqlite.getLifecycleById(id);
    if (!existing) {
      throw new NotFoundException({ error: 'Không tìm thấy lifecycle' });
    }

    if ('stage' in body && body.stage != null) {
      const toStage = String(body.stage).trim();
      if (!isValidStage(toStage)) {
        throw new BadRequestException({ error: `Stage không hợp lệ: ${toStage}` });
      }
      try {
        validateStageAdvance({
          fromStage: existing.stage,
          toStage,
          currentStageComplete: this.tasks.isStageComplete(id, existing.stage),
          tmmtGate: this.tmmtGate(id, existing.stage, toStage),
          paymentGate: this.paymentGate(id, existing.stage, toStage, Boolean(body.finance_confirm)),
        });
      } catch (err) {
        if (err instanceof StageAdvanceError) {
          throw new BadRequestException({ error: err.message, block_reason: err.message });
        }
        throw err;
      }
      const notes =
        'notes' in body && typeof body.notes === 'string'
          ? body.notes.trim().slice(0, 2000)
          : existing.notes;
      const advanced = this.sqlite.advanceStage(id, toStage, notes);
      if (toStage === 'consult' && advanced) {
        try {
          this.consult.prefillConsultTask(id, { overwrite: false });
        } catch {
          /* prefill is best-effort on advance */
        }
      }
      return advanced;
    }

    if ('service_slug' in body && body.service_slug != null) {
      const slug = String(body.service_slug).trim();
      if (slug && !isValidSlug(slug)) {
        throw new BadRequestException({ error: 'service_slug không hợp lệ' });
      }
    }

    const updated = this.sqlite.patchLifecycle(id, body);
    if (!updated) {
      throw new NotFoundException({ error: 'Không tìm thấy lifecycle' });
    }
    return updated;
  }

  advanceInfo(id: number) {
    const lc = this.requireLifecycle(id);
    const prog = this.tasks.getProgress(id)[lc.stage] ?? { done: 0, total: 0 };
    const complete = this.tasks.isStageComplete(id, lc.stage);
    const tmmtGate =
      lc.stage === 'onboard'
        ? validateOfficialTmmt(this.sqlite.getOfficialMarketingPlan(id))
        : undefined;
    const paymentGate =
      lc.stage === 'handover'
        ? paymentGateFromSummary(this.svcFinance.summary(id) as { outstanding_vnd?: number })
        : undefined;
    return getStageAdvanceInfo({
      currentStage: lc.stage,
      currentStageComplete: complete,
      currentDone: prog.done,
      currentTotal: prog.total,
      tmmtGate,
      paymentGate,
    });
  }

  listTasks(id: number) {
    this.requireLifecycle(id);
    return { tasks: this.tasks.listTasksGrouped(id) };
  }

  progress(id: number) {
    this.requireLifecycle(id);
    return { progress: this.tasks.getProgress(id) };
  }

  updateTask(
    lifecycleId: number,
    taskId: number,
    body: { is_done?: boolean; notes?: string; form_data?: Record<string, unknown> },
    doneBy?: number | null,
  ) {
    this.requireLifecycle(lifecycleId);
    const task = this.tasks.getTask(taskId);
    if (!task || task.lifecycle_id !== lifecycleId) {
      throw new NotFoundException({ error: 'Không tìm thấy task' });
    }
    const updated = this.tasks.updateTask(taskId, { ...body, done_by: doneBy ?? null });
    if (!updated) {
      throw new NotFoundException({ error: 'Không tìm thấy task' });
    }
    return { task: updated };
  }

  createCustomTask(
    lifecycleId: number,
    body: { stage?: string; title?: string; description?: string },
  ) {
    this.requireLifecycle(lifecycleId);
    const stage = String(body.stage ?? '').trim();
    if (!isValidStage(stage)) {
      throw new BadRequestException({ error: 'Stage không hợp lệ' });
    }
    const title = String(body.title ?? '').trim();
    if (!title) {
      throw new BadRequestException({ error: 'Cần title' });
    }
    const task = this.tasks.createCustomTask(
      lifecycleId,
      stage,
      title,
      String(body.description ?? ''),
    );
    return { task };
  }

  marketingPlan(id: number) {
    this.requireLifecycle(id);
    const plan = this.sqlite.getOfficialMarketingPlan(id);
    return buildOfficialPlanPayload(plan);
  }

  patchMarketingPlan(id: number, body: Record<string, unknown>) {
    const lc = this.requireLifecycle(id);
    if (!lc.marketing_plan_id) {
      throw new NotFoundException({ error: 'Chưa có Kế hoạch MKT chính thức' });
    }
    const existing = this.sqlite.getOfficialMarketingPlan(id);
    const patch: Record<string, unknown> = { ...body };
    if (body.strategy_framework && typeof body.strategy_framework === 'object') {
      patch.strategy_framework_json = mergeStrategyFramework(
        String(existing?.strategy_framework_json ?? '{}'),
        body.strategy_framework as Record<string, string>,
      );
      delete patch.strategy_framework;
    }
    if (body.target_market_prof && typeof body.target_market_prof === 'object') {
      patch.target_market_prof_json = mergeTargetMarketProf(
        String(existing?.target_market_prof_json ?? '{}'),
        body.target_market_prof as Record<string, string>,
      );
      delete patch.target_market_prof;
    }
    const plan = this.sqlite.updateOfficialMarketingPlan(lc.marketing_plan_id, patch);
    if (!plan) {
      throw new NotFoundException({ error: 'Không tìm thấy plan' });
    }
    return buildOfficialPlanPayload(plan);
  }

  marketingPlanValidation(id: number) {
    this.requireLifecycle(id);
    const plan = this.sqlite.getOfficialMarketingPlan(id);
    return validateOfficialTmmt(plan);
  }

  presalesSummary(id: number) {
    this.requireLifecycle(id);
    return this.sqlite.presalesSummary(id);
  }

  createExpense(id: number, body: Record<string, unknown>) {
    this.requireLifecycle(id);
    return this.sqlite.createExpense(id, body);
  }

  financeSummary(id: number) {
    return this.svcFinance.summary(id);
  }

  listPayments(id: number) {
    this.requireLifecycle(id);
    return this.svcFinance.listPayments(id);
  }

  context(id: number) {
    const ctx = this.sqlite.getLifecycleContext(id);
    if (!ctx) {
      throw new NotFoundException({ error: 'Không tìm thấy lifecycle' });
    }
    return ctx;
  }

  consultBrief(id: number) {
    return this.consult.getConsultBrief(id);
  }

  consultPrefill(id: number, body: Record<string, unknown>) {
    return this.consult.prefillConsultTask(id, { overwrite: Boolean(body.overwrite) });
  }

  private requireLifecycle(id: number) {
    const lc = this.sqlite.getLifecycleById(id);
    if (!lc) {
      throw new NotFoundException({ error: 'Không tìm thấy lifecycle' });
    }
    return lc;
  }

  private tmmtGate(lifecycleId: number, fromStage: string, toStage: string) {
    if (toStage === 'deliver' && fromStage === 'onboard') {
      return validateOfficialTmmt(this.sqlite.getOfficialMarketingPlan(lifecycleId));
    }
    return undefined;
  }

  private paymentGate(
    lifecycleId: number,
    fromStage: string,
    toStage: string,
    financeConfirm: boolean,
  ) {
    if (toStage !== 'retain' || fromStage !== 'handover') return undefined;
    return paymentGateFromSummary(
      this.svcFinance.summary(lifecycleId) as { outstanding_vnd?: number },
      financeConfirm,
    );
  }
}
