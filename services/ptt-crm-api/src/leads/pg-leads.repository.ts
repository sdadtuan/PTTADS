import { Injectable, OnModuleDestroy } from '@nestjs/common';
import { Pool } from 'pg';
import { AppConfigService } from '../config/app-config.service';
import { pgRowToV1 } from './lead-v1.mapper';
import { LeadV1, ListLeadsQuery, PgLeadRow } from './leads.types';

interface PgWhereClause {
  sql: string;
  params: unknown[];
}

@Injectable()
export class PgLeadsRepository implements OnModuleDestroy {
  private pool: Pool | null = null;

  constructor(private readonly config: AppConfigService) {}

  private get db(): Pool {
    if (!this.pool) {
      this.pool = new Pool({ connectionString: this.config.databaseUrl });
    }
    return this.pool;
  }

  onModuleDestroy(): void {
    void this.pool?.end();
    this.pool = null;
  }

  async listLeads(query: ListLeadsQuery): Promise<{ leads: LeadV1[]; total: number }> {
    const limit = Math.max(1, Math.min(Number(query.limit ?? 50), 200));
    const offset = Math.max(0, Number(query.offset ?? 0));
    const where = this.buildWhere(query);

    const countResult = await this.db.query(
      `SELECT COUNT(*)::int AS c FROM crm_leads l${where.sql}`,
      where.params,
    );
    const total = Number(countResult.rows[0]?.c ?? 0);

    const listParams = [...where.params, limit, offset];
    const listResult = await this.db.query(
      `SELECT l.sqlite_lead_id, l.full_name, l.phone, l.email, l.status, l.source,
              l.owner_id, l.is_duplicate, l.agency_client_id, l.channel,
              l.external_lead_id, l.campaign_id, l.received_at, l.created_at
       FROM crm_leads l
       ${where.sql}
       ORDER BY l.sqlite_lead_id DESC
       LIMIT $${listParams.length - 1} OFFSET $${listParams.length}`,
      listParams,
    );

    return {
      leads: listResult.rows.map((row) => pgRowToV1(row as PgLeadRow)),
      total,
    };
  }

  async getLeadById(leadId: number): Promise<LeadV1 | null> {
    const result = await this.db.query(
      `SELECT l.sqlite_lead_id, l.full_name, l.phone, l.email, l.status, l.source,
              l.owner_id, l.is_duplicate, l.agency_client_id, l.channel,
              l.external_lead_id, l.campaign_id, l.received_at, l.created_at
       FROM crm_leads l
       WHERE l.sqlite_lead_id = $1`,
      [leadId],
    );
    const row = result.rows[0] as PgLeadRow | undefined;
    return row ? pgRowToV1(row) : null;
  }

  private buildWhere(query: ListLeadsQuery): PgWhereClause {
    const clauses = ['l.is_duplicate IS NOT TRUE'];
    const params: unknown[] = [];

    const push = (clause: string, ...values: unknown[]) => {
      const idx = params.length + 1;
      clauses.push(clause.replace('?', `$${idx}`));
      params.push(...values);
    };

    if (query.client_id?.trim()) {
      push('l.agency_client_id = ?::uuid', query.client_id.trim());
    }
    if (query.status?.trim()) {
      push('l.status = ?', query.status.trim());
    }
    if (query.source?.trim()) {
      push('l.source = ?', query.source.trim());
    }
    if (query.channel?.trim()) {
      push('lower(l.channel) = ?', query.channel.trim().toLowerCase());
    }
    if (query.q?.trim()) {
      const like = `%${query.q.trim()}%`;
      const base = params.length;
      clauses.push(
        `(l.full_name ILIKE $${base + 1} OR l.phone ILIKE $${base + 2} OR l.email ILIKE $${base + 3})`,
      );
      params.push(like, like, like);
    }
    if (query.review_queue_filter === 'only') {
      const ids = query.review_queue_ids ?? [];
      if (ids.length === 0) {
        clauses.push('FALSE');
      } else {
        const base = params.length;
        const placeholders = ids.map((_, i) => `$${base + i + 1}`).join(', ');
        clauses.push(`l.sqlite_lead_id IN (${placeholders})`);
        params.push(...ids);
      }
    } else if (query.review_queue_filter === 'hide') {
      const ids = query.review_queue_ids ?? [];
      if (ids.length > 0) {
        const base = params.length;
        const placeholders = ids.map((_, i) => `$${base + i + 1}`).join(', ');
        clauses.push(`l.sqlite_lead_id NOT IN (${placeholders})`);
        params.push(...ids);
      }
    }

    return {
      sql: clauses.length ? ` WHERE ${clauses.join(' AND ')}` : '',
      params,
    };
  }
}
