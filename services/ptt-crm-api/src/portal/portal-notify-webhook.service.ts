import { Injectable, Logger } from '@nestjs/common';
import { AppConfigService } from '../config/app-config.service';
import { PortalNotifyWebhookResult } from './portal-notification.types';

@Injectable()
export class PortalNotifyWebhookService {
  private readonly logger = new Logger(PortalNotifyWebhookService.name);

  constructor(private readonly config: AppConfigService) {}

  resolveWebhookUrl(): string | null {
    return this.config.portalNotifyWebhookUrl ?? this.config.portalEmailWebhookUrl;
  }

  async send(payload: Record<string, unknown>): Promise<PortalNotifyWebhookResult> {
    if (!this.config.portalEmailNotifyEnabled) {
      return { ok: true, skipped: true };
    }
    const url = this.resolveWebhookUrl();
    if (!url) {
      this.logger.warn('portal notify webhook not configured: %j', payload);
      return { ok: false, error: 'webhook_not_configured' };
    }
    try {
      const res = await fetch(url, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', Accept: 'application/json' },
        body: JSON.stringify(payload),
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
