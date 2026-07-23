import { Injectable, UnauthorizedException } from '@nestjs/common';
import { Pool } from 'pg';
import { AppConfigService, PortalStubUser } from '../config/app-config.service';
import { signPortalJwt, verifyPortalJwt, PortalJwtPayload, signPortalRefreshJwt, verifyPortalRefreshJwt } from './portal-jwt.util';
import { mapKeycloakToPortalPayload, verifyKeycloakAccessToken } from './portal-keycloak.util';
import { hashPortalPassword, verifyPortalPassword } from './portal-password.util';

export interface PortalLoginResult {
  access_token: string;
  refresh_token: string;
  token_type: 'Bearer';
  expires_in: number;
  refresh_expires_in: number;
  user: {
    id: string;
    email: string;
    client_id: string;
    role: 'viewer' | 'approver';
  };
}

@Injectable()
export class PortalAuthService {
  private pool: Pool | null = null;

  constructor(private readonly config: AppConfigService) {}

  private get db(): Pool {
    if (!this.pool) {
      this.pool = new Pool({ connectionString: this.config.databaseUrl });
    }
    return this.pool;
  }

  async login(email: string, password: string): Promise<PortalLoginResult> {
    const normalized = email.trim().toLowerCase();
    const user = await this.resolveUser(normalized, password);
    if (!user) {
      throw new UnauthorizedException({ error: 'Invalid credentials' });
    }
    const token = signPortalJwt(
      {
        sub: user.id,
        email: user.email,
        client_id: user.clientId,
        role: user.role,
      },
      this.config.portalJwtSecret,
      this.config.portalJwtTtlSec,
    );
    const refreshToken = signPortalRefreshJwt(
      user.id,
      user.clientId,
      this.config.portalJwtSecret,
      this.config.portalRefreshTtlSec,
    );
    return {
      access_token: token,
      refresh_token: refreshToken,
      token_type: 'Bearer',
      expires_in: this.config.portalJwtTtlSec,
      refresh_expires_in: this.config.portalRefreshTtlSec,
      user: {
        id: user.id,
        email: user.email,
        client_id: user.clientId,
        role: user.role,
      },
    };
  }

  async refresh(refreshToken: string): Promise<PortalLoginResult> {
    const payload = verifyPortalRefreshJwt(refreshToken, this.config.portalJwtSecret);
    if (!payload) {
      throw new UnauthorizedException({ error: 'Invalid or expired refresh token' });
    }
    const user = await this.resolveUserById(payload.sub, payload.client_id);
    if (!user) {
      throw new UnauthorizedException({ error: 'Invalid refresh subject' });
    }
    const token = signPortalJwt(
      {
        sub: user.id,
        email: user.email,
        client_id: user.clientId,
        role: user.role,
      },
      this.config.portalJwtSecret,
      this.config.portalJwtTtlSec,
    );
    const nextRefresh = signPortalRefreshJwt(
      user.id,
      user.clientId,
      this.config.portalJwtSecret,
      this.config.portalRefreshTtlSec,
    );
    return {
      access_token: token,
      refresh_token: nextRefresh,
      token_type: 'Bearer',
      expires_in: this.config.portalJwtTtlSec,
      refresh_expires_in: this.config.portalRefreshTtlSec,
      user: {
        id: user.id,
        email: user.email,
        client_id: user.clientId,
        role: user.role,
      },
    };
  }

  verifyToken(token: string): PortalJwtPayload {
    const nest = verifyPortalJwt(token, this.config.portalJwtSecret);
    if (nest && this.config.portalAuthMode !== 'keycloak') {
      return nest;
    }
    throw new UnauthorizedException({ error: 'Invalid or expired token' });
  }

  async verifyTokenAsync(token: string): Promise<PortalJwtPayload> {
    const mode = this.config.portalAuthMode;
    if (mode === 'keycloak' || mode === 'dual') {
      const issuer = this.config.keycloakIssuer;
      if (issuer) {
        const claims = await verifyKeycloakAccessToken(token, {
          issuer,
          audience: this.config.keycloakAudience,
          clientIdClaim: this.config.keycloakClientIdClaim,
        });
        if (claims) {
          const mapped = mapKeycloakToPortalPayload(claims, {
            issuer,
            audience: this.config.keycloakAudience,
            clientIdClaim: this.config.keycloakClientIdClaim,
          });
          if (mapped) {
            return mapped;
          }
        }
      }
      if (mode === 'keycloak') {
        throw new UnauthorizedException({ error: 'Invalid Keycloak token' });
      }
    }
    const payload = verifyPortalJwt(token, this.config.portalJwtSecret);
    if (!payload) {
      throw new UnauthorizedException({ error: 'Invalid or expired token' });
    }
    return payload;
  }

  private async resolveUser(email: string, password: string): Promise<(PortalStubUser & { id: string }) | null> {
    if (this.config.portalAllowStubUsers) {
      const stub = this.config.portalStubUsers.find(
        (u) => u.email === email && u.password === password,
      );
      if (stub) {
        return { ...stub, id: `stub:${stub.email}` };
      }
    }
    try {
      const result = await this.db.query(
        `SELECT id::text, client_id::text, email, password_hash, role
         FROM portal_client_users
         WHERE LOWER(email) = $1 AND active IS TRUE
         LIMIT 1`,
        [email],
      );
      const row = result.rows[0] as
        | { id: string; client_id: string; email: string; password_hash: string; role: string }
        | undefined;
      if (!row) {
        return null;
      }
      if (!this.verifyPassword(password, row.password_hash)) {
        return null;
      }
      void this.db.query(`UPDATE portal_client_users SET last_login_at = NOW() WHERE id = $1::uuid`, [
        row.id,
      ]);
      return {
        id: row.id,
        email: row.email,
        clientId: row.client_id,
        password,
        role: row.role === 'approver' ? 'approver' : 'viewer',
      };
    } catch {
      return null;
    }
  }

  private async resolveUserById(
    userId: string,
    clientId: string,
  ): Promise<(PortalStubUser & { id: string }) | null> {
    if (userId.startsWith('stub:') && this.config.portalAllowStubUsers) {
      const email = userId.slice('stub:'.length);
      const stub = this.config.portalStubUsers.find((u) => u.email === email && u.clientId === clientId);
      if (stub) {
        return { ...stub, id: userId };
      }
      return null;
    }
    try {
      const result = await this.db.query(
        `SELECT id::text, client_id::text, email, role
         FROM portal_client_users
         WHERE id = $1::uuid AND client_id = $2::uuid AND active IS TRUE
         LIMIT 1`,
        [userId, clientId],
      );
      const row = result.rows[0] as
        | { id: string; client_id: string; email: string; role: string }
        | undefined;
      if (!row) {
        return null;
      }
      return {
        id: row.id,
        email: row.email,
        clientId: row.client_id,
        password: '',
        role: row.role === 'approver' ? 'approver' : 'viewer',
      };
    } catch {
      return null;
    }
  }

  private verifyPassword(plain: string, stored: string): boolean {
    return verifyPortalPassword(plain, stored);
  }

  hashPasswordForSeed(plain: string): string {
    return hashPortalPassword(plain);
  }
}
