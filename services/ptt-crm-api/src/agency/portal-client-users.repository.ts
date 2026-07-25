import { Injectable, OnModuleDestroy } from '@nestjs/common';
import { Pool } from 'pg';
import { AppConfigService } from '../config/app-config.service';
import { PortalClientRole, PortalClientUserPublic } from './portal-client-users.types';

function iso(value: unknown): string | null {
  if (value == null) return null;
  if (value instanceof Date) return value.toISOString();
  return String(value);
}

function mapRow(row: Record<string, unknown>): PortalClientUserPublic {
  return {
    id: String(row.id),
    email: String(row.email),
    role: row.role === 'approver' ? 'approver' : 'viewer',
    active: row.active === true || row.active === 't' || row.active === 1,
    last_login_at: iso(row.last_login_at),
    created_at: iso(row.created_at) ?? new Date().toISOString(),
    updated_at: iso(row.updated_at) ?? new Date().toISOString(),
  };
}

@Injectable()
export class PortalClientUsersRepository implements OnModuleDestroy {
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
         WHERE table_schema = 'public' AND table_name = 'portal_client_users'`,
      );
      return (result.rowCount ?? 0) > 0;
    } catch {
      return false;
    }
  }

  async clientExists(clientId: string): Promise<boolean> {
    const result = await this.db.query(`SELECT 1 FROM clients WHERE id = $1::uuid LIMIT 1`, [clientId]);
    return (result.rowCount ?? 0) > 0;
  }

  async listByClient(clientId: string): Promise<PortalClientUserPublic[]> {
    const result = await this.db.query(
      `SELECT id, email, role, active, last_login_at, created_at, updated_at
       FROM portal_client_users
       WHERE client_id = $1::uuid
       ORDER BY active DESC, email ASC`,
      [clientId],
    );
    return result.rows.map((row) => mapRow(row as Record<string, unknown>));
  }

  async findById(clientId: string, userId: string): Promise<PortalClientUserPublic | null> {
    const result = await this.db.query(
      `SELECT id, email, role, active, last_login_at, created_at, updated_at
       FROM portal_client_users
       WHERE id = $1::uuid AND client_id = $2::uuid
       LIMIT 1`,
      [userId, clientId],
    );
    if (!result.rows.length) return null;
    return mapRow(result.rows[0] as Record<string, unknown>);
  }

  async emailTaken(email: string, excludeUserId?: string): Promise<boolean> {
    const normalized = email.trim().toLowerCase();
    const result = excludeUserId
      ? await this.db.query(
          `SELECT 1 FROM portal_client_users WHERE lower(email) = $1 AND id <> $2::uuid LIMIT 1`,
          [normalized, excludeUserId],
        )
      : await this.db.query(`SELECT 1 FROM portal_client_users WHERE lower(email) = $1 LIMIT 1`, [normalized]);
    return (result.rowCount ?? 0) > 0;
  }

  async insertUser(params: {
    clientId: string;
    email: string;
    passwordHash: string;
    role: PortalClientRole;
  }): Promise<PortalClientUserPublic> {
    const normalized = params.email.trim().toLowerCase();
    const result = await this.db.query(
      `INSERT INTO portal_client_users (client_id, email, password_hash, role, active)
       VALUES ($1::uuid, $2, $3, $4, TRUE)
       RETURNING id, email, role, active, last_login_at, created_at, updated_at`,
      [params.clientId, normalized, params.passwordHash, params.role],
    );
    return mapRow(result.rows[0] as Record<string, unknown>);
  }

  async updateUser(
    clientId: string,
    userId: string,
    patch: { role?: PortalClientRole; active?: boolean },
  ): Promise<PortalClientUserPublic | null> {
    const sets: string[] = ['updated_at = NOW()'];
    const values: unknown[] = [userId, clientId];
    let idx = 3;
    if (patch.role !== undefined) {
      sets.push(`role = $${idx++}`);
      values.push(patch.role);
    }
    if (patch.active !== undefined) {
      sets.push(`active = $${idx++}`);
      values.push(patch.active);
    }
    if (sets.length === 1) {
      return this.findById(clientId, userId);
    }
    const result = await this.db.query(
      `UPDATE portal_client_users
       SET ${sets.join(', ')}
       WHERE id = $1::uuid AND client_id = $2::uuid
       RETURNING id, email, role, active, last_login_at, created_at, updated_at`,
      values,
    );
    if (!result.rows.length) return null;
    return mapRow(result.rows[0] as Record<string, unknown>);
  }

  async updatePassword(clientId: string, userId: string, passwordHash: string): Promise<boolean> {
    const result = await this.db.query(
      `UPDATE portal_client_users
       SET password_hash = $3, updated_at = NOW()
       WHERE id = $1::uuid AND client_id = $2::uuid`,
      [userId, clientId, passwordHash],
    );
    return (result.rowCount ?? 0) > 0;
  }
}
