import type { MetaOpsWebhookEvent } from './meta-ops-webhook.types';

const ACCOUNT_DISABLED_FIELDS = new Set(['account_update', 'ad_account', 'advertiser_account']);
const AD_STATUS_FIELDS = new Set(['ads', 'ad', 'with_issues_ad_objects']);
const ACTIVE_ACCOUNT_STATUSES = new Set(['active', '1', 'enabled']);

export function normalizeAdAccountId(raw: unknown): string {
  const text = String(raw ?? '').trim();
  if (!text) return '';
  if (text.startsWith('act_')) return text;
  const digits = text.replace(/\D/g, '');
  if (digits) return `act_${digits}`;
  return text;
}

export function isAccountDisabledStatus(status: unknown): boolean {
  if (status == null) return false;
  const text = String(status).trim().toLowerCase();
  if (!text) return false;
  if (ACTIVE_ACCOUNT_STATUSES.has(text)) return false;
  if (['disabled', '2', 'disabled_account', 'deactivated', 'closed'].includes(text)) return true;
  return /^\d+$/.test(text) && text !== '1';
}

export function isAdDisapprovedStatus(status: unknown): boolean {
  return String(status ?? '').trim().toUpperCase() === 'DISAPPROVED';
}

export function parseOpsWebhookChanges(payload: Record<string, unknown>): MetaOpsWebhookEvent[] {
  const events: MetaOpsWebhookEvent[] = [];
  const entries = payload.entry;
  if (!Array.isArray(entries)) return events;

  for (const entry of entries) {
    if (!entry || typeof entry !== 'object') continue;
    const entryObj = entry as Record<string, unknown>;
    const entryId = entryObj.id;
    const changes = entryObj.changes;
    if (!Array.isArray(changes)) continue;

    for (const change of changes) {
      if (!change || typeof change !== 'object') continue;
      const ch = change as { field?: string; value?: Record<string, unknown> };
      const field = String(ch.field ?? '').trim().toLowerCase();
      const value = ch.value ?? {};

      if (
        ACCOUNT_DISABLED_FIELDS.has(field) ||
        (payload.object === 'ad_account' && !AD_STATUS_FIELDS.has(field))
      ) {
        const accountId = normalizeAdAccountId(
          value.account_id ?? value.ad_account_id ?? entryId,
        );
        const status = value.account_status ?? value.status ?? value.event;
        if (accountId && isAccountDisabledStatus(status)) {
          events.push({
            event_type: 'meta_account_disabled',
            external_account_id: accountId,
            external_ad_id: null,
            external_campaign_id: null,
            account_status: String(status),
            disable_reason: value.disable_reason != null ? String(value.disable_reason) : null,
            field: field || 'account_update',
          });
        }
        continue;
      }

      if (AD_STATUS_FIELDS.has(field)) {
        const adId = String(value.ad_id ?? value.id ?? '').trim();
        const effective = value.effective_status ?? value.status;
        if (adId && isAdDisapprovedStatus(effective)) {
          events.push({
            event_type: 'ad_disapproved',
            external_account_id:
              normalizeAdAccountId(value.account_id ?? value.ad_account_id ?? entryId) || null,
            external_ad_id: adId,
            external_campaign_id:
              String(value.campaign_id ?? value.external_campaign_id ?? '').trim() || null,
            effective_status: String(effective),
            field,
          });
        }
      }
    }
  }

  return events;
}
