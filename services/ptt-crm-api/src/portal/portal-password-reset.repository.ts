import { Injectable, OnModuleDestroy } from '@nestjs/common';
import { Pool } from 'pg';
import { AppConfigService } from '../config/app-config.service';
import { PortalPasswordResetUserRow } from './portal-password-reset.types';

@Injectable()
export class PortalPasswordResetRepository implements OnModuleDestroy {
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
    try {
      const users = await this.db.query(
        `SELECT 1 FROM information_schema.tables WHERE table_name = 'portal_client_users'`,
      );
      const tokens = await this.db.query(
        `SELECT 1 FROM information_schema.tables WHERE table_name = 'portal_password_reset_tokens'`,
      );
      return (users.rowCount ?? 0) > 0 && (tokens.rowCount ?? 0) > 0;
    } catch {
      return false;
    }
  }

  async findActiveUserByEmail(email: string): Promise<PortalPasswordResetUserRow | null> {
    const result = await this.db.query(
      `SELECT id::text, client_id::text, email, password_hash
       FROM portal_client_users
       WHERE LOWER(email) = $1 AND active IS TRUE
       LIMIT 1`,
      [email.trim().toLowerCase()],
    );
    const row = result.rows[0] as PortalPasswordResetUserRow | undefined;
    return row ?? null;
  }

  async findUserById(userId: string, clientId: string): Promise<PortalPasswordResetUserRow | null> {
    const result = await this.db.query(
      `SELECT id::text, client_id::text, email, password_hash
       FROM portal_client_users
       WHERE id = $1::uuid AND client_id = $2::uuid AND active IS TRUE
       LIMIT 1`,
      [userId, clientId],
    );
    const row = result.rows[0] as PortalPasswordResetUserRow | undefined;
    return row ?? null;
  }

  async invalidateUserTokens(userId: string): Promise<void> {
    await this.db.query(
      `UPDATE portal_password_reset_tokens SET used_at = NOW()
       WHERE user_id = $1::uuid AND used_at IS NULL`,
      [userId],
    );
  }

  async insertToken(userId: string, tokenHash: string, expiresAt: Date): Promise<void> {
    await this.db.query(
      `INSERT INTO portal_password_reset_tokens (user_id, token_hash, expires_at)
       VALUES ($1::uuid, $2, $3)`,
      [userId, tokenHash, expiresAt.toISOString()],
    );
  }

  async findValidToken(tokenHash: string): Promise<{ token_id: string; user_id: string; email: string; client_id: string } | null> {
    const result = await this.db.query(
      `SELECT t.id::text AS token_id, u.id::text AS user_id, u.email, u.client_id::text AS client_id
       FROM portal_password_reset_tokens t
       JOIN portal_client_users u ON u.id = t.user_id
       WHERE t.token_hash = $1
         AND t.used_at IS NULL
         AND t.expires_at > NOW()
         AND u.active IS TRUE
       LIMIT 1`,
      [tokenHash],
    );
    const row = result.rows[0] as
      | { token_id: string; user_id: string; email: string; client_id: string }
      | undefined;
    return row ?? null;
  }

  async markTokenUsed(tokenId: string): Promise<void> {
    await this.db.query(
      `UPDATE portal_password_reset_tokens SET used_at = NOW() WHERE id = $1::uuid`,
      [tokenId],
    );
  }

  async updatePassword(userId: string, passwordHash: string): Promise<void> {
    await this.db.query(
      `UPDATE portal_client_users SET password_hash = $2, updated_at = NOW() WHERE id = $1::uuid`,
      [userId, passwordHash],
    );
  }
}
