import { Injectable, OnModuleDestroy } from '@nestjs/common';
import { DatabaseSync } from 'node:sqlite';
import { catalogTs } from '../catalog/catalog-slug.util';
import { AppConfigService } from '../config/app-config.service';
import { assertPresalesCareGate, parseLeadMeta } from '../leads-funnel/care-pipeline.util';
import { PRESALES_STAGES } from '../leads-funnel/leads-funnel.types';
import { validatePreliminaryPlan } from '../leads-funnel/presales-marketing-plan.util';
import { buildReadinessChecks } from './contract-readiness.util';
import { ContractPromoteUtil } from './contract-promote.util';
import type {
  ApprovalStatus,
  ContractApprovalRow,
  ContractReadiness,
  ContractRow,
  CreateContractBody,
  PatchContractBody,
} from './contract.types';
import { ensureSvcTasksSchema } from './lifecycle-tasks-seed.util';
import { inferBillingType, SERVICE_LABELS } from './lifecycle-workflow-steps.util';

@Injectable()
export class LeadsContractSqliteRepository implements OnModuleDestroy {
  private db: DatabaseSync | null = null;
  private readonly promoteUtil = new ContractPromoteUtil();

  constructor(private readonly config: AppConfigService) {}

  private get database(): DatabaseSync {
    if (!this.db) {
      this.db = new DatabaseSync(this.config.sqlitePath);
      this.db.exec('PRAGMA foreign_keys = ON');
      this.ensureSchema();
    }
    return this.db;
  }

  onModuleDestroy(): void {
    if (this.db) {
      this.db.close();
      this.db = null;
    }
  }

  private ts(): string {
    return catalogTs();
  }

  ensureSchema(): void {
    const db = this.database;
    db.exec(`
      CREATE TABLE IF NOT EXISTS crm_customers (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT NOT NULL DEFAULT '',
        phone TEXT NOT NULL DEFAULT '',
        email TEXT NOT NULL DEFAULT '',
        address TEXT NOT NULL DEFAULT '',
        company TEXT NOT NULL DEFAULT '',
        created_at TEXT NOT NULL DEFAULT ''
      )
    `);
    db.exec(`
      CREATE TABLE IF NOT EXISTS crm_cases (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        customer_id INTEGER NOT NULL,
        title TEXT NOT NULL DEFAULT '',
        description TEXT NOT NULL DEFAULT '',
        channel TEXT NOT NULL DEFAULT 'khac',
        priority TEXT NOT NULL DEFAULT 'binh_thuong',
        status TEXT NOT NULL DEFAULT 'moi',
        assigned_to TEXT NOT NULL DEFAULT '',
        assigned_staff_id INTEGER,
        assigned_at TEXT NOT NULL DEFAULT '',
        created_at TEXT NOT NULL DEFAULT '',
        updated_at TEXT NOT NULL DEFAULT '',
        pipeline_stage TEXT NOT NULL DEFAULT 'moi',
        stage_entered_at TEXT NOT NULL DEFAULT '',
        lead_source TEXT NOT NULL DEFAULT ''
      )
    `);
    db.exec(`
      CREATE TABLE IF NOT EXISTS crm_contracts (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        customer_id INTEGER NOT NULL,
        case_id INTEGER,
        campaign_id INTEGER,
        reference_code TEXT NOT NULL DEFAULT '',
        title TEXT NOT NULL,
        status TEXT NOT NULL DEFAULT 'draft',
        signed_on TEXT NOT NULL DEFAULT '',
        starts_on TEXT NOT NULL DEFAULT '',
        ends_on TEXT NOT NULL DEFAULT '',
        amount_vnd INTEGER NOT NULL DEFAULT 0,
        renewal_reminder_days INTEGER NOT NULL DEFAULT 30,
        notes TEXT NOT NULL DEFAULT '',
        created_at TEXT NOT NULL DEFAULT '',
        updated_at TEXT NOT NULL DEFAULT ''
      )
    `);
    const contractCols = new Set(
      (db.prepare('PRAGMA table_info(crm_contracts)').all() as Array<{ name: string }>).map((c) => c.name),
    );
    for (const [col, ddl] of [
      ['lead_id', 'ALTER TABLE crm_contracts ADD COLUMN lead_id INTEGER'],
      ['service_slug', "ALTER TABLE crm_contracts ADD COLUMN service_slug TEXT NOT NULL DEFAULT ''"],
      ['agency_client_id', "ALTER TABLE crm_contracts ADD COLUMN agency_client_id TEXT NOT NULL DEFAULT ''"],
      ['billing_type', "ALTER TABLE crm_contracts ADD COLUMN billing_type TEXT NOT NULL DEFAULT 'one_off'"],
    ] as const) {
      if (!contractCols.has(col)) db.exec(ddl);
    }
    const custCols = new Set(
      (db.prepare('PRAGMA table_info(crm_customers)').all() as Array<{ name: string }>).map((c) => c.name),
    );
    if (!custCols.has('is_placeholder')) {
      db.exec('ALTER TABLE crm_customers ADD COLUMN is_placeholder INTEGER NOT NULL DEFAULT 0');
    }
    if (!custCols.has('placeholder_lead_id')) {
      db.exec('ALTER TABLE crm_customers ADD COLUMN placeholder_lead_id INTEGER');
    }
    db.exec(`
      CREATE TABLE IF NOT EXISTS crm_contract_approvals (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        contract_id INTEGER NOT NULL,
        lead_id INTEGER NOT NULL,
        status TEXT NOT NULL DEFAULT 'pending',
        requested_by TEXT NOT NULL DEFAULT '',
        decided_by TEXT NOT NULL DEFAULT '',
        amount_vnd INTEGER NOT NULL DEFAULT 0,
        notes TEXT NOT NULL DEFAULT '',
        decision_notes TEXT NOT NULL DEFAULT '',
        created_at TEXT NOT NULL DEFAULT '',
        decided_at TEXT NOT NULL DEFAULT ''
      )
    `);
    db.exec(`
      CREATE TABLE IF NOT EXISTS crm_contract_events (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        contract_id INTEGER NOT NULL,
        event_type TEXT NOT NULL DEFAULT '',
        actor TEXT NOT NULL DEFAULT '',
        payload_json TEXT NOT NULL DEFAULT '{}',
        created_at TEXT NOT NULL DEFAULT ''
      )
    `);
    db.exec(`
      CREATE TABLE IF NOT EXISTS crm_service_lifecycle (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        lead_id INTEGER,
        customer_id INTEGER,
        contract_id INTEGER,
        service_slug TEXT NOT NULL DEFAULT '',
        stage TEXT NOT NULL DEFAULT 'lead',
        status TEXT NOT NULL DEFAULT 'draft',
        assigned_am INTEGER,
        assigned_sp INTEGER,
        stage_entered_at TEXT NOT NULL DEFAULT '',
        notes TEXT NOT NULL DEFAULT '',
        created_at TEXT NOT NULL DEFAULT '',
        updated_at TEXT NOT NULL DEFAULT ''
      )
    `);
    db.exec(`
      CREATE TABLE IF NOT EXISTS crm_service_lifecycle_events (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        lifecycle_id INTEGER NOT NULL,
        from_stage TEXT,
        to_stage TEXT NOT NULL,
        actor_id INTEGER,
        actor_type TEXT NOT NULL DEFAULT 'human',
        notes TEXT NOT NULL DEFAULT '',
        created_at TEXT NOT NULL DEFAULT ''
      )
    `);
    ensureSvcTasksSchema(db);
    const planCols = new Set(
      (db.prepare('PRAGMA table_info(crm_marketing_plans)').all() as Array<{ name: string }>).map((c) => c.name),
    );
    if (!planCols.has('lifecycle_id')) {
      db.exec('ALTER TABLE crm_marketing_plans ADD COLUMN lifecycle_id INTEGER');
    }
    if (!planCols.has('source_plan_id')) {
      db.exec('ALTER TABLE crm_marketing_plans ADD COLUMN source_plan_id INTEGER');
    }
    const lcCols = new Set(
      (db.prepare('PRAGMA table_info(crm_service_lifecycle)').all() as Array<{ name: string }>).map(
        (c) => c.name,
      ),
    );
    if (!lcCols.has('marketing_plan_id')) {
      db.exec('ALTER TABLE crm_service_lifecycle ADD COLUMN marketing_plan_id INTEGER');
    }
    if (!lcCols.has('sop_run_id')) {
      db.exec('ALTER TABLE crm_service_lifecycle ADD COLUMN sop_run_id INTEGER');
    }
  }

  mapContract(row: Record<string, unknown>): ContractRow {
    return {
      id: Number(row.id),
      customer_id: Number(row.customer_id),
      lead_id: row.lead_id != null ? Number(row.lead_id) : null,
      case_id: row.case_id != null ? Number(row.case_id) : null,
      agency_client_id: String(row.agency_client_id ?? ''),
      title: String(row.title ?? ''),
      status: String(row.status ?? 'draft') as ContractRow['status'],
      amount_vnd: Number(row.amount_vnd ?? 0),
      service_slug: String(row.service_slug ?? ''),
      signed_on: String(row.signed_on ?? ''),
      notes: String(row.notes ?? ''),
      created_at: String(row.created_at ?? ''),
      updated_at: String(row.updated_at ?? ''),
    };
  }

  mapApproval(row: Record<string, unknown>): ContractApprovalRow {
    return {
      id: Number(row.id),
      contract_id: Number(row.contract_id),
      lead_id: Number(row.lead_id),
      status: String(row.status ?? 'pending') as ApprovalStatus,
      requested_by: String(row.requested_by ?? ''),
      decided_by: String(row.decided_by ?? ''),
      amount_vnd: Number(row.amount_vnd ?? 0),
      notes: String(row.notes ?? ''),
      decision_notes: String(row.decision_notes ?? ''),
      created_at: String(row.created_at ?? ''),
      decided_at: String(row.decided_at ?? ''),
    };
  }

  logContractEvent(contractId: number, eventType: string, actor: string, payload: unknown = {}): void {
    this.database
      .prepare(
        `INSERT INTO crm_contract_events (contract_id, event_type, actor, payload_json, created_at)
         VALUES (?, ?, ?, ?, ?)`,
      )
      .run(contractId, eventType, actor, JSON.stringify(payload), this.ts());
  }

  private leadAgencyClientId(metaJson: string | null): string {
    const meta = parseLeadMeta(metaJson);
    return String(meta.agency_client_id ?? meta.client_id ?? '').trim();
  }

  private getPresalesProgress(presalesId: number): Record<string, { total: number; done: number }> {
    const rows = this.database
      .prepare('SELECT stage, is_done FROM crm_lead_presales_tasks WHERE presales_id = ?')
      .all(presalesId) as Array<{ stage: string; is_done: number }>;
    const progress: Record<string, { total: number; done: number }> = {};
    for (const stage of PRESALES_STAGES) progress[stage] = { total: 0, done: 0 };
    for (const row of rows) {
      const stage = String(row.stage);
      if (!progress[stage]) progress[stage] = { total: 0, done: 0 };
      progress[stage].total += 1;
      if (Number(row.is_done)) progress[stage].done += 1;
    }
    return progress;
  }

  getReadiness(leadId: number): ContractReadiness {
    const lead = this.database
      .prepare(`SELECT care_stage_current, care_stages_done_json, meta_json FROM crm_leads WHERE id = ?`)
      .get(leadId) as { care_stage_current: string; care_stages_done_json: string; meta_json: string } | undefined;
    if (!lead) throw new Error('Không tìm thấy lead');

    const ps = this.database.prepare('SELECT * FROM crm_lead_presales WHERE lead_id = ?').get(leadId) as
      | Record<string, unknown>
      | undefined;
    const { contract, approval } = this.getContractForLead(leadId);

    let marketingPlan: Record<string, unknown> | null = null;
    if (ps) {
      marketingPlan =
        (this.database
          .prepare(
            `SELECT * FROM crm_marketing_plans WHERE presales_id = ? AND plan_kind = 'preliminary' ORDER BY id DESC LIMIT 1`,
          )
          .get(Number(ps.id)) as Record<string, unknown> | undefined) ?? null;
    }

    const checks = buildReadinessChecks({
      careStageCurrent: String(lead.care_stage_current ?? ''),
      careStagesDoneJson: String(lead.care_stages_done_json ?? '{}'),
      presales: ps
        ? {
            stage: String(ps.stage),
            status: String(ps.status),
            tasksProgress: this.getPresalesProgress(Number(ps.id)),
          }
        : null,
      marketingPlan,
      contract,
      pendingApproval: approval,
    });

    return {
      ok: checks.every((c) => c.ok) && approval?.status !== 'pending',
      checks,
      contract,
      approval,
      lifecycle_id: ps?.lifecycle_id != null ? Number(ps.lifecycle_id) : null,
    };
  }

  getContractForLead(leadId: number): { contract: ContractRow | null; approval: ContractApprovalRow | null } {
    const contractRow = this.database
      .prepare(`SELECT * FROM crm_contracts WHERE lead_id = ? ORDER BY id DESC LIMIT 1`)
      .get(leadId) as Record<string, unknown> | undefined;
    const contract = contractRow ? this.mapContract(contractRow) : null;
    let approval: ContractApprovalRow | null = null;
    if (contract) {
      const appr = this.database
        .prepare(`SELECT * FROM crm_contract_approvals WHERE contract_id = ? ORDER BY id DESC LIMIT 1`)
        .get(contract.id) as Record<string, unknown> | undefined;
      approval = appr ? this.mapApproval(appr) : null;
    }
    return { contract, approval };
  }

  createDraftContract(leadId: number, body: CreateContractBody, actor: string): ContractRow {
    const lead = this.database
      .prepare(
        `SELECT id, full_name, meta_json, care_stage_current, care_stages_done_json FROM crm_leads WHERE id = ?`,
      )
      .get(leadId) as Record<string, unknown> | undefined;
    if (!lead) throw new Error('Không tìm thấy lead');
    assertPresalesCareGate(String(lead.care_stage_current), String(lead.care_stages_done_json));

    const ps = this.database.prepare('SELECT * FROM crm_lead_presales WHERE lead_id = ?').get(leadId) as
      | Record<string, unknown>
      | undefined;
    if (!ps) throw new Error('Chưa có pre-sales');
    if (String(ps.status) !== 'active') throw new Error('Pre-sales không còn active');

    const existing = this.database
      .prepare(`SELECT * FROM crm_contracts WHERE lead_id = ? AND status = 'draft' ORDER BY id DESC LIMIT 1`)
      .get(leadId) as Record<string, unknown> | undefined;
    if (existing) return this.mapContract(existing);

    const slug = String(ps.service_slug ?? '').trim();
    if (!slug) throw new Error('Pre-sales thiếu service_slug');

    const ts = this.ts();
    const placeholderId = this.ensurePlaceholderCustomer(leadId, String(lead.full_name ?? ''), ts);
    const svcLabel = SERVICE_LABELS[slug] ?? slug;
    const leadName = String(lead.full_name ?? '').trim() || `#${leadId}`;
    const title = String(body.title ?? '').trim() || `${svcLabel} — Lead #${leadId} ${leadName}`.slice(0, 500);
    const amount = Math.max(0, Math.min(Number(body.amount_vnd ?? 0) || 0, 9_999_999_999_999));
    const noteLine = String(body.notes ?? '').trim();

    const result = this.database
      .prepare(
        `INSERT INTO crm_contracts (
           customer_id, lead_id, title, status, amount_vnd, service_slug, agency_client_id,
           billing_type, notes, created_at, updated_at
         ) VALUES (?, ?, ?, 'draft', ?, ?, ?, ?, ?, ?, ?)`,
      )
      .run(
        placeholderId,
        leadId,
        title,
        amount,
        slug,
        this.leadAgencyClientId(String(lead.meta_json ?? '')),
        inferBillingType(slug),
        noteLine,
        ts,
        ts,
      );
    const contractId = Number(result.lastInsertRowid);
    this.logContractEvent(contractId, 'draft_created', actor, { lead_id: leadId });
    return this.mapContract(
      this.database.prepare('SELECT * FROM crm_contracts WHERE id = ?').get(contractId) as Record<string, unknown>,
    );
  }

  private ensurePlaceholderCustomer(leadId: number, fullName: string, ts: string): number {
    const existing = this.database
      .prepare(
        `SELECT id FROM crm_customers WHERE placeholder_lead_id = ? AND COALESCE(is_placeholder, 0) = 1 ORDER BY id DESC LIMIT 1`,
      )
      .get(leadId) as { id: number } | undefined;
    if (existing) return Number(existing.id);
    const name = `[Lead #${leadId}] Chưa ký — ${String(fullName || 'Lead').trim()}`.slice(0, 240);
    const result = this.database
      .prepare(
        `INSERT INTO crm_customers (name, phone, email, address, company, created_at, is_placeholder, placeholder_lead_id)
         VALUES (?, '', '', '', '', ?, 1, ?)`,
      )
      .run(name, ts.slice(0, 10), leadId);
    return Number(result.lastInsertRowid);
  }

  patchContract(contractId: number, leadId: number, body: PatchContractBody): ContractRow {
    const row = this.database.prepare('SELECT * FROM crm_contracts WHERE id = ? AND lead_id = ?').get(contractId, leadId) as
      | Record<string, unknown>
      | undefined;
    if (!row) throw new Error('Không tìm thấy hợp đồng');
    if (String(row.status) !== 'draft') throw new Error('Chỉ sửa được HĐ draft');
    const ts = this.ts();
    this.database
      .prepare(`UPDATE crm_contracts SET title = ?, amount_vnd = ?, notes = ?, updated_at = ? WHERE id = ?`)
      .run(
        body.title != null ? String(body.title).trim().slice(0, 500) : String(row.title),
        body.amount_vnd != null
          ? Math.max(0, Math.min(Number(body.amount_vnd) || 0, 9_999_999_999_999))
          : Number(row.amount_vnd),
        body.notes != null ? String(body.notes).trim().slice(0, 8000) : String(row.notes),
        ts,
        contractId,
      );
    return this.mapContract(
      this.database.prepare('SELECT * FROM crm_contracts WHERE id = ?').get(contractId) as Record<string, unknown>,
    );
  }

  submitForApproval(contractId: number, leadId: number, actor: string, notes: string): ContractApprovalRow {
    const readiness = this.getReadiness(leadId);
    const submitChecks = readiness.checks.filter((c) => c.key !== 'no_pending_approval');
    if (!submitChecks.every((c) => c.ok)) {
      throw new Error(submitChecks.find((c) => !c.ok)?.message ?? 'Chưa đủ điều kiện submit HĐ');
    }
    if (!readiness.contract || readiness.contract.id !== contractId) throw new Error('HĐ không khớp lead');
    if (readiness.approval?.status === 'pending') throw new Error('Đã có yêu cầu duyệt đang chờ');

    const ts = this.ts();
    const result = this.database
      .prepare(
        `INSERT INTO crm_contract_approvals (contract_id, lead_id, status, requested_by, amount_vnd, notes, created_at)
         VALUES (?, ?, 'pending', ?, ?, ?, ?)`,
      )
      .run(contractId, leadId, actor, readiness.contract.amount_vnd, notes.slice(0, 4000), ts);
    const approvalId = Number(result.lastInsertRowid);
    this.logContractEvent(contractId, 'submitted', actor, { approval_id: approvalId });
    return this.mapApproval(
      this.database.prepare('SELECT * FROM crm_contract_approvals WHERE id = ?').get(approvalId) as Record<
        string,
        unknown
      >,
    );
  }

  listPendingApprovals(limit = 50): Array<ContractApprovalRow & { contract_title: string; lead_name: string }> {
    const rows = this.database
      .prepare(
        `SELECT a.*, c.title AS contract_title, l.full_name AS lead_name
         FROM crm_contract_approvals a
         INNER JOIN crm_contracts c ON c.id = a.contract_id
         INNER JOIN crm_leads l ON l.id = a.lead_id
         WHERE a.status = 'pending'
         ORDER BY a.created_at ASC LIMIT ?`,
      )
      .all(limit) as Array<Record<string, unknown>>;
    return rows.map((r) => ({
      ...this.mapApproval(r),
      contract_title: String(r.contract_title ?? ''),
      lead_name: String(r.lead_name ?? ''),
    }));
  }

  listContractsByClient(clientId: string, limit = 50): ContractRow[] {
    const rows = this.database
      .prepare(`SELECT * FROM crm_contracts WHERE agency_client_id = ? ORDER BY updated_at DESC LIMIT ?`)
      .all(clientId.trim(), limit) as Array<Record<string, unknown>>;
    return rows.map((r) => this.mapContract(r));
  }

  rejectApproval(approvalId: number, actor: string, decisionNotes: string): ContractApprovalRow {
    const appr = this.database.prepare('SELECT * FROM crm_contract_approvals WHERE id = ?').get(approvalId) as
      | Record<string, unknown>
      | undefined;
    if (!appr || String(appr.status) !== 'pending') throw new Error('Yêu cầu không hợp lệ');
    const ts = this.ts();
    this.database
      .prepare(
        `UPDATE crm_contract_approvals SET status = 'rejected', decided_by = ?, decision_notes = ?, decided_at = ? WHERE id = ?`,
      )
      .run(actor, decisionNotes.slice(0, 4000), ts, approvalId);
    this.logContractEvent(Number(appr.contract_id), 'rejected', actor, { approval_id: approvalId });
    return this.mapApproval(
      this.database.prepare('SELECT * FROM crm_contract_approvals WHERE id = ?').get(approvalId) as Record<
        string,
        unknown
      >,
    );
  }

  approveAndPromote(
    approvalId: number,
    actor: string,
  ): {
    approval: ContractApprovalRow;
    contract: ContractRow;
    lifecycle_id: number;
    customer_id: number;
    case_id: number | null;
  } {
    const appr = this.database.prepare('SELECT * FROM crm_contract_approvals WHERE id = ?').get(approvalId) as
      | Record<string, unknown>
      | undefined;
    if (!appr || String(appr.status) !== 'pending') throw new Error('Yêu cầu không hợp lệ');

    const contractId = Number(appr.contract_id);
    const leadId = Number(appr.lead_id);
    const ts = this.ts();
    const promote = this.promoteUtil.run(this.database, contractId, leadId, actor, ts);

    this.database
      .prepare(`UPDATE crm_contract_approvals SET status = 'approved', decided_by = ?, decided_at = ? WHERE id = ?`)
      .run(actor, ts, approvalId);
    this.logContractEvent(contractId, 'approved', actor, { approval_id: approvalId });
    this.logContractEvent(contractId, 'activated', actor, { lifecycle_id: promote.lifecycle_id });
    this.logContractEvent(contractId, 'promoted', actor, promote);

    return {
      approval: this.mapApproval(
        this.database.prepare('SELECT * FROM crm_contract_approvals WHERE id = ?').get(approvalId) as Record<
          string,
          unknown
        >,
      ),
      contract: this.mapContract(
        this.database.prepare('SELECT * FROM crm_contracts WHERE id = ?').get(contractId) as Record<string, unknown>,
      ),
      lifecycle_id: promote.lifecycle_id,
      customer_id: promote.customer_id,
      case_id: promote.case_id,
    };
  }
}
