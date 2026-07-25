import {
  BadRequestException,
  ForbiddenException,
  Injectable,
  ServiceUnavailableException,
  UnauthorizedException,
} from '@nestjs/common';
import { createHash, randomBytes } from 'crypto';
import { ClientOffboardService } from '../agency/client-offboard.service';
import { AppConfigService } from '../config/app-config.service';
import { hashPortalPassword, verifyPortalPassword } from './portal-password.util';
import { PortalPasswordResetNotifyService } from './portal-password-reset-notify.service';
import { PortalPasswordResetRepository } from './portal-password-reset.repository';
import {
  PortalChangePasswordResponse,
  PortalForgotPasswordResponse,
  PortalResetPasswordResponse,
  PortalValidateResetTokenResponse,
} from './portal-password-reset.types';

const MIN_PASSWORD_LEN = 8;
const GENERIC_FORGOT_MSG =
  'Nếu email tồn tại trong hệ thống, bạn sẽ nhận link đặt lại mật khẩu trong vài phút.';

function hashResetToken(raw: string): string {
  return createHash('sha256').update(raw).digest('hex');
}

function maskEmail(email: string): string {
  const [local, domain] = email.split('@');
  if (!domain) return '***';
  const head = local.slice(0, 1);
  return `${head}***@${domain}`;
}

@Injectable()
export class PortalPasswordResetService {
  constructor(
    private readonly repo: PortalPasswordResetRepository,
    private readonly notify: PortalPasswordResetNotifyService,
    private readonly tenantLock: ClientOffboardService,
    private readonly config: AppConfigService,
  ) {}

  async forgotPassword(email: string): Promise<PortalForgotPasswordResponse> {
    const normalized = email.trim().toLowerCase();
    if (!normalized.includes('@')) {
      throw new BadRequestException({ error: 'invalid_email' });
    }

    if (!(await this.repo.tablesReady())) {
      throw new ServiceUnavailableException({ ok: false, error: 'password_reset_not_ready' });
    }

    const user = await this.repo.findActiveUserByEmail(normalized);
    if (!user) {
      return { ok: true, message: GENERIC_FORGOT_MSG };
    }

    try {
      await this.tenantLock.assertPortalTenantActive(user.client_id);
    } catch (err) {
      if (err instanceof ForbiddenException) {
        return { ok: true, message: GENERIC_FORGOT_MSG };
      }
      throw err;
    }

    const rawToken = randomBytes(32).toString('base64url');
    const tokenHash = hashResetToken(rawToken);
    const expiresAt = new Date(Date.now() + this.config.portalResetTtlMin * 60 * 1000);

    await this.repo.invalidateUserTokens(user.id);
    await this.repo.insertToken(user.id, tokenHash, expiresAt);

    const resetUrl = `${this.config.portalPublicUrl.replace(/\/$/, '')}/reset-password?token=${encodeURIComponent(rawToken)}`;
    await this.notify.sendResetEmail({
      to: user.email,
      resetUrl,
      expiresMinutes: this.config.portalResetTtlMin,
    });

    const response: PortalForgotPasswordResponse = { ok: true, message: GENERIC_FORGOT_MSG };
    if (process.env.NODE_ENV !== 'production' && !this.config.portalEmailNotifyEnabled) {
      response.reset_url = resetUrl;
    }
    return response;
  }

  async validateResetToken(rawToken: string): Promise<PortalValidateResetTokenResponse> {
    if (!(await this.repo.tablesReady())) {
      return { ok: false, error: 'password_reset_not_ready' };
    }
    const token = rawToken?.trim();
    if (!token) {
      return { ok: false, error: 'invalid_token' };
    }
    const row = await this.repo.findValidToken(hashResetToken(token));
    if (!row) {
      return { ok: false, error: 'invalid_or_expired_token' };
    }
    try {
      await this.tenantLock.assertPortalTenantActive(row.client_id);
    } catch {
      return { ok: false, error: 'invalid_or_expired_token' };
    }
    return { ok: true, email_masked: maskEmail(row.email) };
  }

  async resetPassword(rawToken: string, newPassword: string): Promise<PortalResetPasswordResponse> {
    if (!(await this.repo.tablesReady())) {
      throw new ServiceUnavailableException({ ok: false, error: 'password_reset_not_ready' });
    }
    const token = rawToken?.trim();
    const plain = newPassword?.trim() ?? '';
    if (!token) {
      throw new BadRequestException({ error: 'invalid_token' });
    }
    if (plain.length < MIN_PASSWORD_LEN) {
      throw new BadRequestException({ error: 'password_too_short', min_length: MIN_PASSWORD_LEN });
    }

    const row = await this.repo.findValidToken(hashResetToken(token));
    if (!row) {
      throw new BadRequestException({ error: 'invalid_or_expired_token' });
    }
    await this.tenantLock.assertPortalTenantActive(row.client_id);

    await this.repo.updatePassword(row.user_id, hashPortalPassword(plain));
    await this.repo.markTokenUsed(row.token_id);
    await this.repo.invalidateUserTokens(row.user_id);

    return { ok: true, message: 'password_updated' };
  }

  async changePassword(
    userId: string,
    clientId: string,
    currentPassword: string,
    newPassword: string,
  ): Promise<PortalChangePasswordResponse> {
    if (!(await this.repo.tablesReady())) {
      throw new ServiceUnavailableException({ ok: false, error: 'password_reset_not_ready' });
    }
    if (userId.startsWith('stub:')) {
      throw new BadRequestException({ error: 'stub_user_password_change_not_supported' });
    }

    await this.tenantLock.assertPortalTenantActive(clientId);

    const user = await this.repo.findUserById(userId, clientId);
    if (!user) {
      throw new UnauthorizedException({ error: 'user_not_found' });
    }

    const current = currentPassword?.trim() ?? '';
    const next = newPassword?.trim() ?? '';
    if (!verifyPortalPassword(current, user.password_hash)) {
      throw new UnauthorizedException({ error: 'invalid_current_password' });
    }
    if (next.length < MIN_PASSWORD_LEN) {
      throw new BadRequestException({ error: 'password_too_short', min_length: MIN_PASSWORD_LEN });
    }
    if (current === next) {
      throw new BadRequestException({ error: 'password_unchanged' });
    }

    await this.repo.updatePassword(user.id, hashPortalPassword(next));
    await this.repo.invalidateUserTokens(user.id);

    return { ok: true, message: 'password_updated' };
  }
}
