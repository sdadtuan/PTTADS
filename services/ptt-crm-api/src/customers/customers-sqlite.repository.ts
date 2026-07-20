import { Injectable, OnModuleDestroy } from '@nestjs/common';
import { DatabaseSync } from 'node:sqlite';
import { catalogTs } from '../catalog/catalog-slug.util';
import { AppConfigService } from '../config/app-config.service';
import {
  CreateCustomerBody,
  CreateIssueBody,
  CreatePurchaseBody,
  CreateRelationBody,
  CUSTOMER_GENDER_LABELS,
  CUSTOMER_GENDERS,
  CUSTOMER_LEAD_SOURCE_LABELS,
  CUSTOMER_LEAD_SOURCES,
  CustomerBriefRow,
  CustomerDetailStats,
  CustomerIssueRow,
  CustomerPurchaseRow,
  CustomerRelationRow,
  CustomerRow,
  ISSUE_PRIORITY_LABELS,
  ISSUE_STATUS_LABELS,
  ISSUE_TYPE_LABELS,
  normalizeIssuePriority,
  normalizeIssueStatus,
  normalizeIssueType,
  normalizePurchaseStatus,
  normalizeRelationType,
  PatchCustomerBody,
  PatchIssueBody,
  PatchPurchaseBody,
  PatchRelationBody,
  PROFILE_PATCH_KEYS,
  PURCHASE_STATUS_LABELS,
  RELATION_TYPE_LABELS,
} from './customers.types';

interface SqliteCustomerRow {
  id: number;
  name: string;
  phone: string;
  email: string;
  address: string;
  company: string;
  lead_source: string;
  lead_source_note: string;
  date_of_birth: string;
  gender: string;
  id_number: string;
  occupation: string;
  interests: string;
  profile_notes: string;
  created_at: string;
}

@Injectable()
export class CustomersSqliteRepository implements OnModuleDestroy {
  private db: DatabaseSync | null = null;

  constructor(private readonly config: AppConfigService) {}

  private get database(): DatabaseSync {
    if (!this.db) {
      this.db = new DatabaseSync(this.config.sqlitePath);
      this.db.exec('PRAGMA foreign_keys = ON');
      this.ensureBriefSchema();
    }
    return this.db;
  }

  private ensureBriefSchema(): void {
    if (!this.db) return;
    this.db.exec(`
      CREATE TABLE IF NOT EXISTS crm_customer_brief_scans (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        customer_id INTEGER NOT NULL REFERENCES crm_customers(id) ON DELETE CASCADE,
        meeting_purpose TEXT NOT NULL DEFAULT '',
        ai_output TEXT NOT NULL DEFAULT '',
        created_at TEXT NOT NULL DEFAULT ''
      );
      CREATE INDEX IF NOT EXISTS idx_brief_scans_customer
        ON crm_customer_brief_scans (customer_id);
    `);
  }

  onModuleDestroy(): void {
    if (this.db) {
      this.db.close();
      this.db = null;
    }
  }

  listCustomers(q?: string, limit = 200): CustomerRow[] {
    const lim = Math.max(1, Math.min(limit, 500));
    const phClause = ' AND COALESCE(is_placeholder, 0) = 0';
    const qRaw = String(q ?? '').trim().toLowerCase();

    let rows: SqliteCustomerRow[];
    if (qRaw) {
      const like = `%${qRaw}%`;
      rows = this.database
        .prepare(
          `SELECT id, name, phone, email, address, company, lead_source, lead_source_note,
                  date_of_birth, gender, id_number, occupation, interests, profile_notes, created_at
           FROM crm_customers
           WHERE (
             lower(coalesce(trim(name), '')) LIKE ?
             OR lower(coalesce(trim(phone), '')) LIKE ?
             OR lower(coalesce(trim(email), '')) LIKE ?
             OR lower(coalesce(trim(address), '')) LIKE ?
             OR lower(coalesce(trim(company), '')) LIKE ?
           )${phClause}
           ORDER BY id DESC
           LIMIT ?`,
        )
        .all(like, like, like, like, like, lim) as unknown as SqliteCustomerRow[];
    } else {
      rows = this.database
        .prepare(
          `SELECT id, name, phone, email, address, company, lead_source, lead_source_note,
                  date_of_birth, gender, id_number, occupation, interests, profile_notes, created_at
           FROM crm_customers
           WHERE 1=1${phClause}
           ORDER BY id DESC
           LIMIT ?`,
        )
        .all(lim) as unknown as SqliteCustomerRow[];
    }
    return rows.map((r) => this.mapCustomer(r));
  }

  getCustomerById(id: number): CustomerRow | null {
    const row = this.database
      .prepare('SELECT * FROM crm_customers WHERE id = ?')
      .get(id) as unknown as SqliteCustomerRow | undefined;
    return row ? this.mapCustomer(row) : null;
  }

  createCustomer(body: CreateCustomerBody): CustomerRow {
    const ts = catalogTs();
    const leadSource = this.normalizeLeadSource(body.lead_source ?? '');
    const result = this.database
      .prepare(
        `INSERT INTO crm_customers (
           name, phone, email, address, company, lead_source, lead_source_note,
           date_of_birth, gender, id_number, occupation, interests, profile_notes, created_at
         ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)`,
      )
      .run(
        String(body.name ?? '').trim().slice(0, 240),
        String(body.phone ?? '').trim().slice(0, 64),
        String(body.email ?? '').trim().slice(0, 240),
        String(body.address ?? '').trim().slice(0, 500),
        String(body.company ?? '').trim().slice(0, 240),
        leadSource,
        String(body.lead_source_note ?? '').trim().slice(0, 4000),
        String(body.date_of_birth ?? '').trim().slice(0, 32),
        this.normalizeGender(body.gender ?? ''),
        String(body.id_number ?? '').trim().slice(0, 32),
        String(body.occupation ?? '').trim().slice(0, 240),
        String(body.interests ?? '').trim().slice(0, 4000),
        String(body.profile_notes ?? '').trim().slice(0, 4000),
        ts,
      );
    const created = this.getCustomerById(Number(result.lastInsertRowid));
    if (!created) {
      throw new Error('Failed to create customer');
    }
    return created;
  }

  patchCustomer(id: number, body: PatchCustomerBody): CustomerRow | null {
    const existing = this.database
      .prepare('SELECT * FROM crm_customers WHERE id = ?')
      .get(id) as unknown as SqliteCustomerRow | undefined;
    if (!existing) return null;

    const merged: Record<string, string> = {
      name: String(existing.name ?? ''),
      phone: String(existing.phone ?? ''),
      email: String(existing.email ?? ''),
      address: String(existing.address ?? ''),
      company: String(existing.company ?? ''),
      lead_source: String(existing.lead_source ?? ''),
      lead_source_note: String(existing.lead_source_note ?? ''),
      date_of_birth: String(existing.date_of_birth ?? ''),
      gender: String(existing.gender ?? ''),
      id_number: String(existing.id_number ?? ''),
      occupation: String(existing.occupation ?? ''),
      interests: String(existing.interests ?? ''),
      profile_notes: String(existing.profile_notes ?? ''),
    };

    for (const key of PROFILE_PATCH_KEYS) {
      if (!(key in body)) continue;
      const val = body[key];
      if (val === null || val === undefined) {
        merged[key] = '';
        continue;
      }
      if (typeof val !== 'string') continue;
      const s = val.trim();
      if (key === 'phone') merged[key] = s.slice(0, 64);
      else if (key === 'address') merged[key] = s.slice(0, 500);
      else if (key === 'interests' || key === 'profile_notes' || key === 'lead_source_note') {
        merged[key] = s.slice(0, 4000);
      } else if (key === 'id_number' || key === 'date_of_birth') merged[key] = s.slice(0, 32);
      else if (key === 'lead_source') merged[key] = s ? this.normalizeLeadSource(s) : '';
      else if (key === 'gender') merged[key] = s ? this.normalizeGender(s) : '';
      else merged[key] = s.slice(0, 240);
    }

    this.database
      .prepare(
        `UPDATE crm_customers
         SET name = ?, phone = ?, email = ?, address = ?, company = ?,
             lead_source = ?, lead_source_note = ?, date_of_birth = ?, gender = ?,
             id_number = ?, occupation = ?, interests = ?, profile_notes = ?
         WHERE id = ?`,
      )
      .run(
        merged.name,
        merged.phone,
        merged.email,
        merged.address,
        merged.company,
        merged.lead_source,
        merged.lead_source_note,
        merged.date_of_birth,
        merged.gender,
        merged.id_number,
        merged.occupation,
        merged.interests,
        merged.profile_notes,
        id,
      );
    return this.getCustomerById(id);
  }

  fetchRelations(customerId: number): CustomerRelationRow[] {
    const rows = this.database
      .prepare(
        `SELECT * FROM crm_customer_relations
         WHERE customer_id = ?
         ORDER BY id ASC`,
      )
      .all(customerId) as unknown as Array<Record<string, unknown>>;
    return rows.map((d) => {
      const rt = String(d.relation_type ?? '');
      return {
        id: Number(d.id),
        customer_id: Number(d.customer_id),
        relation_type: rt,
        relation_type_label: RELATION_TYPE_LABELS[rt] ?? rt,
        full_name: String(d.full_name ?? ''),
        phone: String(d.phone ?? ''),
        email: String(d.email ?? ''),
        notes: String(d.notes ?? ''),
        created_at: String(d.created_at ?? ''),
        updated_at: String(d.updated_at ?? ''),
      };
    });
  }

  fetchPurchases(customerId: number): CustomerPurchaseRow[] {
    const rows = this.database
      .prepare(
        `SELECT * FROM crm_customer_purchases
         WHERE customer_id = ?
         ORDER BY datetime(COALESCE(NULLIF(order_date,''), created_at)) DESC, id DESC`,
      )
      .all(customerId) as unknown as Array<Record<string, unknown>>;
    return rows.map((d) => {
      const st = String(d.status ?? '');
      return {
        id: Number(d.id),
        customer_id: Number(d.customer_id),
        order_date: String(d.order_date ?? ''),
        product_name: String(d.product_name ?? ''),
        amount_vnd: Number(d.amount_vnd ?? 0),
        quantity: Number(d.quantity ?? 1),
        status: st,
        status_label: PURCHASE_STATUS_LABELS[st] ?? st,
        reference_code: String(d.reference_code ?? ''),
        notes: String(d.notes ?? ''),
        contract_id: d.contract_id != null ? Number(d.contract_id) : null,
        created_at: String(d.created_at ?? ''),
        updated_at: String(d.updated_at ?? ''),
      };
    });
  }

  fetchIssues(customerId: number): CustomerIssueRow[] {
    const rows = this.database
      .prepare(
        `SELECT i.*, st.name AS assigned_staff_name
         FROM crm_customer_issues i
         LEFT JOIN crm_staff st ON st.id = i.assigned_staff_id
         WHERE i.customer_id = ?
         ORDER BY CASE i.status WHEN 'moi' THEN 0 WHEN 'dang_xu_ly' THEN 1 WHEN 'cho_khach' THEN 2 ELSE 9 END,
                  i.id DESC`,
      )
      .all(customerId) as unknown as Array<Record<string, unknown>>;
    return rows.map((d) => {
      const it = String(d.issue_type ?? '');
      const st = String(d.status ?? '');
      const pr = String(d.priority ?? '');
      return {
        id: Number(d.id),
        customer_id: Number(d.customer_id),
        case_id: d.case_id != null ? Number(d.case_id) : null,
        issue_type: it,
        issue_type_label: ISSUE_TYPE_LABELS[it] ?? it,
        priority: pr,
        priority_label: ISSUE_PRIORITY_LABELS[pr] ?? pr,
        status: st,
        status_label: ISSUE_STATUS_LABELS[st] ?? st,
        title: String(d.title ?? ''),
        description: String(d.description ?? ''),
        resolution: String(d.resolution ?? ''),
        assigned_staff_id: d.assigned_staff_id != null ? Number(d.assigned_staff_id) : null,
        assigned_staff_name: String(d.assigned_staff_name ?? ''),
        created_at: String(d.created_at ?? ''),
        updated_at: String(d.updated_at ?? ''),
        resolved_at: String(d.resolved_at ?? ''),
      };
    });
  }

  computeStats(
    relations: CustomerRelationRow[],
    purchases: CustomerPurchaseRow[],
    issues: CustomerIssueRow[],
  ): CustomerDetailStats {
    const issuesOpen = issues.filter(
      (i) => !['da_xu_ly', 'dong'].includes(String(i.status ?? '')),
    ).length;
    return {
      relations_total: relations.length,
      purchases_total: purchases.length,
      issues_total: issues.length,
      issues_open: issuesOpen,
    };
  }

  createRelation(customerId: number, body: CreateRelationBody): CustomerRelationRow {
    const ts = catalogTs();
    const result = this.database
      .prepare(
        `INSERT INTO crm_customer_relations (
           customer_id, relation_type, full_name, phone, email, notes, created_at, updated_at
         ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)`,
      )
      .run(
        customerId,
        normalizeRelationType(body.relation_type),
        String(body.full_name ?? '').trim().slice(0, 240),
        String(body.phone ?? '').trim().slice(0, 64),
        String(body.email ?? '').trim().slice(0, 240),
        String(body.notes ?? '').trim().slice(0, 2000),
        ts,
        ts,
      );
    const row = this.database
      .prepare('SELECT * FROM crm_customer_relations WHERE id = ?')
      .get(Number(result.lastInsertRowid)) as unknown as Record<string, unknown>;
    return this.mapRelationRow(row);
  }

  patchRelation(
    customerId: number,
    relationId: number,
    body: PatchRelationBody,
  ): CustomerRelationRow | null {
    const existing = this.database
      .prepare('SELECT * FROM crm_customer_relations WHERE id = ? AND customer_id = ?')
      .get(relationId, customerId) as unknown as Record<string, unknown> | undefined;
    if (!existing) return null;

    const merged: Record<string, string> = {
      relation_type: String(existing.relation_type ?? ''),
      full_name: String(existing.full_name ?? ''),
      phone: String(existing.phone ?? ''),
      email: String(existing.email ?? ''),
      notes: String(existing.notes ?? ''),
    };
    if ('relation_type' in body) {
      merged.relation_type = normalizeRelationType(body.relation_type);
    }
    for (const key of ['full_name', 'phone', 'email', 'notes'] as const) {
      if (key in body && typeof body[key] === 'string') {
        merged[key] = body[key]!.trim().slice(key === 'notes' ? 0 : key === 'full_name' ? 240 : 240);
      }
    }
    const ts = catalogTs();
    this.database
      .prepare(
        `UPDATE crm_customer_relations
         SET relation_type = ?, full_name = ?, phone = ?, email = ?, notes = ?, updated_at = ?
         WHERE id = ?`,
      )
      .run(
        merged.relation_type,
        merged.full_name,
        merged.phone,
        merged.email,
        merged.notes,
        ts,
        relationId,
      );
    const row = this.database
      .prepare('SELECT * FROM crm_customer_relations WHERE id = ?')
      .get(relationId) as unknown as Record<string, unknown>;
    return this.mapRelationRow(row);
  }

  deleteRelation(customerId: number, relationId: number): boolean {
    const result = this.database
      .prepare('DELETE FROM crm_customer_relations WHERE id = ? AND customer_id = ?')
      .run(relationId, customerId);
    return result.changes > 0;
  }

  createPurchase(customerId: number, body: CreatePurchaseBody): CustomerPurchaseRow {
    const ts = catalogTs();
    let amount = 0;
    try {
      amount = Math.max(0, Number(body.amount_vnd ?? 0));
    } catch {
      amount = 0;
    }
    let qty = 1;
    try {
      qty = Math.max(1, Number(body.quantity ?? 1));
    } catch {
      qty = 1;
    }
    let contractId: number | null = null;
    if (body.contract_id != null && body.contract_id !== 0) {
      contractId = Number(body.contract_id);
      if (!Number.isFinite(contractId)) contractId = null;
    }
    const result = this.database
      .prepare(
        `INSERT INTO crm_customer_purchases (
           customer_id, order_date, product_name, amount_vnd, quantity, status,
           reference_code, notes, contract_id, created_at, updated_at
         ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)`,
      )
      .run(
        customerId,
        String(body.order_date ?? ts.slice(0, 10)).trim().slice(0, 32),
        String(body.product_name ?? '').trim().slice(0, 400),
        amount,
        qty,
        normalizePurchaseStatus(body.status),
        String(body.reference_code ?? '').trim().slice(0, 120),
        String(body.notes ?? '').trim().slice(0, 2000),
        contractId,
        ts,
        ts,
      );
    const row = this.database
      .prepare('SELECT * FROM crm_customer_purchases WHERE id = ?')
      .get(Number(result.lastInsertRowid)) as unknown as Record<string, unknown>;
    return this.mapPurchaseRow(row);
  }

  patchPurchase(
    customerId: number,
    purchaseId: number,
    body: PatchPurchaseBody,
  ): CustomerPurchaseRow | null {
    const existing = this.database
      .prepare('SELECT * FROM crm_customer_purchases WHERE id = ? AND customer_id = ?')
      .get(purchaseId, customerId) as unknown as Record<string, unknown> | undefined;
    if (!existing) return null;

    const merged: Record<string, unknown> = { ...existing };
    for (const key of ['product_name', 'order_date', 'reference_code', 'notes'] as const) {
      if (key in body && typeof body[key] === 'string') {
        merged[key] = body[key]!.trim().slice(key === 'product_name' ? 0 : 2000);
      }
    }
    if ('status' in body) {
      merged.status = normalizePurchaseStatus(body.status);
    }
    if ('amount_vnd' in body) {
      try {
        merged.amount_vnd = Math.max(0, Number(body.amount_vnd ?? 0));
      } catch {
        /* keep existing */
      }
    }
    if ('quantity' in body) {
      try {
        merged.quantity = Math.max(1, Number(body.quantity ?? 1));
      } catch {
        /* keep existing */
      }
    }
    const ts = catalogTs();
    this.database
      .prepare(
        `UPDATE crm_customer_purchases
         SET order_date = ?, product_name = ?, amount_vnd = ?, quantity = ?, status = ?,
             reference_code = ?, notes = ?, updated_at = ?
         WHERE id = ?`,
      )
      .run(
        String(merged.order_date ?? ''),
        String(merged.product_name ?? ''),
        Number(merged.amount_vnd ?? 0),
        Number(merged.quantity ?? 1),
        String(merged.status ?? ''),
        String(merged.reference_code ?? ''),
        String(merged.notes ?? ''),
        ts,
        purchaseId,
      );
    const row = this.database
      .prepare('SELECT * FROM crm_customer_purchases WHERE id = ?')
      .get(purchaseId) as unknown as Record<string, unknown>;
    return this.mapPurchaseRow(row);
  }

  deletePurchase(customerId: number, purchaseId: number): boolean {
    const result = this.database
      .prepare('DELETE FROM crm_customer_purchases WHERE id = ? AND customer_id = ?')
      .run(purchaseId, customerId);
    return result.changes > 0;
  }

  createIssue(customerId: number, body: CreateIssueBody): CustomerIssueRow {
    const ts = catalogTs();
    let caseId: number | null = null;
    if (body.case_id != null && body.case_id !== 0) {
      caseId = Number(body.case_id);
      if (!Number.isFinite(caseId)) caseId = null;
    }
    let assignedStaffId: number | null = null;
    if (body.assigned_staff_id != null && body.assigned_staff_id !== 0) {
      assignedStaffId = Number(body.assigned_staff_id);
      if (!Number.isFinite(assignedStaffId)) assignedStaffId = null;
    }
    const result = this.database
      .prepare(
        `INSERT INTO crm_customer_issues (
           customer_id, case_id, issue_type, priority, status, title, description,
           resolution, assigned_staff_id, created_at, updated_at, resolved_at
         ) VALUES (?, ?, ?, ?, 'moi', ?, ?, '', ?, ?, ?, '')`,
      )
      .run(
        customerId,
        caseId,
        normalizeIssueType(body.issue_type),
        normalizeIssuePriority(body.priority),
        String(body.title ?? '').trim().slice(0, 400),
        String(body.description ?? '').trim().slice(0, 8000),
        assignedStaffId,
        ts,
        ts,
      );
    const row = this.database
      .prepare(
        `SELECT i.*, st.name AS assigned_staff_name
         FROM crm_customer_issues i
         LEFT JOIN crm_staff st ON st.id = i.assigned_staff_id
         WHERE i.id = ?`,
      )
      .get(Number(result.lastInsertRowid)) as unknown as Record<string, unknown>;
    return this.mapIssueRow(row);
  }

  patchIssue(
    customerId: number,
    issueId: number,
    body: PatchIssueBody,
  ): CustomerIssueRow | null {
    const existing = this.database
      .prepare('SELECT * FROM crm_customer_issues WHERE id = ? AND customer_id = ?')
      .get(issueId, customerId) as unknown as Record<string, unknown> | undefined;
    if (!existing) return null;

    const merged: Record<string, unknown> = { ...existing };
    for (const key of ['title', 'description', 'resolution'] as const) {
      if (key in body && typeof body[key] === 'string') {
        merged[key] = body[key]!.trim().slice(key === 'title' ? 0 : 8000);
      }
    }
    if ('issue_type' in body) merged.issue_type = normalizeIssueType(body.issue_type);
    if ('priority' in body) merged.priority = normalizeIssuePriority(body.priority);
    if ('status' in body) merged.status = normalizeIssueStatus(body.status);
    if ('assigned_staff_id' in body) {
      const raw = body.assigned_staff_id;
      if (raw == null || raw === 0) {
        merged.assigned_staff_id = null;
      } else {
        const aid = Number(raw);
        merged.assigned_staff_id = Number.isFinite(aid) ? aid : null;
      }
    }
    let resolvedAt = String(merged.resolved_at ?? '');
    const status = String(merged.status ?? '');
    const ts = catalogTs();
    if (['da_xu_ly', 'dong'].includes(status) && !resolvedAt) {
      resolvedAt = ts;
    } else if (!['da_xu_ly', 'dong'].includes(status)) {
      resolvedAt = '';
    }
    this.database
      .prepare(
        `UPDATE crm_customer_issues
         SET issue_type = ?, priority = ?, status = ?, title = ?, description = ?,
             resolution = ?, assigned_staff_id = ?, updated_at = ?, resolved_at = ?
         WHERE id = ?`,
      )
      .run(
        String(merged.issue_type ?? ''),
        String(merged.priority ?? ''),
        String(merged.status ?? ''),
        String(merged.title ?? ''),
        String(merged.description ?? ''),
        String(merged.resolution ?? ''),
        merged.assigned_staff_id != null ? Number(merged.assigned_staff_id) : null,
        ts,
        resolvedAt,
        issueId,
      );
    const row = this.database
      .prepare(
        `SELECT i.*, st.name AS assigned_staff_name
         FROM crm_customer_issues i
         LEFT JOIN crm_staff st ON st.id = i.assigned_staff_id
         WHERE i.id = ?`,
      )
      .get(issueId) as unknown as Record<string, unknown>;
    return this.mapIssueRow(row);
  }

  getLatestBrief(customerId: number): CustomerBriefRow | null {
    const row = this.database
      .prepare(
        `SELECT id, customer_id, meeting_purpose, ai_output, created_at
         FROM crm_customer_brief_scans
         WHERE customer_id = ?
         ORDER BY id DESC
         LIMIT 1`,
      )
      .get(customerId) as unknown as CustomerBriefRow | undefined;
    return row ?? null;
  }

  private mapRelationRow(d: Record<string, unknown>): CustomerRelationRow {
    const rt = String(d.relation_type ?? '');
    return {
      id: Number(d.id),
      customer_id: Number(d.customer_id),
      relation_type: rt,
      relation_type_label: RELATION_TYPE_LABELS[rt] ?? rt,
      full_name: String(d.full_name ?? ''),
      phone: String(d.phone ?? ''),
      email: String(d.email ?? ''),
      notes: String(d.notes ?? ''),
      created_at: String(d.created_at ?? ''),
      updated_at: String(d.updated_at ?? ''),
    };
  }

  private mapPurchaseRow(d: Record<string, unknown>): CustomerPurchaseRow {
    const st = String(d.status ?? '');
    return {
      id: Number(d.id),
      customer_id: Number(d.customer_id),
      order_date: String(d.order_date ?? ''),
      product_name: String(d.product_name ?? ''),
      amount_vnd: Number(d.amount_vnd ?? 0),
      quantity: Number(d.quantity ?? 1),
      status: st,
      status_label: PURCHASE_STATUS_LABELS[st] ?? st,
      reference_code: String(d.reference_code ?? ''),
      notes: String(d.notes ?? ''),
      contract_id: d.contract_id != null ? Number(d.contract_id) : null,
      created_at: String(d.created_at ?? ''),
      updated_at: String(d.updated_at ?? ''),
    };
  }

  private mapIssueRow(d: Record<string, unknown>): CustomerIssueRow {
    const it = String(d.issue_type ?? '');
    const st = String(d.status ?? '');
    const pr = String(d.priority ?? '');
    return {
      id: Number(d.id),
      customer_id: Number(d.customer_id),
      case_id: d.case_id != null ? Number(d.case_id) : null,
      issue_type: it,
      issue_type_label: ISSUE_TYPE_LABELS[it] ?? it,
      priority: pr,
      priority_label: ISSUE_PRIORITY_LABELS[pr] ?? pr,
      status: st,
      status_label: ISSUE_STATUS_LABELS[st] ?? st,
      title: String(d.title ?? ''),
      description: String(d.description ?? ''),
      resolution: String(d.resolution ?? ''),
      assigned_staff_id: d.assigned_staff_id != null ? Number(d.assigned_staff_id) : null,
      assigned_staff_name: String(d.assigned_staff_name ?? ''),
      created_at: String(d.created_at ?? ''),
      updated_at: String(d.updated_at ?? ''),
      resolved_at: String(d.resolved_at ?? ''),
    };
  }

  private mapCustomer(row: SqliteCustomerRow): CustomerRow {
    const ls = String(row.lead_source ?? '');
    const g = String(row.gender ?? '');
    return {
      id: Number(row.id),
      name: String(row.name ?? ''),
      phone: String(row.phone ?? ''),
      email: String(row.email ?? ''),
      address: String(row.address ?? ''),
      company: String(row.company ?? ''),
      lead_source: ls,
      lead_source_label: ls ? (CUSTOMER_LEAD_SOURCE_LABELS[ls] ?? ls) : '',
      lead_source_note: String(row.lead_source_note ?? ''),
      date_of_birth: String(row.date_of_birth ?? ''),
      gender: g,
      gender_label: g ? (CUSTOMER_GENDER_LABELS[g] ?? g) : '',
      id_number: String(row.id_number ?? ''),
      occupation: String(row.occupation ?? ''),
      interests: String(row.interests ?? ''),
      profile_notes: String(row.profile_notes ?? ''),
      created_at: String(row.created_at ?? ''),
    };
  }

  private normalizeLeadSource(raw: string): string {
    const code = String(raw ?? '').trim().toLowerCase();
    if ((CUSTOMER_LEAD_SOURCES as readonly string[]).includes(code)) return code;
    return code ? 'other' : '';
  }

  private normalizeGender(raw: string): string {
    const code = String(raw ?? '').trim().toLowerCase();
    return (CUSTOMER_GENDERS as readonly string[]).includes(code) ? code : '';
  }
}
