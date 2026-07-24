import { Injectable, Logger } from '@nestjs/common';
import { MetaWebhookRepository } from './meta-webhook.repository';
import { parseOpsWebhookChanges } from './meta-ops-webhook.parser';
import type { MetaOpsWebhookEvent, MetaOpsWebhookProcessResult } from './meta-ops-webhook.types';

@Injectable()
export class MetaOpsWebhookService {
  private readonly logger = new Logger(MetaOpsWebhookService.name);

  constructor(private readonly repo: MetaWebhookRepository) {}

  isEnabled(): boolean {
    return ['1', 'true', 'yes', 'on'].includes(
      (process.env.PTT_META_OPS_WEBHOOKS ?? '0').trim().toLowerCase(),
    );
  }

  private todayIso(): string {
    return new Date().toISOString().slice(0, 10);
  }

  private dedupeKey(
    alertType: string,
    clientId: string,
    externalCampaignId: string | null,
  ): string {
    const camp = externalCampaignId?.trim() || '_';
    return `${alertType}:${clientId}:${camp}:${this.todayIso()}`;
  }

  async processPayload(payload: Record<string, unknown>): Promise<MetaOpsWebhookProcessResult> {
    if (!this.isEnabled()) {
      return { ok: true, skipped: true, reason: 'PTT_META_OPS_WEBHOOKS=0', events: 0, created: 0, results: [] };
    }
    if (!(await this.repo.pgMetaAlertsReady())) {
      return {
        ok: false,
        reason: 'meta_alerts_not_ready',
        events: 0,
        created: 0,
        results: [],
      };
    }

    const events = parseOpsWebhookChanges(payload);
    const results: Array<Record<string, unknown>> = [];
    let created = 0;

    for (const event of events) {
      const clientId = await this.repo.resolveClientIdByAdAccount(event.external_account_id);
      if (!clientId) {
        results.push({ ...event, ok: false, error: 'client_not_resolved' });
        continue;
      }
      const outcome = await this.raiseAlert(clientId, event);
      if (outcome.created) created += 1;
      results.push({ ...event, ...outcome });
    }

    if (events.length) {
      this.logger.log(`meta ops webhook processed events=${events.length} created=${created}`);
    }

    return { ok: true, events: events.length, created, results };
  }

  private async raiseAlert(
    clientId: string,
    event: MetaOpsWebhookEvent,
  ): Promise<{ ok: boolean; created?: boolean; alert_id?: string; dedupe_key?: string; idempotent?: boolean }> {
    if (event.event_type === 'meta_account_disabled') {
      const accountId = event.external_account_id ?? 'unknown';
      const reason = event.disable_reason ?? 'account_status_not_active';
      const message = `Meta ad account ${accountId} disabled (${reason})`;
      return this.repo.insertOpsAlert({
        clientId,
        alertType: 'meta_account_disabled',
        severity: 'danger',
        message,
        externalCampaignId: null,
        dedupeKey: this.dedupeKey('meta_account_disabled', clientId, null),
      });
    }

    const adId = event.external_ad_id ?? 'unknown';
    const message = `Meta ad ${adId} disapproved — review creative/copy`;
    const campaignKey = event.external_campaign_id ?? adId;
    return this.repo.insertOpsAlert({
      clientId,
      alertType: 'ad_disapproved',
      severity: 'warning',
      message,
      externalCampaignId: campaignKey,
      dedupeKey: this.dedupeKey('ad_disapproved', clientId, campaignKey),
    });
  }
}
