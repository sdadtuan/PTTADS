import { Injectable, Logger } from '@nestjs/common';
import { AppConfigService } from '../config/app-config.service';

@Injectable()
export class PortalPasswordResetNotifyService {
  private readonly logger = new Logger(PortalPasswordResetNotifyService.name);

  constructor(private readonly config: AppConfigService) {}

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
      this.logger.log('portal password reset email stub to=%s url=%s', params.to, params.resetUrl);
      return { ok: true, stub: true };
    }

    const url = this.config.portalEmailWebhookUrl;
    if (!url) {
      this.logger.log('portal password reset notify (no webhook): %s', params.resetUrl);
      return { ok: true, stub: true };
    }

    try {
      const res = await fetch(url, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', Accept: 'application/json' },
        body: JSON.stringify({
          source: 'portal_password_reset',
          to: params.to,
          subject,
          body,
          reset_url: params.resetUrl,
        }),
      });
      if (!res.ok) {
        return { ok: false, error: `webhook HTTP ${res.status}` };
      }
      return { ok: true };
    } catch (err) {
      const message = err instanceof Error ? err.message : String(err);
      return { ok: false, error: message };
    }
  }
}
