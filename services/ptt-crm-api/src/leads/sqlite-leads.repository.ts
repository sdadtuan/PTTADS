import { Injectable, OnModuleDestroy } from '@nestjs/common';
import { DatabaseSync } from 'node:sqlite';
import { AppConfigService } from '../config/app-config.service';
import { leadRowToV1 } from './lead-v1.mapper';
import { LeadRow, LeadV1, ListLeadsQuery } from './leads.types';

interface WhereClause {
  sql: string;
  params: Array<string | number>;
}

@Injectable()
export class SqliteLeadsRepository implements OnModuleDestroy {
  private db: DatabaseSync | null = null;
  private overridePath: string | null = null;

  constructor(private readonly config: AppConfigService) {}

  useDatabasePath(dbPath: string): void {
    this.close();
    this.overridePath = dbPath;
    this.db = this.openDb(dbPath);
  }

  private get database(): DatabaseSync {
    if (!this.db) {
      this.db = this.openDb(this.overridePath ?? this.config.sqlitePath);
    }
    return this.db;
  }

  private openDb(dbPath: string): DatabaseSync {
    return new DatabaseSync(dbPath, { readOnly: true });
  }

  onModuleDestroy(): void {
    this.close();
  }

  private close(): void {
    if (this.db) {
      this.db.close();
      this.db = null;
    }
  }

  listLeads(query: ListLeadsQuery): { leads: LeadV1[]; total: number } {
    const limit = Math.max(1, Math.min(Number(query.limit ?? 50), 200));
    const offset = Math.max(0, Number(query.offset ?? 0));
    const where = this.buildWhere(query);

    const totalRow = this.database
      .prepare(`SELECT COUNT(*) AS c FROM crm_leads l${where.sql}`)
      .get(...where.params) as { c: number };
    const total = Number(totalRow?.c ?? 0);

    const rows = this.database
      .prepare(
        `SELECT l.id, l.full_name, l.phone, l.email, l.status, l.source,
                l.owner_id, l.created_at, l.is_duplicate, l.meta_json
         FROM crm_leads l
         ${where.sql}
         ORDER BY l.id DESC
         LIMIT ? OFFSET ?`,
      )
      .all(...where.params, limit, offset) as unknown as LeadRow[];

    return { leads: rows.map(leadRowToV1), total };
  }

  getLeadById(leadId: number): LeadV1 | null {
    const row = this.database
      .prepare(
        `SELECT l.id, l.full_name, l.phone, l.email, l.status, l.source,
                l.owner_id, l.created_at, l.is_duplicate, l.meta_json
         FROM crm_leads l
         WHERE l.id = ?`,
      )
      .get(leadId) as unknown as LeadRow | undefined;
    return row ? leadRowToV1(row) : null;
  }

  private buildWhere(query: ListLeadsQuery): WhereClause {
    const clauses = ['COALESCE(l.is_duplicate, 0) = 0'];
    const params: Array<string | number> = [];

    if (query.client_id?.trim()) {
      clauses.push(`json_extract(l.meta_json, '$.agency_client_id') = ?`);
      params.push(query.client_id.trim());
    }
    if (query.status?.trim()) {
      clauses.push('l.status = ?');
      params.push(query.status.trim());
    }
    if (query.source?.trim()) {
      clauses.push('l.source = ?');
      params.push(query.source.trim());
    }
    if (query.channel?.trim()) {
      const ch = query.channel.trim().toLowerCase();
      clauses.push(
        `(
          lower(COALESCE(json_extract(l.meta_json, '$.channel'), '')) = ?
          OR lower(COALESCE(json_extract(l.meta_json, '$.ingest_channel'), '')) = ?
          OR lower(COALESCE(l.source, '')) = ?
        )`,
      );
      params.push(ch, ch, ch);
    }
    if (query.q?.trim()) {
      const like = `%${query.q.trim()}%`;
      clauses.push('(l.full_name LIKE ? OR l.phone LIKE ? OR l.email LIKE ?)');
      params.push(like, like, like);
    }

    return {
      sql: clauses.length ? ` WHERE ${clauses.join(' AND ')}` : '',
      params,
    };
  }
}
