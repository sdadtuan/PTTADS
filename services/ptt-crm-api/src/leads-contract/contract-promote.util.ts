import type { DatabaseSync } from 'node:sqlite';
import { PRESALES_STAGES } from '../leads-funnel/leads-funnel.types';
import { validatePreliminaryPlan } from '../leads-funnel/presales-marketing-plan.util';
import { linkPresalesExpensesToLifecycle } from '../service-lifecycle/lifecycle-finance.util';
import { seedPostOnboardLifecycleTasks } from './lifecycle-tasks-seed.util';

export class ContractPromoteUtil {
  run(
    db: DatabaseSync,
    contractId: number,
    leadId: number,
    actor: string,
    ts: string,
  ): { lifecycle_id: number; customer_id: number; case_id: number | null } {
    db.exec('BEGIN');
    try {
      const contract = db.prepare('SELECT * FROM crm_contracts WHERE id = ?').get(contractId) as
        | Record<string, unknown>
        | undefined;
      if (!contract) throw new Error('Không tìm thấy hợp đồng');

      const ps = db.prepare('SELECT * FROM crm_lead_presales WHERE lead_id = ?').get(leadId) as
        | Record<string, unknown>
        | undefined;
      if (!ps) throw new Error('Lead chưa có pre-sales');
      const presalesId = Number(ps.id);
      if (String(ps.status) === 'converted' && ps.lifecycle_id) {
        db.exec('COMMIT');
        return {
          lifecycle_id: Number(ps.lifecycle_id),
          customer_id: Number(contract.customer_id),
          case_id: contract.case_id != null ? Number(contract.case_id) : null,
        };
      }

      for (const stage of PRESALES_STAGES) {
        const pending = db
          .prepare(
            `SELECT COUNT(*) AS c FROM crm_lead_presales_tasks
             WHERE presales_id = ? AND stage = ? AND is_custom = 0 AND is_done = 0`,
          )
          .get(presalesId, stage) as { c: number };
        if (Number(pending.c) > 0) throw new Error(`Chưa hoàn thành task giai đoạn ${stage}`);
      }

      const plan = db
        .prepare(
          `SELECT * FROM crm_marketing_plans WHERE presales_id = ? AND plan_kind = 'preliminary' ORDER BY id DESC LIMIT 1`,
        )
        .get(presalesId) as Record<string, unknown> | undefined;
      const planGate = validatePreliminaryPlan(plan ?? null);
      if (!planGate.ok) throw new Error(planGate.messages[0] ?? 'KH MKT sơ bộ chưa đủ');

      const convert = this.convertLeadToCrm(db, leadId, actor, ts);
      db.prepare(
        `UPDATE crm_contracts SET customer_id = ?, case_id = COALESCE(?, case_id), status = 'active', signed_on = ?, updated_at = ? WHERE id = ?`,
      ).run(convert.customer_id, convert.case_id, ts.slice(0, 10), ts, contractId);

      const lifecycleId = this.promotePresalesToLifecycle(
        db,
        presalesId,
        convert.customer_id,
        contractId,
        actor,
        ts,
      );

      db.prepare(`UPDATE crm_leads SET status = 'won', updated_at = ?, updated_by = ? WHERE id = ?`).run(
        ts,
        actor.slice(0, 120),
        leadId,
      );

      const placeholderId = Number(contract.customer_id);
      if (placeholderId !== convert.customer_id) this.deletePlaceholderIfOrphan(db, placeholderId);

      db.exec('COMMIT');
      return { lifecycle_id: lifecycleId, customer_id: convert.customer_id, case_id: convert.case_id };
    } catch (err) {
      db.exec('ROLLBACK');
      throw err;
    }
  }

  private convertLeadToCrm(
    db: DatabaseSync,
    leadId: number,
    actor: string,
    ts: string,
  ): { customer_id: number; case_id: number | null } {
    const ld = db
      .prepare(
        `SELECT full_name, phone, email, owner_id, converted_customer_id, converted_case_id FROM crm_leads WHERE id = ?`,
      )
      .get(leadId) as Record<string, unknown> | undefined;
    if (!ld) throw new Error('Không tìm thấy lead');
    if (ld.converted_case_id) {
      return { customer_id: Number(ld.converted_customer_id), case_id: Number(ld.converted_case_id) };
    }
    const name = String(ld.full_name ?? '').trim();
    if (!name) throw new Error('Lead thiếu họ tên');

    let custId = this.findExistingCustomer(db, String(ld.phone ?? ''), String(ld.email ?? ''));
    if (!custId) {
      custId = Number(
        db
          .prepare(
            `INSERT INTO crm_customers (name, phone, email, address, company, created_at, is_placeholder)
             VALUES (?, ?, ?, '', '', ?, 0)`,
          )
          .run(name.slice(0, 240), String(ld.phone ?? '').slice(0, 80), String(ld.email ?? '').slice(0, 240), ts.slice(0, 10))
          .lastInsertRowid,
      );
    }

    const caseId = Number(
      db
        .prepare(
          `INSERT INTO crm_cases (
             customer_id, title, description, channel, priority, status,
             assigned_staff_id, assigned_at, created_at, updated_at, pipeline_stage, stage_entered_at
           ) VALUES (?, ?, ?, 'khac', 'binh_thuong', 'moi', ?, ?, ?, ?, 'chot', ?)`,
        )
        .run(
          custId,
          `Lead #${leadId} — ${name}`.slice(0, 800),
          `Chuyển từ Lead #${leadId}`,
          ld.owner_id != null ? Number(ld.owner_id) : null,
          ld.owner_id ? ts : '',
          ts,
          ts,
          ts,
        ).lastInsertRowid,
    );

    db.prepare(
      `UPDATE crm_leads SET converted_customer_id = ?, converted_case_id = ?, updated_at = ?, updated_by = ? WHERE id = ?`,
    ).run(custId, caseId, ts, actor.slice(0, 120), leadId);

    return { customer_id: custId, case_id: caseId };
  }

  private findExistingCustomer(db: DatabaseSync, phone: string, email: string): number | null {
    const ph = phone.replace(/[\s\-.]/g, '');
    if (ph.length >= 8) {
      const hit = db
        .prepare(
          `SELECT id FROM crm_customers WHERE REPLACE(REPLACE(REPLACE(COALESCE(phone,''),' ',''),'-',''),'.','') = ?
           AND COALESCE(is_placeholder, 0) = 0 ORDER BY id ASC LIMIT 1`,
        )
        .get(ph) as { id: number } | undefined;
      if (hit) return Number(hit.id);
    }
    const em = email.trim().toLowerCase();
    if (em.includes('@')) {
      const hit = db
        .prepare(
          `SELECT id FROM crm_customers WHERE lower(trim(email)) = ? AND COALESCE(is_placeholder, 0) = 0 ORDER BY id ASC LIMIT 1`,
        )
        .get(em) as { id: number } | undefined;
      if (hit) return Number(hit.id);
    }
    return null;
  }

  private promotePresalesToLifecycle(
    db: DatabaseSync,
    presalesId: number,
    customerId: number,
    contractId: number,
    actor: string,
    ts: string,
  ): number {
    const ps = db.prepare('SELECT * FROM crm_lead_presales WHERE id = ?').get(presalesId) as Record<string, unknown>;
    const leadId = Number(ps.lead_id);
    const serviceSlug = String(ps.service_slug ?? '');
    const owner = db.prepare('SELECT owner_id FROM crm_leads WHERE id = ?').get(leadId) as { owner_id: number | null } | undefined;
    const assignedAm: number | null =
      ps.assigned_am != null ? Number(ps.assigned_am) : owner?.owner_id != null ? Number(owner.owner_id) : null;

    const lifecycleId = Number(
      db
        .prepare(
          `INSERT INTO crm_service_lifecycle
             (lead_id, customer_id, contract_id, service_slug, stage, status, assigned_am, stage_entered_at, notes, created_at, updated_at)
           VALUES (?, ?, ?, ?, 'onboard', 'active', ?, ?, ?, ?, ?)`,
        )
        .run(
          leadId,
          customerId,
          contractId,
          serviceSlug,
          assignedAm,
          ts,
          `Promote từ pre-sales #${presalesId} — ${actor}`.slice(0, 4000),
          ts,
          ts,
        ).lastInsertRowid,
    );

    db.prepare(
      `INSERT INTO crm_service_lifecycle_events (lifecycle_id, from_stage, to_stage, actor_type, notes, created_at)
       VALUES (?, 'proposal', 'onboard', 'system', ?, ?)`,
    ).run(lifecycleId, `Ký HĐ #${contractId}`, ts);

    const srcTasks = db
      .prepare(`SELECT * FROM crm_lead_presales_tasks WHERE presales_id = ? ORDER BY stage, step_index, id`)
      .all(presalesId) as Array<Record<string, unknown>>;
    for (const src of srcTasks) {
      db.prepare(
        `INSERT INTO crm_svc_tasks
           (lifecycle_id, stage, step_index, title, description, ai_prompt_key, form_fields, form_data,
            ai_output, is_done, done_at, done_by, notes, is_custom, created_at, updated_at)
         VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)`,
      ).run(
        lifecycleId,
        String(src.stage ?? ''),
        Number(src.step_index ?? 0),
        String(src.title ?? ''),
        String(src.description ?? ''),
        String(src.ai_prompt_key ?? ''),
        String(src.form_fields ?? '[]'),
        String(src.form_data ?? '{}'),
        String(src.ai_output ?? ''),
        Number(src.is_done ?? 0),
        String(src.done_at ?? ''),
        src.done_by != null ? Number(src.done_by) : null,
        String(src.notes ?? ''),
        Number(src.is_custom ?? 0),
        ts,
        ts,
      );
    }

    seedPostOnboardLifecycleTasks(db, lifecycleId, serviceSlug, ts);
    this.clonePreliminaryToOfficial(db, presalesId, lifecycleId, ts);
    linkPresalesExpensesToLifecycle(db, presalesId, lifecycleId);

    db.prepare(
      `UPDATE crm_lead_intake_sessions SET lifecycle_id = ? WHERE lead_id = ? AND (lifecycle_id IS NULL OR lifecycle_id = 0)`,
    ).run(lifecycleId, leadId);
    db.prepare(`UPDATE crm_lead_presales SET status = 'converted', lifecycle_id = ?, updated_at = ? WHERE id = ?`).run(
      lifecycleId,
      ts,
      presalesId,
    );

    return lifecycleId;
  }

  private clonePreliminaryToOfficial(
    db: DatabaseSync,
    presalesId: number,
    lifecycleId: number,
    ts: string,
  ): void {
    const draft = db
      .prepare(
        `SELECT * FROM crm_marketing_plans WHERE presales_id = ? AND plan_kind = 'preliminary' ORDER BY id DESC LIMIT 1`,
      )
      .get(presalesId) as Record<string, unknown> | undefined;
    if (!draft) throw new Error('Thiếu Kế hoạch MKT sơ bộ');
    const gate = validatePreliminaryPlan(draft);
    if (!gate.ok) throw new Error(gate.messages[0] ?? 'KH MKT sơ bộ chưa đủ');
    let name = String(draft.name ?? '').trim();
    if (!name.endsWith('(chính thức)')) name = `${name} (chính thức)`.slice(0, 200);
    const insert = db.prepare(
      `INSERT INTO crm_marketing_plans (
         code, name, status, plan_kind, lead_id, presales_id, lifecycle_id, source_plan_id,
         north_star, objectives, notes, strategy_framework_json, target_market_prof_json,
         target_market_steps4_json, created_at, updated_at
       )
       SELECT ?, ?, 'draft', 'official', lead_id, presales_id, ?, id,
              north_star, objectives, notes, strategy_framework_json, target_market_prof_json,
              target_market_steps4_json, ?, ?
       FROM crm_marketing_plans WHERE id = ?`,
    ).run(`LC-${lifecycleId}-OFFICIAL`, name, lifecycleId, ts, ts, Number(draft.id));
    const officialId = Number(insert.lastInsertRowid);
    db.prepare(`UPDATE crm_service_lifecycle SET marketing_plan_id = ?, updated_at = ? WHERE id = ?`).run(
      officialId,
      ts,
      lifecycleId,
    );
  }

  private deletePlaceholderIfOrphan(db: DatabaseSync, customerId: number): void {
    const row = db.prepare('SELECT is_placeholder FROM crm_customers WHERE id = ?').get(customerId) as
      | { is_placeholder: number }
      | undefined;
    if (!row || !Number(row.is_placeholder)) return;
    const nCt = (db.prepare('SELECT COUNT(*) AS n FROM crm_contracts WHERE customer_id = ?').get(customerId) as { n: number }).n;
    if (Number(nCt) > 0) return;
    const nCs = (db.prepare('SELECT COUNT(*) AS n FROM crm_cases WHERE customer_id = ?').get(customerId) as { n: number }).n;
    if (Number(nCs) > 0) return;
    db.prepare('DELETE FROM crm_customers WHERE id = ?').run(customerId);
  }
}
