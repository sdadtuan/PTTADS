import {
  ForbiddenException,
  Injectable,
  Logger,
  NotFoundException,
  ServiceUnavailableException,
} from '@nestjs/common';
import { CreativeRow } from '../creatives/creatives.types';
import { AppConfigService } from '../config/app-config.service';
import { PortalJwtPayload } from './portal-jwt.util';
import { PortalNotificationRepository } from './portal-notification.repository';
import {
  EmitPortalNotificationInput,
  PortalNotificationListResponse,
  PortalNotificationRow,
  PortalNotificationSummaryResponse,
} from './portal-notification.types';
import { PortalNotifyWebhookService } from './portal-notify-webhook.service';

@Injectable()
export class PortalNotificationService {
  private readonly logger = new Logger(PortalNotificationService.name);

  constructor(
    private readonly repo: PortalNotificationRepository,
    private readonly webhook: PortalNotifyWebhookService,
    private readonly config: AppConfigService,
  ) {}

  private clientNotifyEnabled(): boolean {
    return this.config.portalClientNotifyEnabled;
  }

  async list(
    user: PortalJwtPayload,
    params?: { unreadOnly?: boolean; limit?: number },
  ): Promise<PortalNotificationListResponse> {
    const clientId = this.assertClient(user);
    const ready = await this.repo.tableReady();
    if (!ready) {
      return {
        ok: true,
        client_id: clientId,
        count: 0,
        unread: 0,
        rows: [],
        table_ready: false,
      };
    }
    const { rows, unread } = await this.repo.listForUser({
      clientId,
      portalUserId: user.sub,
      unreadOnly: Boolean(params?.unreadOnly),
      limit: Math.min(100, Math.max(1, Number(params?.limit) || 50)),
    });
    return {
      ok: true,
      client_id: clientId,
      count: rows.length,
      unread,
      rows,
      table_ready: true,
    };
  }

  async summary(user: PortalJwtPayload): Promise<PortalNotificationSummaryResponse> {
    const clientId = this.assertClient(user);
    const ready = await this.repo.tableReady();
    if (!ready) {
      return this.repo.emptySummary(clientId, false);
    }
    const [{ unread }, pendingCreatives] = await Promise.all([
      this.repo.listForUser({
        clientId,
        portalUserId: user.sub,
        unreadOnly: false,
        limit: 1,
      }),
      this.repo.countPendingCreatives(clientId),
    ]);
    return {
      ok: true,
      client_id: clientId,
      unread,
      pending_creatives: pendingCreatives,
      pending_email: 0,
      pending_seo: 0,
      table_ready: true,
    };
  }

  async enrichSummary(
    base: PortalNotificationSummaryResponse,
    extras: { pendingEmail?: number; pendingSeo?: number },
  ): Promise<PortalNotificationSummaryResponse> {
    return {
      ...base,
      pending_email: extras.pendingEmail ?? base.pending_email,
      pending_seo: extras.pendingSeo ?? base.pending_seo,
    };
  }

  async markRead(
    user: PortalJwtPayload,
    notificationId: string,
  ): Promise<{ ok: boolean; notification: PortalNotificationRow }> {
    await this.ensureReady();
    const clientId = this.assertClient(user);
    const row = await this.repo.markRead({
      clientId,
      portalUserId: user.sub,
      notificationId,
    });
    if (!row) {
      throw new NotFoundException({ error: 'notification_not_found' });
    }
    return { ok: true, notification: row };
  }

  async markAllRead(user: PortalJwtPayload): Promise<{ ok: boolean; updated: number }> {
    await this.ensureReady();
    const clientId = this.assertClient(user);
    const updated = await this.repo.markAllRead({
      clientId,
      portalUserId: user.sub,
    });
    return { ok: true, updated };
  }

  async emit(input: EmitPortalNotificationInput): Promise<{ ok: boolean; ids: string[]; error?: string }> {
    if (!this.clientNotifyEnabled()) {
      return { ok: true, ids: [] };
    }
    const ready = await this.repo.tableReady();
    if (!ready) {
      this.logger.warn('portal_notification table not ready — skip emit');
      return { ok: false, ids: [], error: 'portal_notification_table_not_ready' };
    }

    const users = await this.repo.listActivePortalUsers(input.clientId);
    const targets = input.approverOnly
      ? users.filter((u) => u.role === 'approver')
      : users;

    const ids: string[] = [];
    if (targets.length === 0) {
      const row = await this.repo.insert({
        clientId: input.clientId,
        portalUserId: input.portalUserId ?? null,
        category: input.category,
        title: input.title,
        body: input.body,
        linkUrl: input.linkUrl,
        meta: input.meta,
      });
      if (row) ids.push(row.id);
    } else {
      for (const target of targets) {
        if (input.portalUserId && target.id !== input.portalUserId) continue;
        const row = await this.repo.insert({
          clientId: input.clientId,
          portalUserId: target.id,
          category: input.category,
          title: input.title,
          body: input.body,
          linkUrl: input.linkUrl,
          meta: input.meta,
        });
        if (row) ids.push(row.id);
      }
    }

    await this.webhook.send({
      source: 'portal_client_notification',
      client_id: input.clientId,
      category: input.category,
      title: input.title,
      body: input.body ?? null,
      link_url: input.linkUrl ?? null,
      meta: input.meta ?? {},
      notification_ids: ids,
    });

    return { ok: true, ids };
  }

  async emitCreativePending(creative: CreativeRow): Promise<{ ok: boolean; ids: string[] }> {
    const channel = creative.channel ?? 'meta';
    const link = '/creatives';
    const title = `Creative chờ duyệt: ${creative.title} (v${creative.version})`;
    const body =
      creative.description?.trim() ||
      `AM đã gửi creative mới${creative.external_campaign_name ? ` — ${creative.external_campaign_name}` : ''}.`;
    const result = await this.emit({
      clientId: creative.client_id,
      category: 'creative_pending',
      title,
      body,
      linkUrl: link,
      approverOnly: true,
      meta: {
        creative_id: creative.id,
        channel,
        version: creative.version,
        external_campaign_id: creative.external_campaign_id,
        submitted_by: creative.submitted_by,
      },
    });
    return { ok: result.ok, ids: result.ids };
  }

  async emitEmailPending(input: {
    clientId: string;
    campaignId: string;
    campaignName: string;
    submittedBy?: string | null;
    audienceCount?: number | null;
  }): Promise<{ ok: boolean; ids: string[] }> {
    const title = `Email chờ duyệt: ${input.campaignName}`;
    const audience =
      input.audienceCount != null ? ` — audience ~${input.audienceCount.toLocaleString('vi-VN')}` : '';
    const body = `Chiến dịch email cần phê duyệt trước khi gửi${audience}.`;
    const result = await this.emit({
      clientId: input.clientId,
      category: 'email_pending',
      title,
      body,
      linkUrl: '/email/approvals',
      approverOnly: true,
      meta: {
        campaign_id: input.campaignId,
        submitted_by: input.submittedBy ?? null,
        audience_count: input.audienceCount ?? null,
      },
    });
    return { ok: result.ok, ids: result.ids };
  }

  async emitSeoPending(input: {
    clientId: string;
    contentId: number;
    title: string;
  }): Promise<{ ok: boolean; ids: string[] }> {
    const result = await this.emit({
      clientId: input.clientId,
      category: 'seo_pending',
      title: `SEO content chờ review: ${input.title}`,
      body: 'Nội dung SEO/AEO cần phê duyệt trên portal.',
      linkUrl: `/seo/content/${input.contentId}`,
      approverOnly: true,
      meta: { content_id: input.contentId },
    });
    return { ok: result.ok, ids: result.ids };
  }

  async emitMilestone(input: {
    clientId: string;
    milestone: string;
    title: string;
    body: string;
    linkUrl?: string | null;
    meta?: Record<string, unknown>;
  }): Promise<{ ok: boolean; ids: string[] }> {
    const result = await this.emit({
      clientId: input.clientId,
      category: 'campaign_milestone',
      title: input.title,
      body: input.body,
      linkUrl: input.linkUrl ?? '/dashboard',
      meta: { milestone: input.milestone, ...(input.meta ?? {}) },
    });
    return { ok: result.ok, ids: result.ids };
  }

  private assertClient(user: PortalJwtPayload): string {
    if (!user.client_id) {
      throw new ForbiddenException({ error: 'missing_client_id' });
    }
    return user.client_id;
  }

  private async ensureReady(): Promise<void> {
    if (!(await this.repo.tableReady())) {
      throw new ServiceUnavailableException({
        ok: false,
        error: 'portal_notification_table_not_ready',
      });
    }
  }
}
