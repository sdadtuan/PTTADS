import { Injectable, OnModuleDestroy } from '@nestjs/common';
import { DatabaseSync } from 'node:sqlite';
import { AppConfigService } from '../config/app-config.service';
import { catalogTs } from '../catalog/catalog-slug.util';
import {
  ACTIVITY_TYPE_LABELS,
  ACTIVITY_TYPES,
  CreateLeadActivityBody,
  LeadActivityRow,
  LeadAssignmentLogRow,
  LeadStatusLogRow,
} from './crm-leads-legacy.types';

@Injectable()
export class CrmLeadsSqliteRepository implements OnModuleDestroy {
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

  leadExists(leadId: number): boolean {
    const row = this.database
      .prepare('SELECT id FROM crm_leads WHERE id = ? LIMIT 1')
      .get(leadId) as { id: number } | undefined;
    return Boolean(row);
  }

  getLeadOwnerId(leadId: number): number | null {
    const row = this.database
      .prepare('SELECT owner_id FROM crm_leads WHERE id = ?')
      .get(leadId) as { owner_id: number | null } | undefined;
    return row?.owner_id != null ? Number(row.owner_id) : null;
  }

  getLeadStatus(leadId: number): string {
    const row = this.database
      .prepare('SELECT status FROM crm_leads WHERE id = ?')
      .get(leadId) as { status: string } | undefined;
    return String(row?.status ?? 'new');
  }

  syncOwner(leadId: number, ownerId: number, actor: string, ts: string): void {
    this.database
      .prepare('UPDATE crm_leads SET owner_id = ?, updated_at = ?, updated_by = ? WHERE id = ?')
      .run(ownerId, ts, actor.slice(0, 120), leadId);
  }

  syncStatus(leadId: number, status: string, actor: string, ts: string): void {
    this.database
      .prepare('UPDATE crm_leads SET status = ?, updated_at = ?, updated_by = ? WHERE id = ?')
      .run(status, ts, actor.slice(0, 120), leadId);
  }

  staffExists(staffId: number): boolean {
    const row = this.database
      .prepare('SELECT id FROM crm_staff WHERE id = ? AND COALESCE(active, 1) = 1')
      .get(staffId);
    return Boolean(row);
  }

  listActivities(leadId: number, limit = 100): LeadActivityRow[] {
    const lim = Math.max(1, Math.min(limit, 500));
    const rows = this.database
      .prepare(
        `SELECT a.*, s.name AS user_name
         FROM crm_lead_activities a
         LEFT JOIN crm_staff s ON s.id = a.user_id
         WHERE a.lead_id = ?
         ORDER BY a.created_at DESC
         LIMIT ?`,
      )
      .all(leadId, lim) as Array<Record<string, unknown>>;
    return rows.map((d) => this.mapActivity(d));
  }

  createActivity(
    leadId: number,
    body: CreateLeadActivityBody,
    actor: string,
    userId: number | null,
  ): LeadActivityRow {
    let at = String(body.activity_type ?? 'note')
      .trim()
      .toLowerCase();
    if (!ACTIVITY_TYPES.includes(at as (typeof ACTIVITY_TYPES)[number])) {
      at = 'note';
    }
    const ts = catalogTs();
    const statusSnap = this.getLeadStatus(leadId);
    const result = this.database
      .prepare(
        `INSERT INTO crm_lead_activities (
           lead_id, user_id, activity_type, content, result,
           next_action, next_action_at, created_at, created_by, lead_status_at_log
         ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)`,
      )
      .run(
        leadId,
        userId,
        at,
        String(body.content ?? '').slice(0, 8000),
        String(body.result ?? '').slice(0, 2000),
        String(body.next_action ?? '').slice(0, 500),
        String(body.next_action_at ?? '').slice(0, 40),
        ts,
        actor.slice(0, 120),
        statusSnap,
      );
    this.database
      .prepare('UPDATE crm_leads SET updated_at = ?, updated_by = ? WHERE id = ?')
      .run(ts, actor.slice(0, 120), leadId);
    const row = this.database
      .prepare(
        `SELECT a.*, s.name AS user_name FROM crm_lead_activities a
         LEFT JOIN crm_staff s ON s.id = a.user_id WHERE a.id = ?`,
      )
      .get(Number(result.lastInsertRowid)) as Record<string, unknown>;
    return this.mapActivity(row);
  }

  logAssignment(
    leadId: number,
    fromUserId: number | null,
    toUserId: number,
    reason: string,
    actor: string,
    ts: string,
  ): void {
    this.database
      .prepare(
        `INSERT INTO crm_lead_assignment_logs
         (lead_id, from_user_id, to_user_id, reason, created_by, created_at)
         VALUES (?, ?, ?, ?, ?, ?)`,
      )
      .run(leadId, fromUserId, toUserId, reason.slice(0, 500), actor.slice(0, 120), ts);
  }

  logStatusChange(
    leadId: number,
    oldStatus: string,
    newStatus: string,
    actor: string,
    note: string,
    ts: string,
  ): void {
    this.database
      .prepare(
        `INSERT INTO crm_lead_status_logs
         (lead_id, old_status, new_status, changed_by, note, created_at)
         VALUES (?, ?, ?, ?, ?, ?)`,
      )
      .run(leadId, oldStatus, newStatus, actor.slice(0, 120), note.slice(0, 2000), ts);
  }

  listStatusLogs(leadId: number, limit = 100): LeadStatusLogRow[] {
    const lim = Math.max(1, Math.min(limit, 200));
    const rows = this.database
      .prepare(
        `SELECT id, lead_id, old_status, new_status, changed_by, note, created_at
         FROM crm_lead_status_logs WHERE lead_id = ? ORDER BY created_at DESC LIMIT ?`,
      )
      .all(leadId, lim) as Array<Record<string, unknown>>;
    return rows.map((d) => ({
      id: Number(d.id),
      lead_id: Number(d.lead_id),
      old_status: String(d.old_status ?? ''),
      new_status: String(d.new_status ?? ''),
      changed_by: String(d.changed_by ?? ''),
      note: String(d.note ?? ''),
      created_at: String(d.created_at ?? ''),
    }));
  }

  listAssignmentLogs(leadId: number, limit = 100): LeadAssignmentLogRow[] {
    const lim = Math.max(1, Math.min(limit, 200));
    const rows = this.database
      .prepare(
        `SELECT a.*, fs.name AS from_name, ts.name AS to_name
         FROM crm_lead_assignment_logs a
         LEFT JOIN crm_staff fs ON fs.id = a.from_user_id
         LEFT JOIN crm_staff ts ON ts.id = a.to_user_id
         WHERE a.lead_id = ? ORDER BY a.created_at DESC LIMIT ?`,
      )
      .all(leadId, lim) as Array<Record<string, unknown>>;
    return rows.map((d) => ({
      id: Number(d.id),
      lead_id: Number(d.lead_id),
      from_user_id: d.from_user_id != null ? Number(d.from_user_id) : null,
      from_name: String(d.from_name ?? '—'),
      to_user_id: d.to_user_id != null ? Number(d.to_user_id) : null,
      to_name: String(d.to_name ?? '—'),
      reason: String(d.reason ?? ''),
      created_by: String(d.created_by ?? ''),
      created_at: String(d.created_at ?? ''),
    }));
  }

  private mapActivity(d: Record<string, unknown>): LeadActivityRow {
    const at = String(d.activity_type ?? 'note');
    return {
      id: Number(d.id),
      lead_id: Number(d.lead_id),
      user_id: d.user_id != null ? Number(d.user_id) : null,
      user_name: String(d.user_name ?? ''),
      activity_type: at,
      activity_type_label: ACTIVITY_TYPE_LABELS[at] ?? at,
      content: String(d.content ?? ''),
      result: String(d.result ?? ''),
      next_action: String(d.next_action ?? ''),
      next_action_at: String(d.next_action_at ?? ''),
      created_at: String(d.created_at ?? ''),
      created_by: String(d.created_by ?? ''),
    };
  }
}
