import { Injectable, Logger } from '@nestjs/common';
import { Pool } from 'pg';
import { AppConfigService } from '../config/app-config.service';
import { CreativeRow } from '../creatives/creatives.types';

export interface CreativeNotifyResult {
  inbox: { ok: boolean; notification_id?: string | null; error?: string };
  email: { ok: boolean; stub?: boolean; skipped?: boolean; error?: string };
}

@Injectable()
export class PortalCreativeNotifyService {
  private readonly logger = new Logger(PortalCreativeNotifyService.name);
  private pool: Pool | null = null;

  constructor(private readonly config: AppConfigService) {}

  private get db(): Pool {
    if (!this.pool) {
      this.pool = new Pool({ connectionString: this.config.databaseUrl });
    }
    return this.pool;
  }

  async notifyDecision(
    creative: CreativeRow,
    decision: 'approved' | 'rejected',
    reviewedBy: string,
    note: string | null,
  ): Promise<CreativeNotifyResult> {
    const recipient = creative.submitted_by?.trim() || 'am@pttads.vn';
    const title =
      decision === 'approved'
        ? `Client đã duyệt: ${creative.title} (v${creative.version})`
        : `Client từ chối: ${creative.title} (v${creative.version})`;
    const body = note?.trim() || `Quyết định ${decision} trên portal bởi ${reviewedBy}`;
    const link = `/crm/creatives/${creative.id}`;

    const inbox = await this.insertInbox(recipient, title, body, link, {
      creative_id: creative.id,
      client_id: creative.client_id,
      version: creative.version,
      decision,
      reviewed_by: reviewedBy,
      kind: 'creative_portal_decision',
    });

    const email = await this.sendEmailWebhook({
      to: recipient,
      subject: title,
      body,
      creative_id: creative.id,
      client_id: creative.client_id,
      decision,
      reviewed_by: reviewedBy,
    });

    return { inbox, email };
  }

  private async insertInbox(
    recipientId: string,
    title: string,
    body: string,
    linkUrl: string,
    meta: Record<string, unknown>,
  ): Promise<{ ok: boolean; notification_id?: string | null; error?: string }> {
    try {
      const result = await this.db.query(
        `INSERT INTO notification_inbox (recipient_id, category, title, body, link_url, meta)
         VALUES ($1, 'creative', $2, $3, $4, $5::jsonb)
         RETURNING id::text`,
        [recipientId, title, body, linkUrl, JSON.stringify(meta)],
      );
      return { ok: true, notification_id: result.rows[0]?.id ?? null };
    } catch (err) {
      const message = err instanceof Error ? err.message : String(err);
      this.logger.warn('notification_inbox insert failed: %s', message);
      return { ok: false, error: message };
    }
  }

  private async sendEmailWebhook(payload: Record<string, unknown>): Promise<{
    ok: boolean;
    stub?: boolean;
    skipped?: boolean;
    error?: string;
  }> {
    if (!this.config.portalEmailNotifyEnabled) {
      return { ok: true, skipped: true };
    }
    const url = this.config.portalEmailWebhookUrl;
    if (!url) {
      this.logger.log('portal email notify stub: %j', payload);
      return { ok: true, stub: true };
    }
    try {
      const res = await fetch(url, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', Accept: 'application/json' },
        body: JSON.stringify({ source: 'portal_creative_decision', ...payload }),
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
