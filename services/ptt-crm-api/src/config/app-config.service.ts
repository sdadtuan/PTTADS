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

export interface StaffStubUser {
  email: string;
  password: string;
  staffId: string;
  positionId: number;
  displayName: string;
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
  readonly opsCorsOrigins: string[];
  readonly portalAuthMode: PortalAuthMode;
  readonly portalAllowStubUsers: boolean;
  readonly staffJwtSecret: string;
  readonly staffJwtTtlSec: number;
  readonly staffRefreshTtlSec: number;
  readonly staffStubUsers: StaffStubUser[];
  readonly staffAllowStubUsers: boolean;
  readonly flaskMonolithUrl: string;
  readonly jobsEnabled: boolean;
  readonly webhookEnqueueEnabled: boolean;
  readonly webhooksNestEnabled: boolean;
  readonly webhooksNestMetaEnabled: boolean;
  readonly webhooksNestZaloEnabled: boolean;
  readonly webhooksNestGoogleEnabled: boolean;
  readonly webhooksNestEmailEnabled: boolean;
  readonly webhooksFlaskFallback: boolean;
  readonly emailSendEnabled: boolean;
  readonly keycloakIssuer: string | null;
  readonly keycloakAudience: string;
  readonly keycloakClientIdClaim: string;
  readonly temporalAddress: string | null;
  readonly temporalNamespace: string;
  readonly temporalTaskQueue: string;
  readonly crmLeadsFunnelNest: boolean;
  readonly presalesOnLead: boolean;
  readonly crmServiceDeliveryNest: boolean;
  readonly sopAutoStartOnLaunch: boolean;
  readonly sopOverdueEscalate: boolean;

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
    this.opsCorsOrigins = this.parseOpsCorsOrigins();
    this.portalAuthMode = this.resolvePortalAuthMode();
    this.portalAllowStubUsers = this.resolvePortalAllowStubUsers();
    this.staffJwtSecret = (
      process.env.PTT_STAFF_JWT_SECRET ??
      process.env.PTT_CRM_INTERNAL_KEY ??
      'dev-staff-jwt-change-me'
    ).trim();
    this.staffJwtTtlSec = Math.max(
      300,
      Number(process.env.PTT_STAFF_JWT_TTL_SEC ?? 28800) || 28800,
    );
    this.staffRefreshTtlSec = Math.max(
      3600,
      Number(process.env.PTT_STAFF_REFRESH_TTL_SEC ?? 604800) || 604800,
    );
    this.staffStubUsers = this.parseStaffStubUsers();
    this.staffAllowStubUsers = this.resolveStaffAllowStubUsers();
    this.flaskMonolithUrl = (process.env.PTT_FLASK_MONOLITH_URL ?? '').trim();
    this.jobsEnabled = this.resolveJobsEnabled();
    this.webhookEnqueueEnabled = this.resolveWebhookEnqueueEnabled();
    this.webhooksNestEnabled = this.resolveWebhooksNestEnabled();
    this.webhooksNestMetaEnabled = this.resolveWebhooksNestMetaEnabled();
    this.webhooksNestZaloEnabled = this.resolveWebhooksNestZaloEnabled();
    this.webhooksNestGoogleEnabled = this.resolveWebhooksNestGoogleEnabled();
    this.webhooksNestEmailEnabled = this.resolveWebhooksNestEmailEnabled();
    this.webhooksFlaskFallback = this.resolveWebhooksFlaskFallback();
    this.emailSendEnabled = this.resolveEmailSendEnabled();
    this.keycloakIssuer = (process.env.PTT_KEYCLOAK_ISSUER ?? '').trim() || null;
    this.keycloakAudience = (process.env.PTT_KEYCLOAK_AUDIENCE ?? 'ptt-portal').trim();
    this.keycloakClientIdClaim = (process.env.PTT_KEYCLOAK_CLIENT_ID_CLAIM ?? 'client_id').trim();
    this.temporalAddress = (process.env.PTT_TEMPORAL_ADDRESS ?? '').trim() || null;
    this.temporalNamespace = (process.env.PTT_TEMPORAL_NAMESPACE ?? 'default').trim();
    this.temporalTaskQueue = (process.env.PTT_TEMPORAL_TASK_QUEUE ?? 'ptt-agency').trim();
    this.crmLeadsFunnelNest = ['1', 'true', 'yes', 'on'].includes(
      (process.env.PTT_CRM_LEADS_FUNNEL_NEST ?? '1').trim().toLowerCase(),
    );
    this.presalesOnLead = ['1', 'true', 'yes', 'on'].includes(
      (process.env.PTT_PRESALES_ON_LEAD ?? '1').trim().toLowerCase(),
    );
    this.crmServiceDeliveryNest = ['1', 'true', 'yes', 'on'].includes(
      (process.env.PTT_CRM_SERVICE_DELIVERY_NEST ?? '0').trim().toLowerCase(),
    );
    this.sopAutoStartOnLaunch = ['1', 'true', 'yes', 'on'].includes(
      (process.env.PTT_SOP_AUTO_START_ON_LAUNCH ?? '0').trim().toLowerCase(),
    );
    this.sopOverdueEscalate = ['1', 'true', 'yes', 'on'].includes(
      (process.env.PTT_SOP_OVERDUE_ESCALATE ?? '0').trim().toLowerCase(),
    );
  }

  private parsePortalCorsOrigins(): string[] {
    const raw = (process.env.PTT_PORTAL_CORS_ORIGINS ?? 'http://127.0.0.1:3100,http://localhost:3100')
      .trim();
    return raw
      .split(',')
      .map((s) => s.trim())
      .filter(Boolean);
  }

  private parseOpsCorsOrigins(): string[] {
    const raw = (
      process.env.PTT_OPS_CORS_ORIGINS ?? 'http://127.0.0.1:3200,http://localhost:3200'
    ).trim();
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

  private parseStaffStubUsers(): StaffStubUser[] {
    const raw = (process.env.PTT_STAFF_STUB_USERS ?? '').trim();
    if (!raw) {
      return [];
    }
    const out: StaffStubUser[] = [];
    for (const part of raw.split(',')) {
      const seg = part.trim();
      if (!seg) continue;
      const [email, password, staffId, positionIdRaw, displayName] = seg
        .split(':')
        .map((s) => s.trim());
      if (!email || !password || !staffId) continue;
      const positionId = Number(positionIdRaw || 1);
      out.push({
        email: email.toLowerCase(),
        password,
        staffId,
        positionId: Number.isFinite(positionId) ? positionId : 1,
        displayName: displayName || email,
      });
    }
    return out;
  }

  private resolveStaffAllowStubUsers(): boolean {
    const explicit = (process.env.PTT_STAFF_ALLOW_STUB ?? '').trim().toLowerCase();
    if (explicit) {
      return ['1', 'true', 'yes', 'on'].includes(explicit);
    }
    const nodeEnv = (process.env.NODE_ENV ?? '').trim().toLowerCase();
    return nodeEnv !== 'production';
  }

  private resolveJobsEnabled(): boolean {
    if (['1', 'true', 'yes', 'on'].includes((process.env.PTT_JOBS_DISABLED ?? '0').trim().toLowerCase())) {
      return false;
    }
    return ['1', 'true', 'yes', 'on'].includes((process.env.PTT_JOBS_ENABLED ?? '1').trim().toLowerCase());
  }

  private resolveWebhookEnqueueEnabled(): boolean {
    return ['1', 'true', 'yes', 'on'].includes(
      (process.env.PTT_WEBHOOK_V1_ENQUEUE ?? '1').trim().toLowerCase(),
    );
  }

  private resolveWebhooksNestEnabled(): boolean {
    return ['1', 'true', 'yes', 'on'].includes(
      (process.env.PTT_WEBHOOKS_NEST_ENABLED ?? '1').trim().toLowerCase(),
    );
  }

  private resolveWebhooksNestMetaEnabled(): boolean {
    return ['1', 'true', 'yes', 'on'].includes(
      (process.env.PTT_WEBHOOKS_NEST_META ?? '1').trim().toLowerCase(),
    );
  }

  private resolveWebhooksNestZaloEnabled(): boolean {
    return ['1', 'true', 'yes', 'on'].includes(
      (process.env.PTT_WEBHOOKS_NEST_ZALO ?? '1').trim().toLowerCase(),
    );
  }

  private resolveWebhooksNestGoogleEnabled(): boolean {
    return ['1', 'true', 'yes', 'on'].includes(
      (process.env.PTT_WEBHOOKS_NEST_GOOGLE ?? '1').trim().toLowerCase(),
    );
  }

  private resolveWebhooksNestEmailEnabled(): boolean {
    return ['1', 'true', 'yes', 'on'].includes(
      (process.env.PTT_WEBHOOKS_NEST_EMAIL ?? '1').trim().toLowerCase(),
    );
  }

  private resolveEmailSendEnabled(): boolean {
    return ['1', 'true', 'yes', 'on'].includes(
      (process.env.PTT_EMAIL_SEND_ENABLED ?? '1').trim().toLowerCase(),
    );
  }

  private resolveWebhooksFlaskFallback(): boolean {
    return ['1', 'true', 'yes', 'on'].includes(
      (process.env.PTT_WEBHOOKS_FLASK_FALLBACK ?? '0').trim().toLowerCase(),
    );
  }

  sqliteAvailable(): boolean {
    try {
      return fs.existsSync(this.sqlitePath);
    } catch {
      return false;
    }
  }
}
