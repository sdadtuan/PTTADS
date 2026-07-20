import { createHmac, timingSafeEqual } from 'crypto';
import {
  cleanEnv,
  legacyRowToNormalizedLead,
  parseWebhookJson,
} from './webhook-lead.mapper';
import type { LegacyLeadRow, NormalizedLeadPayload, WebhookParseResultBase } from './webhook-lead.types';

export interface ZaloWebhookConfig {
  webhookSecret: string;
}

export interface ZaloParseResult extends WebhookParseResultBase {
  channel: 'zalo';
}

export function zaloConfigFromEnv(): ZaloWebhookConfig {
  return {
    webhookSecret: cleanEnv(process.env.CRM_ZALO_WEBHOOK_SECRET ?? process.env.ZALO_OA_SECRET),
  };
}

export function verifyZaloSignature(
  rawBody: Buffer,
  signatureHeader: string | undefined,
  secret: string,
): boolean {
  if (!secret) return true;
  if (!signatureHeader) return false;
  const expected = createHmac('sha256', secret).update(rawBody).digest('hex');
  try {
    return timingSafeEqual(Buffer.from(expected), Buffer.from(signatureHeader.trim().toLowerCase()));
  } catch {
    return expected.toLowerCase() === signatureHeader.trim().toLowerCase();
  }
}

function zaloCampaignFromPayload(payload: Record<string, unknown>, info: Record<string, unknown> | string): string {
  if (info && typeof info === 'object') {
    for (const key of ['campaign_id', 'zalo_campaign_id', 'ads_campaign_id', 'campaign']) {
      const val = String(info[key] ?? '').trim();
      if (val) return val;
    }
  }
  for (const key of ['campaign_id', 'zalo_campaign_id', 'utm_campaign', 'campaign']) {
    const val = String(payload[key] ?? '').trim();
    if (val) return val;
  }
  const meta = payload.meta;
  if (meta && typeof meta === 'object') {
    for (const key of ['campaign_id', 'zalo_campaign_id', 'campaign']) {
      const val = String((meta as Record<string, unknown>)[key] ?? '').trim();
      if (val) return val;
    }
  }
  return '';
}

export function parseZaloWebhookPayload(payload: Record<string, unknown>): LegacyLeadRow[] {
  const out: LegacyLeadRow[] = [];

  if (payload.full_name || payload.name || payload.phone) {
    const campaignId = zaloCampaignFromPayload(payload, {});
    out.push({
      full_name: String(payload.full_name ?? payload.name ?? ''),
      phone: String(payload.phone ?? ''),
      email: String(payload.email ?? ''),
      need: String(payload.need ?? payload.message ?? ''),
      product_interest: String(payload.product_interest ?? ''),
      region: String(payload.region ?? ''),
      utm_campaign: String(payload.utm_campaign ?? campaignId ?? ''),
      campaign_id: campaignId,
      oa_id: String(payload.oa_id ?? payload.app_id ?? ''),
      source: 'zalo',
      meta:
        payload.meta && typeof payload.meta === 'object'
          ? (payload.meta as Record<string, unknown>)
          : { webhook: 'zalo' },
    });
    return out;
  }

  const event = String(payload.event_name ?? payload.event ?? '').toLowerCase();
  if (['user_submit_info', 'oa_send_text', 'user_send_text', 'follow'].includes(event)) {
    const infoRaw = payload.info ?? payload.data ?? payload.message ?? {};
    if (infoRaw && typeof infoRaw === 'object' && !Array.isArray(infoRaw)) {
      const info = infoRaw as Record<string, unknown>;
      const campaignId = zaloCampaignFromPayload(payload, info);
      const oaId = String(payload.oa_id ?? payload.app_id ?? info.oa_id ?? '').trim();
      const follower = payload.follower;
      const userId =
        follower && typeof follower === 'object'
          ? (follower as { id?: unknown }).id
          : payload.user_id;
      const meta: Record<string, unknown> = {
        zalo_event: event,
        oa_id: oaId || null,
        user_id: userId,
      };
      if (campaignId) meta.campaign_id = campaignId;
      out.push({
        full_name: String(info.name ?? info.full_name ?? payload.sender_name ?? ''),
        phone: String(info.phone ?? info.phone_number ?? ''),
        email: String(info.email ?? ''),
        need: String(info.message ?? info.note ?? info.text ?? ''),
        utm_campaign: String(info.utm_campaign ?? campaignId ?? ''),
        campaign_id: campaignId,
        oa_id: oaId,
        source: 'zalo',
        meta,
      });
    } else if (typeof infoRaw === 'string' && infoRaw.trim()) {
      out.push({
        full_name: String(payload.sender_name ?? 'Zalo user'),
        phone: '',
        email: '',
        need: infoRaw.trim(),
        source: 'zalo',
        meta: { zalo_event: event, raw_message: infoRaw.slice(0, 500) },
      });
    }
  }

  const events = payload.events;
  if (Array.isArray(events)) {
    for (const item of events) {
      if (item && typeof item === 'object') {
        out.push(...parseZaloWebhookPayload(item as Record<string, unknown>));
      }
    }
  }

  return out;
}

export function parseZaloWebhook(input: {
  headers: Record<string, string | string[] | undefined>;
  rawBody: Buffer;
  clientId: string;
  config?: ZaloWebhookConfig;
}): ZaloParseResult {
  const config = input.config ?? zaloConfigFromEnv();
  const sig = String(input.headers['x-zalo-signature'] ?? input.headers['X-Zalo-Signature'] ?? '');

  if (!verifyZaloSignature(input.rawBody, sig, config.webhookSecret)) {
    return { verified: false, reject_reason: 'Invalid Zalo signature', channel: 'zalo', leads: [], events: [] };
  }

  const payload = parseWebhookJson(input.rawBody);
  const rows = parseZaloWebhookPayload(payload);
  const clientId = input.clientId || 'unknown';
  const leads: NormalizedLeadPayload[] = rows.map((row) =>
    legacyRowToNormalizedLead(row, clientId, 'zalo', { externalIdMetaKeys: ['zalo_lead_id'] }),
  );
  const events = leads.map((lead) => ({ event_name: 'Lead', external_lead_id: lead.external_lead_id }));

  return { verified: true, channel: 'zalo', leads, events };
}
