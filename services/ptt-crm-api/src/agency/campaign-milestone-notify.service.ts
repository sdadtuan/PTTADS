import { Injectable, Logger } from '@nestjs/common';
import { Pool } from 'pg';
import { AppConfigService } from '../config/app-config.service';
import { PortalNotificationService } from '../portal/portal-notification.service';

@Injectable()
export class CampaignMilestoneNotifyService {
  private readonly logger = new Logger(CampaignMilestoneNotifyService.name);
  private pool: Pool | null = null;

  constructor(
    private readonly config: AppConfigService,
    private readonly portalNotifications: PortalNotificationService,
  ) {}

  private get db(): Pool {
    if (!this.pool) {
      this.pool = new Pool({ connectionString: this.config.databaseUrl });
    }
    return this.pool;
  }

  async notifyZaloMilestone(input: {
    recipientId: string;
    milestone: string;
    title: string;
    body: string;
    link?: string;
    clientId?: string;
    meta?: Record<string, unknown>;
  }): Promise<{ ok: boolean; notification_id?: string | null; error?: string }> {
    const recipient = input.recipientId?.trim() || 'am@pttads.vn';
    const link = input.link?.trim() || '/zalo/zalo-ads';
    try {
      const result = await this.db.query(
        `INSERT INTO notification_inbox (recipient_id, category, title, body, link_url, meta)
         VALUES ($1, 'campaign_milestone', $2, $3, $4, $5::jsonb)
         RETURNING id::text`,
        [
          recipient,
          input.title,
          input.body,
          link,
          JSON.stringify({
            channel: 'zalo',
            milestone: input.milestone,
            client_id: input.clientId ?? null,
            ...(input.meta ?? {}),
          }),
        ],
      );
      const notificationId = result.rows[0]?.id ?? null;

      if (input.clientId) {
        const portalPath =
          input.link?.startsWith('/') && !input.link.startsWith('/crm')
            ? input.link
            : '/zalo';
        await this.portalNotifications.emitMilestone({
          clientId: input.clientId,
          milestone: input.milestone,
          title: input.title,
          body: input.body,
          linkUrl: portalPath,
          meta: { channel: 'zalo', ...(input.meta ?? {}) },
        });
      }

      return { ok: true, notification_id: notificationId };
    } catch (err) {
      const message = err instanceof Error ? err.message : String(err);
      this.logger.warn('zalo milestone notify failed: %s', message);
      return { ok: false, error: message };
    }
  }
}
