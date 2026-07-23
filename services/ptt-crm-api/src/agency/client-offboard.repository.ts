import { Injectable, OnModuleDestroy } from '@nestjs/common';
import { Pool, PoolClient } from 'pg';
import { AppConfigService } from '../config/app-config.service';
import { OffboardAuditRow } from './client-offboard.types';

interface ClientLockRow {
  status: string;
  tenant_locked: boolean;
}

@Injectable()
export class ClientOffboardRepository implements OnModuleDestroy {
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

  async tablesReady(): Promise<boolean> {
    const result = await this.db.query(
      `SELECT COUNT(*)::int AS c FROM information_schema.tables
       WHERE table_schema = 'public' AND table_name = 'client_offboard_audit'`,
    );
    const auditReady = Number(result.rows[0]?.c ?? 0) > 0;
    return auditReady && (await this.tenantLockedColumnReady());
  }

  async tenantLockedColumnReady(): Promise<boolean> {
    const col = await this.db.query(
      `SELECT COUNT(*)::int AS c FROM information_schema.columns
       WHERE table_schema = 'public' AND table_name = 'clients' AND column_name = 'tenant_locked'`,
    );
    return Number(col.rows[0]?.c ?? 0) > 0;
  }

  async clientExists(clientId: string): Promise<boolean> {
    const result = await this.db.query(`SELECT 1 FROM clients WHERE id = $1::uuid LIMIT 1`, [clientId]);
    return (result.rowCount ?? 0) > 0;
  }

  async getClientLockState(clientId: string): Promise<ClientLockRow | null> {
    if (!(await this.tenantLockedColumnReady())) {
      const result = await this.db.query(`SELECT status FROM clients WHERE id = $1::uuid LIMIT 1`, [clientId]);
      const row = result.rows[0];
      if (!row) return null;
      return { status: String(row.status ?? ''), tenant_locked: false };
    }
    const result = await this.db.query(
      `SELECT status, tenant_locked FROM clients WHERE id = $1::uuid LIMIT 1`,
      [clientId],
    );
    const row = result.rows[0];
    if (!row) return null;
    return {
      status: String(row.status ?? ''),
      tenant_locked: Boolean(row.tenant_locked),
    };
  }

  async isTenantLocked(clientId: string): Promise<boolean> {
    const state = await this.getClientLockState(clientId);
    return Boolean(state?.tenant_locked);
  }

  async findLatestAudit(clientId: string): Promise<OffboardAuditRow | null> {
    if (!(await this.tablesReady())) {
      return null;
    }
    const result = await this.db.query(
      `SELECT id::text, client_id::text, initiated_by, reason, note,
              tokens_revoked, portal_users_deactivated, previous_status, created_at
       FROM client_offboard_audit
       WHERE client_id = $1::uuid
       ORDER BY created_at DESC
       LIMIT 1`,
      [clientId],
    );
    const row = result.rows[0];
    return row ? this.mapAudit(row) : null;
  }

  async listAudit(clientId: string, limit = 20): Promise<OffboardAuditRow[]> {
    if (!(await this.tablesReady())) {
      return [];
    }
    const result = await this.db.query(
      `SELECT id::text, client_id::text, initiated_by, reason, note,
              tokens_revoked, portal_users_deactivated, previous_status, created_at
       FROM client_offboard_audit
       WHERE client_id = $1::uuid
       ORDER BY created_at DESC
       LIMIT $2`,
      [clientId, Math.min(100, Math.max(1, limit))],
    );
    return result.rows.map((row) => this.mapAudit(row));
  }

  async runOffboardTransaction(input: {
    clientId: string;
    initiatedBy: string;
    reason: string;
    note: string | null;
  }): Promise<{
    audit: OffboardAuditRow;
    tokensRevoked: number;
    portalUsersDeactivated: number;
    previousStatus: string;
    idempotent: boolean;
  }> {
    if (!(await this.tablesReady())) {
      throw new Error('offboard_tables_not_ready');
    }
    const conn = await this.db.connect();
    try {
      await conn.query('BEGIN');
      const lockResult = await conn.query(
        `SELECT status, tenant_locked FROM clients WHERE id = $1::uuid FOR UPDATE`,
        [input.clientId],
      );
      const lockRow = lockResult.rows[0];
      if (!lockRow) {
        throw new Error('client_not_found');
      }
      const previousStatus = String(lockRow.status ?? '');
      const tenantLocked = Boolean(lockRow.tenant_locked);
      if (tenantLocked && previousStatus === 'archived') {
        const existing = await this.findLatestAuditInTx(conn, input.clientId);
        if (existing) {
          await conn.query('COMMIT');
          return {
            audit: existing,
            tokensRevoked: existing.tokens_revoked,
            portalUsersDeactivated: existing.portal_users_deactivated,
            previousStatus: existing.previous_status ?? previousStatus,
            idempotent: true,
          };
        }
      }

      await conn.query(`UPDATE clients SET status = 'offboarding', updated_at = NOW() WHERE id = $1::uuid`, [
        input.clientId,
      ]);

      const tokenResult = await conn.query(
        `UPDATE client_channel_accounts
         SET access_token_encrypted = NULL,
             credential_ref = NULL,
             token_status = 'revoked',
             last_token_refresh_at = NOW(),
             updated_at = NOW()
         WHERE client_id = $1::uuid
           AND (
             access_token_encrypted IS NOT NULL
             OR NULLIF(credential_ref, '') IS NOT NULL
             OR COALESCE(token_status, '') <> 'revoked'
           )`,
        [input.clientId],
      );
      const tokensRevoked = tokenResult.rowCount ?? 0;

      let portalUsersDeactivated = 0;
      const portalTable = await conn.query(
        `SELECT COUNT(*)::int AS c FROM information_schema.tables
         WHERE table_schema = 'public' AND table_name = 'portal_client_users'`,
      );
      if (Number(portalTable.rows[0]?.c ?? 0) > 0) {
        const portalResult = await conn.query(
          `UPDATE portal_client_users
           SET active = FALSE, updated_at = NOW()
           WHERE client_id = $1::uuid AND active IS TRUE`,
          [input.clientId],
        );
        portalUsersDeactivated = portalResult.rowCount ?? 0;
      }

      await conn.query(
        `UPDATE clients
         SET status = 'archived', tenant_locked = TRUE, updated_at = NOW()
         WHERE id = $1::uuid`,
        [input.clientId],
      );

      const auditInsert = await conn.query(
        `INSERT INTO client_offboard_audit (
           client_id, initiated_by, reason, note, tokens_revoked,
           portal_users_deactivated, previous_status
         ) VALUES ($1::uuid, $2, $3, $4, $5, $6, $7)
         RETURNING id::text, client_id::text, initiated_by, reason, note,
                   tokens_revoked, portal_users_deactivated, previous_status, created_at`,
        [
          input.clientId,
          input.initiatedBy,
          input.reason,
          input.note,
          tokensRevoked,
          portalUsersDeactivated,
          previousStatus,
        ],
      );
      await conn.query('COMMIT');
      const audit = this.mapAudit(auditInsert.rows[0]);
      return {
        audit,
        tokensRevoked,
        portalUsersDeactivated,
        previousStatus,
        idempotent: false,
      };
    } catch (err) {
      await conn.query('ROLLBACK');
      throw err;
    } finally {
      conn.release();
    }
  }

  private async findLatestAuditInTx(conn: PoolClient, clientId: string): Promise<OffboardAuditRow | null> {
    const result = await conn.query(
      `SELECT id::text, client_id::text, initiated_by, reason, note,
              tokens_revoked, portal_users_deactivated, previous_status, created_at
       FROM client_offboard_audit
       WHERE client_id = $1::uuid
       ORDER BY created_at DESC
       LIMIT 1`,
      [clientId],
    );
    const row = result.rows[0];
    return row ? this.mapAudit(row) : null;
  }

  private mapAudit(row: Record<string, unknown>): OffboardAuditRow {
    return {
      id: String(row.id),
      client_id: String(row.client_id),
      initiated_by: String(row.initiated_by ?? ''),
      reason: String(row.reason ?? ''),
      note: row.note != null ? String(row.note) : null,
      tokens_revoked: Number(row.tokens_revoked ?? 0),
      portal_users_deactivated: Number(row.portal_users_deactivated ?? 0),
      previous_status: row.previous_status != null ? String(row.previous_status) : null,
      created_at: row.created_at instanceof Date ? row.created_at.toISOString() : String(row.created_at ?? ''),
    };
  }
}
