import {
  BadRequestException,
  Injectable,
  NotFoundException,
} from '@nestjs/common';
import { MarketingPlansSqliteRepository } from './marketing-plans-sqlite.repository';
import {
  CreateMarketingPlanBody,
  CRM_MARKETING_PLAN_STATUSES,
  PatchMarketingPlanBody,
} from './marketing-plans.types';

@Injectable()
export class MarketingPlansService {
  constructor(private readonly sqlite: MarketingPlansSqliteRepository) {}

  list(fiscalYear?: number, status?: string, q?: string) {
    const qRaw = String(q ?? '').trim().toLowerCase();
    let st = String(status ?? 'all').trim().toLowerCase();
    if (!CRM_MARKETING_PLAN_STATUSES.includes(st as (typeof CRM_MARKETING_PLAN_STATUSES)[number]) && st !== 'all') {
      st = 'all';
    }
    const plans = this.sqlite.listPlans({
      fiscalYear,
      status: st,
      q: qRaw || undefined,
    });
    return { plans };
  }

  detail(id: number) {
    const plan = this.sqlite.getPlanById(id);
    if (!plan) {
      throw new NotFoundException({ error: 'Không tìm thấy kế hoạch' });
    }
    const milestones = this.sqlite.listMilestones(id);
    const campaigns = this.sqlite.listCampaigns(id);
    return { ...plan, milestones, campaigns };
  }

  create(body: CreateMarketingPlanBody) {
    const name = String(body.name ?? '').trim();
    if (!name) {
      throw new BadRequestException({ error: 'Thiếu tên kế hoạch' });
    }
    return this.sqlite.createPlan({ ...body, name });
  }

  patch(id: number, body: PatchMarketingPlanBody) {
    if ('name' in body && body.name != null) {
      const nm = String(body.name).trim();
      if (!nm) {
        throw new BadRequestException({ error: 'Tên không được trống' });
      }
    }
    const updated = this.sqlite.patchPlan(id, body);
    if (!updated) {
      throw new NotFoundException({ error: 'Không tìm thấy kế hoạch' });
    }
    return updated;
  }

  segmentRefs(id: number) {
    const plan = this.sqlite.getPlanById(id);
    if (!plan) {
      throw new NotFoundException({ error: 'Không tìm thấy kế hoạch' });
    }
    return { refs: [] };
  }
}
