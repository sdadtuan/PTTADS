import { Injectable, Logger } from '@nestjs/common';
import { AppConfigService } from '../config/app-config.service';
import { PortalNotifyWebhookService } from './portal-notify-webhook.service';

@Injectable()
export class PortalPasswordResetNotifyService {
  private readonly logger = new Logger(PortalPasswordResetNotifyService.name);

  constructor(
    private readonly config: AppConfigService,
    private readonly webhook: PortalNotifyWebhookService,
  ) {}

  async sendResetEmail(params: {
    to: string;
    resetUrl: string;
    expiresMinutes: number;
  }): Promise<{ ok: boolean; stub?: boolean; skipped?: boolean; error?: string }> {
    const subject = 'PTT Client Portal — Đặt lại mật khẩu';
    const body =
      `Bạn (hoặc quản trị PTT) đã yêu cầu đặt lại mật khẩu portal.\n\n` +
      `Link (hết hạn sau ${params.expiresMinutes} phút):\n${params.resetUrl}\n\n` +
      `Nếu bạn không yêu cầu, bỏ qua email này.`;

    if (!this.config.portalEmailNotifyEnabled) {
      this.logger.log('portal password reset email disabled to=%s', params.to);
      return { ok: true, skipped: true };
    }

    const result = await this.webhook.send({
      source: 'portal_password_reset',
      to: params.to,
      subject,
      body,
      reset_url: params.resetUrl,
    });
    if (result.skipped) {
      return { ok: true, skipped: true };
    }
    if (!result.ok) {
      this.logger.warn('portal password reset webhook failed: %s', result.error);
      return { ok: false, error: result.error };
    }
    return { ok: true };
  }
}
