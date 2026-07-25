import { Injectable, OnModuleDestroy } from '@nestjs/common';
import { Pool } from 'pg';
import { AppConfigService } from '../config/app-config.service';
import {
  PortalNotificationRow,
  PortalNotificationSummaryResponse,
} from './portal-notification.types';

function iso(value: unknown): string | null {
  if (value == null) return null;
  if (value instanceof Date) return value.toISOString();
  return String(value);
}

function mapRow(row: Record<string, unknown>): PortalNotificationRow {
  const metaRaw = row.meta;
  let meta: Record<string, unknown> = {};
  if (metaRaw && typeof metaRaw === 'object' && !Array.isArray(metaRaw)) {
    meta = metaRaw as Record<string, unknown>;
  } else if (typeof metaRaw === 'string') {
    try {
      meta = JSON.parse(metaRaw) as Record<string, unknown>;
    } catch {
      meta = {};
    }
  }
  return {
    id: String(row.id),
    client_id: String(row.client_id),
    portal_user_id: row.portal_user_id != null ? String(row.portal_user_id) : null,
    category: String(row.category ?? 'system'),
    title: String(row.title ?? ''),
    body: row.body != null ? String(row.body) : null,
    link_url: row.link_url != null ? String(row.link_url) : null,
    meta,
    read: row.read_at != null,
    read_at: iso(row.read_at),
    created_at: iso(row.created_at) ?? new Date().toISOString(),
  };
}

@Injectable()
export class PortalNotificationRepository implements OnModuleDestroy {
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

  async tableReady(): Promise<boolean> {
    try {
      const result = await this.db.query(
        `SELECT 1 FROM information_schema.tables
         WHERE table_schema = 'public' AND table_name = 'portal_notification'`,
      );
      return (result.rowCount ?? 0) > 0;
    } catch {
      return false;
    }
  }

  async listForUser(params: {
    clientId: string;
    portalUserId: string;
    unreadOnly: boolean;
    limit: number;
  }): Promise<{ rows: PortalNotificationRow[]; unread: number }> {
    const clauses = [
      'client_id = $1::uuid',
      '(portal_user_id IS NULL OR portal_user_id = $2::uuid)',
    ];
    const values: unknown[] = [params.clientId, params.portalUserId];
    if (params.unreadOnly) {
      clauses.push('read_at IS NULL');
    }
    const result = await this.db.query(
      `SELECT id, client_id, portal_user_id, category, title, body, link_url, meta, read_at, created_at
       FROM portal_notification
       WHERE ${clauses.join(' AND ')}
       ORDER BY created_at DESC
       LIMIT $3`,
      [...values, params.limit],
    );
    const unreadResult = await this.db.query(
      `SELECT COUNT(*)::int AS c FROM portal_notification
       WHERE client_id = $1::uuid
         AND (portal_user_id IS NULL OR portal_user_id = $2::uuid)
         AND read_at IS NULL`,
      [params.clientId, params.portalUserId],
    );
    return {
      rows: result.rows.map((row) => mapRow(row as Record<string, unknown>)),
      unread: Number(unreadResult.rows[0]?.c ?? 0),
    };
  }

  async insert(params: {
    clientId: string;
    portalUserId?: string | null;
    category: string;
    title: string;
    body?: string | null;
    linkUrl?: string | null;
    meta?: Record<string, unknown>;
  }): Promise<PortalNotificationRow | null> {
    const result = await this.db.query(
      `INSERT INTO portal_notification
         (client_id, portal_user_id, category, title, body, link_url, meta)
       VALUES ($1::uuid, $2::uuid, $3, $4, $5, $6, $7::jsonb)
       RETURNING id, client_id, portal_user_id, category, title, body, link_url, meta, read_at, created_at`,
      [
        params.clientId,
        params.portalUserId ?? null,
        params.category,
        params.title,
        params.body ?? null,
        params.linkUrl ?? null,
        JSON.stringify(params.meta ?? {}),
      ],
    );
    if (!result.rows.length) return null;
    return mapRow(result.rows[0] as Record<string, unknown>);
  }

  async markRead(params: {
    clientId: string;
    portalUserId: string;
    notificationId: string;
  }): Promise<PortalNotificationRow | null> {
    const result = await this.db.query(
      `UPDATE portal_notification
       SET read_at = COALESCE(read_at, NOW())
       WHERE id = $1::uuid
         AND client_id = $2::uuid
         AND (portal_user_id IS NULL OR portal_user_id = $3::uuid)
       RETURNING id, client_id, portal_user_id, category, title, body, link_url, meta, read_at, created_at`,
      [params.notificationId, params.clientId, params.portalUserId],
    );
    if (!result.rows.length) return null;
    return mapRow(result.rows[0] as Record<string, unknown>);
  }

  async markAllRead(params: { clientId: string; portalUserId: string }): Promise<number> {
    const result = await this.db.query(
      `UPDATE portal_notification
       SET read_at = NOW()
       WHERE client_id = $1::uuid
         AND (portal_user_id IS NULL OR portal_user_id = $2::uuid)
         AND read_at IS NULL`,
      [params.clientId, params.portalUserId],
    );
    return result.rowCount ?? 0;
  }

  async listActivePortalUsers(clientId: string): Promise<
    Array<{ id: string; email: string; role: 'viewer' | 'approver' }>
  > {
    try {
      const result = await this.db.query(
        `SELECT id, email, role FROM portal_client_users
         WHERE client_id = $1::uuid AND active IS TRUE
         ORDER BY email ASC`,
        [clientId],
      );
      return result.rows.map((row) => ({
        id: String(row.id),
        email: String(row.email),
        role: row.role === 'approver' ? 'approver' : 'viewer',
      }));
    } catch {
      return [];
    }
  }

  async countPendingCreatives(clientId: string): Promise<number> {
    try {
      const result = await this.db.query(
        `SELECT COUNT(*)::int AS c FROM creatives
         WHERE client_id = $1::uuid AND status = 'pending_client'`,
        [clientId],
      );
      return Number(result.rows[0]?.c ?? 0);
    } catch {
      return 0;
    }
  }

  emptySummary(clientId: string, tableReady: boolean): PortalNotificationSummaryResponse {
    return {
      ok: true,
      client_id: clientId,
      unread: 0,
      pending_creatives: 0,
      pending_email: 0,
      pending_seo: 0,
      table_ready: tableReady,
    };
  }
}
