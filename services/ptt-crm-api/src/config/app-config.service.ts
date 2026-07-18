import { Injectable } from '@nestjs/common';
import * as fs from 'fs';
import * as path from 'path';

export type LeadsReadSource = 'sqlite' | 'pg';
export type LeadsCreateIdMode = 'staging' | 'prod';
export type PortalAuthMode = 'nest-jwt' | 'keycloak' | 'dual';

export interface PortalStubUser {
  email: string;
  password: string;
  clientId: string;
  role: 'viewer' | 'approver';
}

@Injectable()
export class AppConfigService {
  readonly port: number;
  readonly sqlitePath: string;
  readonly databaseUrl: string;
  readonly leadsReadSource: LeadsReadSource;
  readonly internalKey: string | null;
  readonly authDisabled: boolean;
  readonly leadsWriteEnabled: boolean;
  readonly leadsCreateIdMode: LeadsCreateIdMode;
  readonly portalJwtSecret: string;
  readonly portalJwtTtlSec: number;
  readonly portalStubUsers: PortalStubUser[];
  readonly portalCorsOrigins: string[];
  readonly portalAuthMode: PortalAuthMode;
  readonly portalAllowStubUsers: boolean;
  readonly keycloakIssuer: string | null;
  readonly keycloakAudience: string;
  readonly keycloakClientIdClaim: string;
  readonly temporalAddress: string | null;
  readonly temporalNamespace: string;
  readonly temporalTaskQueue: string;

  constructor() {
    this.port = Number(process.env.PORT ?? process.env.CRM_API_PORT ?? 3000);
    this.sqlitePath = this.resolveSqlitePath();
    this.databaseUrl = (
      process.env.DATABASE_URL ??
      process.env.PTT_DATABASE_URL ??
      'postgresql://ptt:ptt_dev@127.0.0.1:5432/ptt_agency'
    ).trim();
    this.leadsReadSource = this.resolveLeadsReadSource();
    this.internalKey = (process.env.PTT_CRM_INTERNAL_KEY ?? '').trim() || null;
    this.authDisabled = ['1', 'true', 'yes', 'on'].includes(
      (process.env.PTT_CRM_API_AUTH_DISABLED ?? '0').trim().toLowerCase(),
    );
    this.leadsWriteEnabled = ['1', 'true', 'yes', 'on'].includes(
      (process.env.PTT_LEADS_WRITE_ENABLED ?? '0').trim().toLowerCase(),
    );
    this.leadsCreateIdMode = this.resolveLeadsCreateIdMode();
    this.portalJwtSecret = (
      process.env.PTT_PORTAL_JWT_SECRET ??
      process.env.PTT_CRM_INTERNAL_KEY ??
      'dev-portal-jwt-change-me'
    ).trim();
    this.portalJwtTtlSec = Math.max(
      300,
      Number(process.env.PTT_PORTAL_JWT_TTL_SEC ?? 28800) || 28800,
    );
    this.portalStubUsers = this.parsePortalStubUsers();
    this.portalCorsOrigins = this.parsePortalCorsOrigins();
    this.portalAuthMode = this.resolvePortalAuthMode();
    this.portalAllowStubUsers = this.resolvePortalAllowStubUsers();
    this.keycloakIssuer = (process.env.PTT_KEYCLOAK_ISSUER ?? '').trim() || null;
    this.keycloakAudience = (process.env.PTT_KEYCLOAK_AUDIENCE ?? 'ptt-portal').trim();
    this.keycloakClientIdClaim = (process.env.PTT_KEYCLOAK_CLIENT_ID_CLAIM ?? 'client_id').trim();
    this.temporalAddress = (process.env.PTT_TEMPORAL_ADDRESS ?? '').trim() || null;
    this.temporalNamespace = (process.env.PTT_TEMPORAL_NAMESPACE ?? 'default').trim();
    this.temporalTaskQueue = (process.env.PTT_TEMPORAL_TASK_QUEUE ?? 'ptt-agency').trim();
  }

  private parsePortalCorsOrigins(): string[] {
    const raw = (process.env.PTT_PORTAL_CORS_ORIGINS ?? 'http://127.0.0.1:3100,http://localhost:3100')
      .trim();
    return raw
      .split(',')
      .map((s) => s.trim())
      .filter(Boolean);
  }

  private resolveLeadsCreateIdMode(): LeadsCreateIdMode {
    const raw = (process.env.PTT_LEADS_CREATE_ID_MODE ?? 'staging').trim().toLowerCase();
    return raw === 'prod' ? 'prod' : 'staging';
  }

  private parsePortalStubUsers(): PortalStubUser[] {
    const raw = (process.env.PTT_PORTAL_STUB_USERS ?? '').trim();
    if (!raw) {
      return [];
    }
    const out: PortalStubUser[] = [];
    for (const part of raw.split(',')) {
      const seg = part.trim();
      if (!seg) continue;
      const [email, password, clientId, role] = seg.split(':').map((s) => s.trim());
      if (!email || !password || !clientId) continue;
      out.push({
        email: email.toLowerCase(),
        password,
        clientId,
        role: role === 'approver' ? 'approver' : 'viewer',
      });
    }
    return out;
  }

  private resolveSqlitePath(): string {
    const fromEnv = (process.env.PTT_SQLITE_PATH ?? '').trim();
    if (fromEnv) {
      return path.isAbsolute(fromEnv) ? fromEnv : path.resolve(process.cwd(), fromEnv);
    }
    return path.resolve(__dirname, '..', '..', '..', 'ptt.db');
  }

  private resolveLeadsReadSource(): LeadsReadSource {
    const explicit = (process.env.PTT_LEADS_READ_SOURCE ?? '').trim().toLowerCase();
    if (explicit === 'sqlite' || explicit === 'pg') {
      return explicit;
    }
    return 'pg';
  }

  private resolvePortalAuthMode(): PortalAuthMode {
    const raw = (process.env.PTT_PORTAL_AUTH_MODE ?? 'nest-jwt').trim().toLowerCase();
    if (raw === 'keycloak' || raw === 'dual') {
      return raw;
    }
    return 'nest-jwt';
  }

  private resolvePortalAllowStubUsers(): boolean {
    const explicit = (process.env.PTT_PORTAL_ALLOW_STUB ?? '').trim().toLowerCase();
    if (explicit) {
      return ['1', 'true', 'yes', 'on'].includes(explicit);
    }
    const nodeEnv = (process.env.NODE_ENV ?? '').trim().toLowerCase();
    return nodeEnv !== 'production';
  }

  sqliteAvailable(): boolean {
    try {
      return fs.existsSync(this.sqlitePath);
    } catch {
      return false;
    }
  }
}
