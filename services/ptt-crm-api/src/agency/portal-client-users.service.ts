import {
  BadRequestException,
  ConflictException,
  Injectable,
  NotFoundException,
  ServiceUnavailableException,
} from '@nestjs/common';
import { randomBytes } from 'crypto';
import { ClientOffboardService } from './client-offboard.service';
import { PortalClientUsersRepository } from './portal-client-users.repository';
import {
  CreatePortalClientUserBody,
  CreatePortalClientUserResponse,
  PortalClientRole,
  PortalClientUsersListResponse,
  PortalClientUserPublic,
  ResetPortalClientUserPasswordBody,
  ResetPortalClientUserPasswordResponse,
  UpdatePortalClientUserBody,
} from './portal-client-users.types';
import { hashPortalPassword } from '../portal/portal-password.util';

const EMAIL_RE = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;
const MIN_PASSWORD_LEN = 8;

@Injectable()
export class PortalClientUsersService {
  constructor(
    private readonly repo: PortalClientUsersRepository,
    private readonly tenantLock: ClientOffboardService,
  ) {}

  async list(clientId: string): Promise<PortalClientUsersListResponse> {
    await this.assertClientExists(clientId);
    const tableReady = await this.repo.tableReady();
    if (!tableReady) {
      return { ok: true, client_id: clientId, users: [], table_ready: false };
    }
    const users = await this.repo.listByClient(clientId);
    return { ok: true, client_id: clientId, users, table_ready: true };
  }

  async create(clientId: string, body: CreatePortalClientUserBody): Promise<CreatePortalClientUserResponse> {
    await this.ensureWritable(clientId);
    if (!(await this.repo.tableReady())) {
      throw new ServiceUnavailableException({ ok: false, error: 'portal_users_table_not_ready' });
    }

    const email = body.email?.trim().toLowerCase() ?? '';
    if (!EMAIL_RE.test(email)) {
      throw new BadRequestException({ error: 'invalid_email' });
    }

    const role = this.normalizeRole(body.role);
    let temporaryPassword: string | undefined;
    let plainPassword = body.password?.trim() ?? '';
    if (!plainPassword) {
      temporaryPassword = this.generateTemporaryPassword();
      plainPassword = temporaryPassword;
    } else if (plainPassword.length < MIN_PASSWORD_LEN) {
      throw new BadRequestException({ error: 'password_too_short', min_length: MIN_PASSWORD_LEN });
    }

    if (await this.repo.emailTaken(email)) {
      throw new ConflictException({ error: 'email_already_registered', email });
    }

    const passwordHash = hashPortalPassword(plainPassword);
    let user: PortalClientUserPublic;
    try {
      user = await this.repo.insertUser({ clientId, email, passwordHash, role });
    } catch (err) {
      const code = (err as { code?: string })?.code;
      if (code === '23505') {
        throw new ConflictException({ error: 'email_already_registered', email });
      }
      throw err;
    }

    return {
      ok: true,
      user,
      ...(temporaryPassword ? { temporary_password: temporaryPassword } : {}),
    };
  }

  async update(
    clientId: string,
    userId: string,
    body: UpdatePortalClientUserBody,
  ): Promise<PortalClientUserPublic> {
    await this.ensureWritable(clientId);
    if (!(await this.repo.tableReady())) {
      throw new ServiceUnavailableException({ ok: false, error: 'portal_users_table_not_ready' });
    }

    if (body.role === undefined && body.active === undefined) {
      throw new BadRequestException({ error: 'no_updates' });
    }

    const patch: { role?: PortalClientRole; active?: boolean } = {};
    if (body.role !== undefined) {
      patch.role = this.normalizeRole(body.role);
    }
    if (body.active !== undefined) {
      patch.active = Boolean(body.active);
    }

    const updated = await this.repo.updateUser(clientId, userId, patch);
    if (!updated) {
      throw new NotFoundException({ error: 'portal_user_not_found' });
    }
    return updated;
  }

  async resetPassword(
    clientId: string,
    userId: string,
    body: ResetPortalClientUserPasswordBody,
  ): Promise<ResetPortalClientUserPasswordResponse> {
    await this.ensureWritable(clientId);
    if (!(await this.repo.tableReady())) {
      throw new ServiceUnavailableException({ ok: false, error: 'portal_users_table_not_ready' });
    }

    const existing = await this.repo.findById(clientId, userId);
    if (!existing) {
      throw new NotFoundException({ error: 'portal_user_not_found' });
    }

    let temporaryPassword: string | undefined;
    let plainPassword = body.password?.trim() ?? '';
    if (!plainPassword) {
      temporaryPassword = this.generateTemporaryPassword();
      plainPassword = temporaryPassword;
    } else if (plainPassword.length < MIN_PASSWORD_LEN) {
      throw new BadRequestException({ error: 'password_too_short', min_length: MIN_PASSWORD_LEN });
    }

    const ok = await this.repo.updatePassword(clientId, userId, hashPortalPassword(plainPassword));
    if (!ok) {
      throw new NotFoundException({ error: 'portal_user_not_found' });
    }

    return {
      ok: true,
      ...(temporaryPassword ? { temporary_password: temporaryPassword } : {}),
    };
  }

  private async assertClientExists(clientId: string): Promise<void> {
    if (!(await this.repo.clientExists(clientId))) {
      throw new NotFoundException({ error: 'Not found' });
    }
  }

  private async ensureWritable(clientId: string): Promise<void> {
    await this.assertClientExists(clientId);
    await this.tenantLock.assertClientWritable(clientId);
  }

  private normalizeRole(role: unknown): PortalClientRole {
    const value = String(role ?? 'viewer').trim().toLowerCase();
    if (value === 'approver') return 'approver';
    if (value === 'viewer') return 'viewer';
    throw new BadRequestException({ error: 'invalid_role', allowed: ['viewer', 'approver'] });
  }

  private generateTemporaryPassword(): string {
    const raw = randomBytes(9).toString('base64url');
    return `Pt${raw}!`;
  }
}
