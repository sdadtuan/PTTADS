import { Injectable, OnModuleDestroy } from '@nestjs/common';
import { DatabaseSync } from 'node:sqlite';
import { catalogTs } from '../catalog/catalog-slug.util';
import { AppConfigService } from '../config/app-config.service';
import {
  CreateMarketingPlanBody,
  CRM_MARKETING_PLAN_PRIORITY_LABELS,
  CRM_MARKETING_PLAN_STATUS_LABELS,
  MarketingPlanCampaignRow,
  MarketingPlanMilestoneRow,
  MarketingPlanRow,
  normalizeMarketingPlanPriority,
  normalizeMarketingPlanStatus,
  PatchMarketingPlanBody,
} from './marketing-plans.types';

const PLAN_LIST_SELECT = `
SELECT p.*,
       st.name AS owner_name,
       (SELECT COUNT(*) FROM crm_marketing_plan_campaigns mpc WHERE mpc.plan_id = p.id)
         AS linked_campaign_count,
       (SELECT COUNT(*) FROM crm_marketing_plan_milestones mm WHERE mm.plan_id = p.id)
         AS milestone_total,
       (SELECT COUNT(*) FROM crm_marketing_plan_milestones mm
        WHERE mm.plan_id = p.id AND mm.status = 'done') AS milestone_done
FROM crm_marketing_plans p
LEFT JOIN crm_staff st ON st.id = p.owner_staff_id
`;

const PLAN_DETAIL_SELECT = `
SELECT p.*, st.name AS owner_name
FROM crm_marketing_plans p
LEFT JOIN crm_staff st ON st.id = p.owner_staff_id
`;

@Injectable()
export class MarketingPlansSqliteRepository implements OnModuleDestroy {
  private db: DatabaseSync | null = null;

  constructor(private readonly config: AppConfigService) {}

  private get database(): DatabaseSync {
    if (!this.db) {
      this.db = new DatabaseSync(this.config.sqlitePath);
      this.db.exec('PRAGMA foreign_keys = ON');
    }
    return this.db;
  }

  onModuleDestroy(): void {
    if (this.db) {
      this.db.close();
      this.db = null;
    }
  }

  listPlans(opts: {
    fiscalYear?: number;
    status?: string;
    q?: string;
  }): MarketingPlanRow[] {
    const clauses: string[] = [];
    const params: (string | number)[] = [];

    if (opts.fiscalYear != null) {
      clauses.push('p.fiscal_year = ?');
      params.push(opts.fiscalYear);
    }
    if (opts.status && opts.status !== 'all') {
      clauses.push('p.status = ?');
      params.push(opts.status);
    }
    if (opts.q) {
      clauses.push(
        '(lower(p.name) LIKE ? OR lower(p.code) LIKE ? OR lower(p.period_label) LIKE ?)',
      );
      const like = `%${opts.q}%`;
      params.push(like, like, like);
    }

    const whereSql = clauses.length ? `WHERE ${clauses.join(' AND ')}` : '';
    const rows = this.database
      .prepare(
        `${PLAN_LIST_SELECT}
         ${whereSql}
         ORDER BY p.fiscal_year DESC, datetime(p.updated_at) DESC, p.id DESC
         LIMIT 300`,
      )
      .all(...params) as unknown as Array<Record<string, unknown>>;

    return rows.map((r) => this.mapPlanRow(r));
  }

  getPlanById(planId: number): MarketingPlanRow | null {
    const row = this.database
      .prepare(`${PLAN_DETAIL_SELECT} WHERE p.id = ?`)
      .get(planId) as unknown as Record<string, unknown> | undefined;
    return row ? this.mapPlanRow(row) : null;
  }

  listMilestones(planId: number): MarketingPlanMilestoneRow[] {
    const rows = this.database
      .prepare(
        `SELECT * FROM crm_marketing_plan_milestones
         WHERE plan_id = ?
         ORDER BY position ASC, id ASC`,
      )
      .all(planId) as unknown as Array<Record<string, unknown>>;
    return rows.map((r) => ({
      id: Number(r.id),
      plan_id: Number(r.plan_id),
      position: Number(r.position ?? 0),
      title: String(r.title ?? ''),
      description: String(r.description ?? ''),
      due_date: String(r.due_date ?? ''),
      status: String(r.status ?? ''),
      owner_staff_id: r.owner_staff_id != null ? Number(r.owner_staff_id) : null,
      notes: String(r.notes ?? ''),
      created_at: String(r.created_at ?? ''),
      updated_at: String(r.updated_at ?? ''),
    }));
  }

  listCampaigns(planId: number): MarketingPlanCampaignRow[] {
    const rows = this.database
      .prepare(
        `SELECT c.*
         FROM crm_marketing_plan_campaigns l
         JOIN crm_campaigns c ON c.id = l.campaign_id
         WHERE l.plan_id = ?
         ORDER BY c.name COLLATE NOCASE ASC`,
      )
      .all(planId) as unknown as Array<Record<string, unknown>>;
    return rows.map((r) => ({
      id: Number(r.id),
      name: String(r.name ?? ''),
      code: String(r.code ?? ''),
      status: String(r.status ?? ''),
      channel: String(r.channel ?? ''),
      ...r,
    }));
  }

  createPlan(body: CreateMarketingPlanBody): MarketingPlanRow {
    const name = String(body.name ?? '').trim().slice(0, 400);
    const code = String(body.code ?? '').trim().slice(0, 64);
    const status = normalizeMarketingPlanStatus(body.status);
    const priority = normalizeMarketingPlanPriority(body.priority);
    const now = new Date();
    let fiscalYear = Number(body.fiscal_year ?? now.getFullYear());
    if (!Number.isFinite(fiscalYear)) fiscalYear = now.getFullYear();
    fiscalYear = Math.max(1990, Math.min(2120, fiscalYear));

    const periodLabel = String(body.period_label ?? '').trim().slice(0, 120);
    const northStar = String(body.north_star ?? '').trim().slice(0, 2000);
    const objectives = String(body.objectives ?? '').trim().slice(0, 32000);
    const audiences = String(body.audiences ?? '').trim().slice(0, 32000);
    const risksNotes = String(body.risks_notes ?? '').trim().slice(0, 32000);
    const notes = String(body.notes ?? '').trim().slice(0, 32000);
    const startDate = String(body.start_date ?? '').trim().slice(0, 32);
    const endDate = String(body.end_date ?? '').trim().slice(0, 32);

    let budgetPlanned = Number(body.budget_planned_vnd ?? 0);
    if (!Number.isFinite(budgetPlanned)) budgetPlanned = 0;
    budgetPlanned = Math.max(0, Math.min(budgetPlanned, 9_999_999_999_999));

    let budgetActual = Number(body.budget_actual_vnd ?? 0);
    if (!Number.isFinite(budgetActual)) budgetActual = 0;
    budgetActual = Math.max(0, Math.min(budgetActual, 9_999_999_999_999));

    let ownerId: number | null = null;
    if (body.owner_staff_id != null && body.owner_staff_id !== 0) {
      const oid = Number(body.owner_staff_id);
      if (Number.isFinite(oid) && oid > 0) {
        const staff = this.database
          .prepare('SELECT id FROM crm_staff WHERE id = ?')
          .get(oid) as unknown as { id: number } | undefined;
        if (staff) ownerId = oid;
      }
    }

    const tsDate = now.toISOString().slice(0, 10);
    const ts = catalogTs();

    const result = this.database
      .prepare(
        `INSERT INTO crm_marketing_plans (
           code, name, status, priority, fiscal_year, period_label, north_star, objectives,
           pillars_json, audiences, channels_focus_json, budget_planned_vnd, budget_actual_vnd,
           success_metrics_json, risks_notes, owner_staff_id, start_date, end_date, notes,
           strategy_framework_json, target_market_prof_json, target_market_steps4_json,
           khtn_market_research_json, created_at, updated_at
         ) VALUES (
           ?, ?, ?, ?, ?, ?, ?, ?, '[]', ?, '[]', ?, ?, '[]', ?, ?, ?, ?, ?,
           '{}', '{}', '{}', '{}', ?, ?
         )`,
      )
      .run(
        code,
        name,
        status,
        priority,
        fiscalYear,
        periodLabel,
        northStar,
        objectives,
        audiences,
        budgetPlanned,
        budgetActual,
        risksNotes,
        ownerId,
        startDate,
        endDate,
        notes,
        tsDate,
        ts,
      );

    const plan = this.getPlanById(Number(result.lastInsertRowid));
    if (!plan) throw new Error('Failed to create marketing plan');
    return plan;
  }

  patchPlan(planId: number, body: PatchMarketingPlanBody): MarketingPlanRow | null {
    const existing = this.database
      .prepare('SELECT * FROM crm_marketing_plans WHERE id = ?')
      .get(planId) as unknown as Record<string, unknown> | undefined;
    if (!existing) return null;

    const merged: Record<string, unknown> = { ...existing };
    if ('name' in body && typeof body.name === 'string') {
      merged.name = body.name.trim().slice(0, 400);
    }
    if ('status' in body) {
      merged.status = normalizeMarketingPlanStatus(body.status);
    }
    if ('priority' in body) {
      merged.priority = normalizeMarketingPlanPriority(body.priority);
    }
    if ('notes' in body && typeof body.notes === 'string') {
      merged.notes = body.notes.trim().slice(0, 32000);
    }
    if ('objectives' in body && typeof body.objectives === 'string') {
      merged.objectives = body.objectives.trim().slice(0, 32000);
    }

    const ts = catalogTs();
    this.database
      .prepare(
        `UPDATE crm_marketing_plans
         SET name = ?, status = ?, priority = ?, notes = ?, objectives = ?, updated_at = ?
         WHERE id = ?`,
      )
      .run(
        String(merged.name ?? ''),
        String(merged.status ?? ''),
        String(merged.priority ?? ''),
        String(merged.notes ?? ''),
        String(merged.objectives ?? ''),
        ts,
        planId,
      );

    return this.getPlanById(planId);
  }

  private mapPlanRow(row: Record<string, unknown>): MarketingPlanRow {
    const status = String(row.status ?? '');
    const priority = String(row.priority ?? '');
    return {
      id: Number(row.id),
      code: String(row.code ?? ''),
      name: String(row.name ?? ''),
      status,
      status_label: CRM_MARKETING_PLAN_STATUS_LABELS[status] ?? status,
      priority,
      priority_label: CRM_MARKETING_PLAN_PRIORITY_LABELS[priority] ?? priority,
      fiscal_year: Number(row.fiscal_year ?? 0),
      period_label: String(row.period_label ?? ''),
      north_star: String(row.north_star ?? ''),
      objectives: String(row.objectives ?? ''),
      pillars_json: String(row.pillars_json ?? '[]'),
      audiences: String(row.audiences ?? ''),
      channels_focus_json: String(row.channels_focus_json ?? '[]'),
      budget_planned_vnd: Number(row.budget_planned_vnd ?? 0),
      budget_actual_vnd: Number(row.budget_actual_vnd ?? 0),
      success_metrics_json: String(row.success_metrics_json ?? '[]'),
      risks_notes: String(row.risks_notes ?? ''),
      owner_staff_id: row.owner_staff_id != null ? Number(row.owner_staff_id) : null,
      owner_name: String(row.owner_name ?? ''),
      start_date: String(row.start_date ?? ''),
      end_date: String(row.end_date ?? ''),
      notes: String(row.notes ?? ''),
      strategy_framework_json: String(row.strategy_framework_json ?? '{}'),
      target_market_prof_json: String(row.target_market_prof_json ?? '{}'),
      target_market_steps4_json: String(row.target_market_steps4_json ?? '{}'),
      khtn_market_research_json: String(row.khtn_market_research_json ?? '{}'),
      created_at: String(row.created_at ?? ''),
      updated_at: String(row.updated_at ?? ''),
      linked_campaign_count:
        row.linked_campaign_count != null ? Number(row.linked_campaign_count) : undefined,
      milestone_total: row.milestone_total != null ? Number(row.milestone_total) : undefined,
      milestone_done: row.milestone_done != null ? Number(row.milestone_done) : undefined,
    };
  }
}
