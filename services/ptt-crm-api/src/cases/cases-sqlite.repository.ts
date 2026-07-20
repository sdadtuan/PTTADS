import { Injectable, OnModuleDestroy } from '@nestjs/common';
import { DatabaseSync } from 'node:sqlite';
import { catalogTs } from '../catalog/catalog-slug.util';
import { AppConfigService } from '../config/app-config.service';
import {
  CareReportRow,
  CaseEventRow,
  CaseRow,
  CreateCareReportBody,
  CRM_CARE_CONTACT_LABELS,
  CRM_CARE_STATUS_LABELS,
  CRM_CHANNEL_LABELS,
  CRM_PRIORITY_LABELS,
  CRM_STATUS_LABELS,
  CRM_STATUSES,
  normalizeCareContact,
  normalizeCareStatus,
  normalizeCaseChannel,
  normalizeCasePriority,
  normalizeCaseStatus,
  PatchCaseBody,
} from './cases.types';

const CASE_SELECT = `
SELECT c.*,
       cu.name AS customer_name,
       cu.phone AS customer_phone,
       cu.email AS customer_email,
       cu.address AS customer_address,
       cu.company AS customer_company,
       st.name AS staff_display_name
FROM crm_cases c
JOIN crm_customers cu ON cu.id = c.customer_id
LEFT JOIN crm_staff st ON st.id = c.assigned_staff_id
`;

@Injectable()
export class CasesSqliteRepository implements OnModuleDestroy {
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

  listCases(staffId?: number): CaseRow[] {
    let rows: Array<Record<string, unknown>>;
    if (staffId != null && Number.isFinite(staffId)) {
      rows = this.database
        .prepare(`${CASE_SELECT} WHERE c.assigned_staff_id = ? ORDER BY datetime(c.updated_at) DESC`)
        .all(staffId) as unknown as Array<Record<string, unknown>>;
    } else {
      rows = this.database
        .prepare(`${CASE_SELECT} ORDER BY datetime(c.updated_at) DESC`)
        .all() as unknown as Array<Record<string, unknown>>;
    }
    return rows.map((r) => this.mapCaseRow(r));
  }

  getCaseById(caseId: number): CaseRow | null {
    const row = this.database
      .prepare(`${CASE_SELECT} WHERE c.id = ?`)
      .get(caseId) as unknown as Record<string, unknown> | undefined;
    return row ? this.mapCaseRow(row) : null;
  }

  patchCase(caseId: number, body: PatchCaseBody): CaseRow | null {
    const existing = this.database
      .prepare('SELECT * FROM crm_cases WHERE id = ?')
      .get(caseId) as unknown as Record<string, unknown> | undefined;
    if (!existing) return null;

    const merged: Record<string, unknown> = { ...existing };
    if ('title' in body && typeof body.title === 'string') {
      merged.title = body.title.trim().slice(0, 800);
    }
    if ('description' in body && typeof body.description === 'string') {
      merged.description = body.description.trim().slice(0, 8000);
    }
    if ('status' in body) {
      merged.status = normalizeCaseStatus(body.status);
    }
    if ('priority' in body) {
      merged.priority = normalizeCasePriority(body.priority);
    }
    if ('pipeline_stage' in body && typeof body.pipeline_stage === 'string') {
      merged.pipeline_stage = body.pipeline_stage.trim().slice(0, 64);
    }
    if ('channel' in body) {
      merged.channel = normalizeCaseChannel(body.channel);
    }
    if ('assigned_staff_id' in body || 'assigned_to' in body) {
      const rawId = body.assigned_staff_id;
      if (rawId == null || rawId === 0) {
        merged.assigned_staff_id = null;
        merged.assigned_to = String(body.assigned_to ?? '').trim().slice(0, 240);
        merged.assigned_at = '';
      } else {
        const aid = Number(rawId);
        if (Number.isFinite(aid) && aid > 0) {
          merged.assigned_staff_id = aid;
          const staffRow = this.database
            .prepare('SELECT name FROM crm_staff WHERE id = ?')
            .get(aid) as unknown as { name: string } | undefined;
          merged.assigned_to = String(staffRow?.name ?? body.assigned_to ?? '').slice(0, 240);
          merged.assigned_at = catalogTs();
        }
      }
    }

    const ts = catalogTs();
    this.database
      .prepare(
        `UPDATE crm_cases
         SET title = ?, description = ?, channel = ?, priority = ?, status = ?,
             assigned_to = ?, assigned_staff_id = ?, assigned_at = ?,
             pipeline_stage = ?, updated_at = ?
         WHERE id = ?`,
      )
      .run(
        String(merged.title ?? ''),
        String(merged.description ?? ''),
        String(merged.channel ?? ''),
        String(merged.priority ?? ''),
        String(merged.status ?? ''),
        String(merged.assigned_to ?? ''),
        merged.assigned_staff_id != null ? Number(merged.assigned_staff_id) : null,
        String(merged.assigned_at ?? ''),
        String(merged.pipeline_stage ?? ''),
        ts,
        caseId,
      );
    return this.getCaseById(caseId);
  }

  listEvents(caseId: number): CaseEventRow[] {
    const rows = this.database
      .prepare(
        `SELECT id, case_id, kind, body, created_at
         FROM crm_case_events
         WHERE case_id = ?
         ORDER BY id ASC`,
      )
      .all(caseId) as unknown as Array<Record<string, unknown>>;
    return rows.map((r) => ({
      id: Number(r.id),
      case_id: Number(r.case_id),
      kind: String(r.kind ?? ''),
      body: String(r.body ?? ''),
      created_at: String(r.created_at ?? ''),
    }));
  }

  createEvent(caseId: number, body: string): CaseEventRow {
    const ts = catalogTs();
    const result = this.database
      .prepare(
        `INSERT INTO crm_case_events (case_id, kind, body, created_at)
         VALUES (?, 'ghi_chu', ?, ?)`,
      )
      .run(caseId, body, ts);
    this.database
      .prepare('UPDATE crm_cases SET updated_at = ? WHERE id = ?')
      .run(ts, caseId);
    const row = this.database
      .prepare('SELECT id, case_id, kind, body, created_at FROM crm_case_events WHERE id = ?')
      .get(Number(result.lastInsertRowid)) as unknown as Record<string, unknown>;
    return {
      id: Number(row.id),
      case_id: Number(row.case_id),
      kind: String(row.kind ?? ''),
      body: String(row.body ?? ''),
      created_at: String(row.created_at ?? ''),
    };
  }

  listCareReports(caseId: number, limit = 50): CareReportRow[] {
    const rows = this.database
      .prepare(
        `SELECT * FROM crm_care_reports
         WHERE case_id = ?
         ORDER BY id DESC
         LIMIT ?`,
      )
      .all(caseId, limit) as unknown as Array<Record<string, unknown>>;
    return rows.map((r) => this.mapCareReportRow(r));
  }

  createCareReport(caseId: number, body: CreateCareReportBody): CareReportRow {
    const caseRow = this.getCaseById(caseId);
    if (!caseRow) {
      throw new Error('Case not found');
    }

    let staffId: number | null = null;
    if (body.staff_id != null && body.staff_id !== 0) {
      staffId = Number(body.staff_id);
      if (!Number.isFinite(staffId)) staffId = null;
    }
    let staffName = '';
    if (staffId) {
      const srow = this.database
        .prepare('SELECT name FROM crm_staff WHERE id = ? AND active = 1')
        .get(staffId) as unknown as { name: string } | undefined;
      if (srow) {
        staffName = String(srow.name);
      } else {
        staffId = null;
      }
    }
    if (!staffId && caseRow.assigned_staff_id) {
      staffId = caseRow.assigned_staff_id;
      staffName = caseRow.staff_display_name || caseRow.assigned_to;
    }

    const contactType = normalizeCareContact(body.contact_type);
    const careStatus = normalizeCareStatus(body.care_status);
    const summary = String(body.summary ?? '').trim().slice(0, 4000);
    const nextAction = String(body.next_action ?? '').trim().slice(0, 800);
    const ts = catalogTs();

    const result = this.database
      .prepare(
        `INSERT INTO crm_care_reports (
           case_id, staff_id, staff_name, contact_type, care_status,
           summary, next_action, created_at
         ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)`,
      )
      .run(caseId, staffId, staffName, contactType, careStatus, summary, nextAction, ts);

    this.database
      .prepare('UPDATE crm_cases SET updated_at = ? WHERE id = ?')
      .run(ts, caseId);

    const row = this.database
      .prepare('SELECT * FROM crm_care_reports WHERE id = ?')
      .get(Number(result.lastInsertRowid)) as unknown as Record<string, unknown>;
    return this.mapCareReportRow(row);
  }

  private mapCaseRow(row: Record<string, unknown>): CaseRow {
    const displayName = row.staff_display_name;
    let assignedTo = String(row.assigned_to ?? '');
    if (displayName) {
      assignedTo = String(displayName);
    }
    const status = String(row.status ?? '');
    const priority = String(row.priority ?? '');
    const channel = String(row.channel ?? '');
    return {
      id: Number(row.id),
      customer_id: Number(row.customer_id),
      title: String(row.title ?? ''),
      description: String(row.description ?? ''),
      channel,
      channel_label: CRM_CHANNEL_LABELS[channel] ?? channel,
      priority,
      priority_label: CRM_PRIORITY_LABELS[priority] ?? priority,
      status,
      status_label: CRM_STATUS_LABELS[status] ?? status,
      pipeline_stage: String(row.pipeline_stage ?? ''),
      assigned_to: assignedTo,
      assigned_staff_id:
        row.assigned_staff_id != null ? Number(row.assigned_staff_id) : null,
      assigned_at: String(row.assigned_at ?? ''),
      campaign_id: row.campaign_id != null ? Number(row.campaign_id) : null,
      created_at: String(row.created_at ?? ''),
      updated_at: String(row.updated_at ?? ''),
      customer_name: String(row.customer_name ?? ''),
      customer_phone: String(row.customer_phone ?? ''),
      customer_email: String(row.customer_email ?? ''),
      customer_address: String(row.customer_address ?? ''),
      customer_company: String(row.customer_company ?? ''),
      staff_display_name: String(displayName ?? ''),
    };
  }

  private mapCareReportRow(row: Record<string, unknown>): CareReportRow {
    const contactType = String(row.contact_type ?? '');
    const careStatus = String(row.care_status ?? '');
    return {
      id: Number(row.id),
      case_id: Number(row.case_id),
      staff_id: row.staff_id != null ? Number(row.staff_id) : null,
      staff_name: String(row.staff_name ?? ''),
      contact_type: contactType,
      contact_type_label: CRM_CARE_CONTACT_LABELS[contactType] ?? contactType,
      care_status: careStatus,
      care_status_label: CRM_CARE_STATUS_LABELS[careStatus] ?? careStatus,
      summary: String(row.summary ?? ''),
      next_action: String(row.next_action ?? ''),
      created_at: String(row.created_at ?? ''),
    };
  }

  isValidStatus(status: string): boolean {
    return (CRM_STATUSES as readonly string[]).includes(status);
  }
}
