import { Injectable, OnModuleDestroy } from '@nestjs/common';
import { DatabaseSync } from 'node:sqlite';
import { catalogTs } from '../catalog/catalog-slug.util';
import { AppConfigService } from '../config/app-config.service';
import { createLifecycleExpense, listPresalesSummary } from './lifecycle-finance.util';
import {
  CreateServiceLifecycleBody,
  PatchServiceLifecycleBody,
  ServiceLifecycleEventRow,
  ServiceLifecycleRow,
} from './service-lifecycle.types';
import type { LifecycleContextDto } from './lifecycle-context.util';

@Injectable()
export class ServiceLifecycleSqliteRepository implements OnModuleDestroy {
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

  listLifecycles(opts: {
    serviceSlug?: string;
    amId?: number;
    includeDraft?: boolean;
  }): ServiceLifecycleRow[] {
    const conditions: string[] = [];
    const params: (string | number)[] = [];

    if (opts.includeDraft) {
      conditions.push("status IN ('active', 'draft')");
    } else {
      conditions.push("status = 'active'");
    }
    if (opts.serviceSlug) {
      conditions.push('service_slug = ?');
      params.push(opts.serviceSlug);
    }
    if (opts.amId) {
      conditions.push('assigned_am = ?');
      params.push(opts.amId);
    }

    const where = conditions.join(' AND ');
    const rows = this.database
      .prepare(
        `SELECT * FROM crm_service_lifecycle
         WHERE ${where}
         ORDER BY updated_at DESC`,
      )
      .all(...params) as unknown as Array<Record<string, unknown>>;

    return rows.map((r) => this.mapLifecycleRow(r));
  }

  getLifecycleById(id: number): ServiceLifecycleRow | null {
    const row = this.database
      .prepare('SELECT * FROM crm_service_lifecycle WHERE id = ?')
      .get(id) as unknown as Record<string, unknown> | undefined;
    return row ? this.mapLifecycleRow(row) : null;
  }

  listEvents(lifecycleId: number): ServiceLifecycleEventRow[] {
    const rows = this.database
      .prepare(
        `SELECT * FROM crm_service_lifecycle_events
         WHERE lifecycle_id = ?
         ORDER BY id ASC`,
      )
      .all(lifecycleId) as unknown as Array<Record<string, unknown>>;
    return rows.map((r) => ({
      id: Number(r.id),
      lifecycle_id: Number(r.lifecycle_id),
      from_stage: r.from_stage != null ? String(r.from_stage) : null,
      to_stage: String(r.to_stage ?? ''),
      actor_id: r.actor_id != null ? Number(r.actor_id) : null,
      actor_type: String(r.actor_type ?? ''),
      notes: String(r.notes ?? ''),
      created_at: String(r.created_at ?? ''),
    }));
  }

  leadOwnerStaffId(leadId: number | null): number | null {
    if (!leadId) return null;
    try {
      const row = this.database
        .prepare('SELECT owner_id FROM crm_leads WHERE id = ?')
        .get(leadId) as unknown as { owner_id: number | null } | undefined;
      if (!row?.owner_id) return null;
      const sid = Number(row.owner_id);
      const staff = this.database
        .prepare('SELECT id FROM crm_staff WHERE id = ? AND COALESCE(active, 1) = 1')
        .get(sid) as unknown as { id: number } | undefined;
      return staff ? sid : null;
    } catch {
      return null;
    }
  }

  createDraft(body: CreateServiceLifecycleBody): ServiceLifecycleRow {
    const serviceSlug = String(body.service_slug ?? '').trim();
    let leadId: number | null = null;
    if (body.lead_id != null && body.lead_id !== 0) {
      const lid = Number(body.lead_id);
      if (Number.isFinite(lid) && lid > 0) leadId = lid;
    }
    let customerId: number | null = null;
    if (body.customer_id != null && body.customer_id !== 0) {
      const cid = Number(body.customer_id);
      if (Number.isFinite(cid) && cid > 0) customerId = cid;
    }

    const ownerId = this.leadOwnerStaffId(leadId);
    const ts = catalogTs();

    const result = this.database
      .prepare(
        `INSERT INTO crm_service_lifecycle
           (lead_id, customer_id, service_slug, stage, status,
            assigned_am, stage_entered_at, created_at, updated_at)
         VALUES (?, ?, ?, 'lead', 'draft', ?, ?, ?, ?)`,
      )
      .run(leadId, customerId, serviceSlug, ownerId, ts, ts, ts);

    const lifecycleId = Number(result.lastInsertRowid);
    this.database
      .prepare(
        `INSERT INTO crm_service_lifecycle_events
           (lifecycle_id, from_stage, to_stage, actor_type, notes, created_at)
         VALUES (?, NULL, 'lead', 'human', ?, ?)`,
      )
      .run(lifecycleId, 'Draft tạo bởi human', ts);

    const row = this.getLifecycleById(lifecycleId);
    if (!row) throw new Error('Failed to create lifecycle');
    return row;
  }

  patchLifecycle(id: number, body: PatchServiceLifecycleBody): ServiceLifecycleRow | null {
    const existing = this.getLifecycleById(id);
    if (!existing) return null;

    const ts = catalogTs();
    let stage = existing.stage;
    let notes = existing.notes;
    let serviceSlug = existing.service_slug;

    if ('service_slug' in body && body.service_slug != null) {
      serviceSlug = String(body.service_slug).trim();
    }
    if ('notes' in body && typeof body.notes === 'string') {
      notes = body.notes.trim().slice(0, 2000);
    }

    if ('stage' in body && body.stage != null) {
      const toStage = String(body.stage).trim();
      const fromStage = existing.stage;
      if (toStage !== fromStage) {
        stage = toStage;
        this.database
          .prepare(
            `UPDATE crm_service_lifecycle
             SET stage = ?, stage_entered_at = ?, updated_at = ?, service_slug = ?, notes = ?
             WHERE id = ?`,
          )
          .run(stage, ts, ts, serviceSlug, notes, id);
        this.database
          .prepare(
            `INSERT INTO crm_service_lifecycle_events
               (lifecycle_id, from_stage, to_stage, actor_type, notes, created_at)
             VALUES (?, ?, ?, 'human', ?, ?)`,
          )
          .run(id, fromStage, toStage, notes, ts);
      } else {
        this.database
          .prepare(
            `UPDATE crm_service_lifecycle
             SET updated_at = ?, service_slug = ?, notes = ?
             WHERE id = ?`,
          )
          .run(ts, serviceSlug, notes, id);
      }
    } else {
      let assignedAm = existing.assigned_am;
      let assignedSp = existing.assigned_sp;
      if ('assigned_am' in body) {
        assignedAm =
          body.assigned_am != null && Number(body.assigned_am) > 0 ? Number(body.assigned_am) : null;
      }
      if ('assigned_sp' in body) {
        assignedSp =
          body.assigned_sp != null && Number(body.assigned_sp) > 0 ? Number(body.assigned_sp) : null;
      }
      this.database
        .prepare(
          `UPDATE crm_service_lifecycle
           SET updated_at = ?, service_slug = ?, notes = ?, assigned_am = ?, assigned_sp = ?
           WHERE id = ?`,
        )
        .run(ts, serviceSlug, notes, assignedAm, assignedSp, id);
    }

    return this.getLifecycleById(id);
  }

  getOfficialMarketingPlan(lifecycleId: number): Record<string, unknown> | null {
    const lc = this.getLifecycleById(lifecycleId);
    if (!lc?.marketing_plan_id) return null;
    const row = this.database
      .prepare('SELECT * FROM crm_marketing_plans WHERE id = ?')
      .get(lc.marketing_plan_id) as Record<string, unknown> | undefined;
    return row ?? null;
  }

  createExpense(lifecycleId: number, body: Record<string, unknown>): Record<string, unknown> {
    return createLifecycleExpense(this.database, lifecycleId, body);
  }

  presalesSummary(lifecycleId: number): Record<string, unknown> {
    return listPresalesSummary(this.database, lifecycleId);
  }

  updateOfficialMarketingPlan(planId: number, patch: Record<string, unknown>): Record<string, unknown> | null {
    const ts = catalogTs();
    const sets: string[] = ['updated_at = ?'];
    const params: (string | number)[] = [ts];
    if (patch.north_star != null) {
      sets.push('north_star = ?');
      params.push(String(patch.north_star).slice(0, 4000));
    }
    if (patch.objectives != null) {
      sets.push('objectives = ?');
      params.push(String(patch.objectives).slice(0, 4000));
    }
    if (patch.strategy_framework_json != null) {
      sets.push('strategy_framework_json = ?');
      params.push(String(patch.strategy_framework_json));
    }
    if (patch.target_market_prof_json != null) {
      sets.push('target_market_prof_json = ?');
      params.push(String(patch.target_market_prof_json));
    }
    params.push(planId);
    this.database.prepare(`UPDATE crm_marketing_plans SET ${sets.join(', ')} WHERE id = ?`).run(...params);
    return this.database.prepare('SELECT * FROM crm_marketing_plans WHERE id = ?').get(planId) as
      | Record<string, unknown>
      | undefined ?? null;
  }

  private staffDisplayName(staffId: number | null): string {
    if (!staffId) return '';
    try {
      const row = this.database
        .prepare(`SELECT name, email FROM crm_staff WHERE id = ? LIMIT 1`)
        .get(staffId) as { name: string; email: string } | undefined;
      if (!row) return `#${staffId}`;
      return String(row.name || row.email || `#${staffId}`);
    } catch {
      return `#${staffId}`;
    }
  }

  getLifecycleContext(lifecycleId: number): LifecycleContextDto | null {
    const lc = this.getLifecycleById(lifecycleId);
    if (!lc) return null;

    let leadFullName = '';
    let ownerId: number | null = null;
    if (lc.lead_id) {
      const lead = this.database
        .prepare(`SELECT full_name, owner_id FROM crm_leads WHERE id = ?`)
        .get(lc.lead_id) as { full_name: string; owner_id: number | null } | undefined;
      if (lead) {
        leadFullName = String(lead.full_name ?? '');
        ownerId = lead.owner_id != null ? Number(lead.owner_id) : null;
      }
    }

    let presalesId: number | null = null;
    let assignedSp: number | null = null;
    if (lc.lead_id) {
      const ps = this.database
        .prepare(`SELECT id, assigned_sp FROM crm_lead_presales WHERE lead_id = ? LIMIT 1`)
        .get(lc.lead_id) as { id: number; assigned_sp: number | null } | undefined;
      if (ps) {
        presalesId = Number(ps.id);
        assignedSp = ps.assigned_sp != null ? Number(ps.assigned_sp) : null;
      }
    }

    let contractTitle = '';
    let contractAmount = 0;
    let agencyClientId = '';
    let campaignId: number | null = null;
    if (lc.contract_id) {
      const ct = this.database
        .prepare(
          `SELECT title, amount_vnd, agency_client_id, campaign_id FROM crm_contracts WHERE id = ? LIMIT 1`,
        )
        .get(lc.contract_id) as Record<string, unknown> | undefined;
      if (ct) {
        contractTitle = String(ct.title ?? '');
        contractAmount = Number(ct.amount_vnd ?? 0);
        agencyClientId = String(ct.agency_client_id ?? '').trim();
        campaignId = ct.campaign_id != null ? Number(ct.campaign_id) : null;
      }
    }

    let campaignName = '';
    let campaignCode = '';
    if (campaignId) {
      try {
        const camp = this.database
          .prepare(`SELECT name, code FROM crm_campaigns WHERE id = ? LIMIT 1`)
          .get(campaignId) as { name: string; code: string } | undefined;
        if (camp) {
          campaignName = String(camp.name ?? '');
          campaignCode = String(camp.code ?? '');
        }
      } catch {
        /* optional table */
      }
    }

    const agencyLink = agencyClientId
      ? `/agency/clients/${encodeURIComponent(agencyClientId)}?tab=contracts`
      : null;
    const hubLink =
      agencyClientId && campaignId
        ? `/crm/hub?client_id=${encodeURIComponent(agencyClientId)}`
        : agencyClientId
          ? `/crm/hub?client_id=${encodeURIComponent(agencyClientId)}`
          : null;

    return {
      lifecycle_id: lc.id,
      lead_id: lc.lead_id,
      customer_id: lc.customer_id,
      contract_id: lc.contract_id,
      service_slug: lc.service_slug,
      stage: lc.stage,
      status: lc.status,
      lead: {
        id: lc.lead_id,
        full_name: leadFullName,
        owner_id: ownerId,
        owner_name: this.staffDisplayName(ownerId),
      },
      presales: {
        id: presalesId,
        assigned_sp: assignedSp,
        assigned_sp_name: this.staffDisplayName(assignedSp),
      },
      contract: {
        id: lc.contract_id,
        title: contractTitle,
        amount_vnd: contractAmount,
        agency_client_id: agencyClientId,
        campaign_id: campaignId,
      },
      campaign: {
        id: campaignId,
        name: campaignName,
        code: campaignCode,
      },
      links: {
        service_delivery: `/crm/service-delivery/${lc.id}`,
        lead: lc.lead_id ? `/crm/leads/${lc.lead_id}` : null,
        agency_client: agencyLink,
        hub: hubLink,
      },
    };
  }

  funnelStats(): Record<string, number> {
    const rows = this.database
      .prepare(
        `SELECT stage, COUNT(*) AS c FROM crm_service_lifecycle
         WHERE status = 'active' GROUP BY stage`,
      )
      .all() as Array<{ stage: string; c: number }>;
    const out: Record<string, number> = {};
    for (const r of rows) out[String(r.stage)] = Number(r.c);
    return out;
  }

  advanceStage(
    id: number,
    toStage: string,
    notes: string,
    actorType = 'human',
  ): ServiceLifecycleRow | null {
    const existing = this.getLifecycleById(id);
    if (!existing) return null;
    const ts = catalogTs();
    const fromStage = existing.stage;
    this.database
      .prepare(
        `UPDATE crm_service_lifecycle
         SET stage = ?, stage_entered_at = ?, updated_at = ?, notes = ?
         WHERE id = ?`,
      )
      .run(toStage, ts, ts, notes, id);
    this.database
      .prepare(
        `INSERT INTO crm_service_lifecycle_events
           (lifecycle_id, from_stage, to_stage, actor_type, notes, created_at)
         VALUES (?, ?, ?, ?, ?, ?)`,
      )
      .run(id, fromStage, toStage, actorType, notes, ts);
    return this.getLifecycleById(id);
  }

  private mapLifecycleRow(row: Record<string, unknown>): ServiceLifecycleRow {
    return {
      id: Number(row.id),
      lead_id: row.lead_id != null ? Number(row.lead_id) : null,
      customer_id: row.customer_id != null ? Number(row.customer_id) : null,
      contract_id: row.contract_id != null ? Number(row.contract_id) : null,
      service_slug: String(row.service_slug ?? ''),
      stage: String(row.stage ?? ''),
      status: String(row.status ?? ''),
      assigned_am: row.assigned_am != null ? Number(row.assigned_am) : null,
      assigned_sp: row.assigned_sp != null ? Number(row.assigned_sp) : null,
      stage_entered_at: String(row.stage_entered_at ?? ''),
      notes: String(row.notes ?? ''),
      marketing_plan_id:
        row.marketing_plan_id != null ? Number(row.marketing_plan_id) : null,
      created_at: String(row.created_at ?? ''),
      updated_at: String(row.updated_at ?? ''),
    };
  }
}
