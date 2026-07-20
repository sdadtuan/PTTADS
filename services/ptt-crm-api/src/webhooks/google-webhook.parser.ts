import {
  cleanEnv,
  legacyRowToNormalizedLead,
  parseWebhookJson,
} from './webhook-lead.mapper';
import type { LegacyLeadRow, NormalizedLeadPayload, WebhookParseResultBase } from './webhook-lead.types';

export interface GoogleWebhookConfig {
  leadWebhookKey: string;
}

export interface GoogleParseResult extends WebhookParseResultBase {
  channel: 'google';
}

export function googleConfigFromEnv(): GoogleWebhookConfig {
  return {
    leadWebhookKey: cleanEnv(
      process.env.CRM_GOOGLE_LEAD_WEBHOOK_KEY ??
        process.env.GOOGLE_LEAD_WEBHOOK_KEY ??
        process.env.PTT_GOOGLE_LEAD_WEBHOOK_KEY,
    ),
  };
}

function columnValue(columns: unknown[], names: string[]): string {
  if (!Array.isArray(columns)) return '';
  for (const col of columns) {
    if (!col || typeof col !== 'object') continue;
    const c = col as { column_name?: unknown; string_value?: unknown };
    const name = String(c.column_name ?? '').trim().toLowerCase();
    if (names.some((n) => n.toLowerCase() === name)) {
      return String(c.string_value ?? '').trim();
    }
  }
  return '';
}

function verifyGoogleLeadKey(payload: Record<string, unknown>, config: GoogleWebhookConfig): boolean {
  if (!config.leadWebhookKey) return true;
  const key = String(payload.google_key ?? payload.key ?? '').trim();
  return key === config.leadWebhookKey;
}

export function parseGoogleWebhookPayload(payload: Record<string, unknown>): LegacyLeadRow[] {
  const out: LegacyLeadRow[] = [];

  if (payload.full_name || payload.name || payload.phone || payload.email) {
    out.push({
      full_name: String(payload.full_name ?? payload.name ?? ''),
      phone: String(payload.phone ?? payload.phone_number ?? ''),
      email: String(payload.email ?? ''),
      utm_campaign: String(payload.utm_campaign ?? payload.campaign_id ?? ''),
      campaign_id: String(payload.campaign_id ?? ''),
      source: 'google',
      meta:
        payload.meta && typeof payload.meta === 'object'
          ? (payload.meta as Record<string, unknown>)
          : { webhook: 'google' },
    });
    return out;
  }

  const leadId = String(payload.lead_id ?? payload.gcl_id ?? '').trim();
  const columns = payload.user_column_data;
  if (leadId || Array.isArray(columns)) {
    const fullName = columnValue(columns as unknown[], ['Full Name', 'full_name', 'name']);
    const phone = columnValue(columns as unknown[], ['User Phone', 'phone', 'phone_number']);
    const email = columnValue(columns as unknown[], ['User Email', 'email']);
    const campaignId = String(payload.campaign_id ?? '').trim();
    const formId = String(payload.form_id ?? '').trim();
    out.push({
      full_name: fullName,
      phone,
      email,
      utm_campaign: campaignId,
      campaign_id: campaignId,
      source: 'google',
      meta: {
        google_lead_id: leadId || undefined,
        form_id: formId || undefined,
        campaign_id: campaignId || undefined,
        is_test: payload.is_test,
        gcl_id: payload.gcl_id,
      },
    });
    return out;
  }

  const leads = payload.leads;
  if (Array.isArray(leads)) {
    for (const item of leads) {
      if (item && typeof item === 'object') {
        out.push(...parseGoogleWebhookPayload(item as Record<string, unknown>));
      }
    }
  }

  return out;
}

export function parseGoogleWebhook(input: {
  headers: Record<string, string | string[] | undefined>;
  rawBody: Buffer;
  clientId: string;
  config?: GoogleWebhookConfig;
}): GoogleParseResult {
  const config = input.config ?? googleConfigFromEnv();
  const payload = parseWebhookJson(input.rawBody);

  if (!verifyGoogleLeadKey(payload, config)) {
    return { verified: false, reject_reason: 'Invalid Google webhook key', channel: 'google', leads: [], events: [] };
  }

  const rows = parseGoogleWebhookPayload(payload);
  const clientId = input.clientId || 'unknown';
  const leads: NormalizedLeadPayload[] = rows.map((row) =>
    legacyRowToNormalizedLead(row, clientId, 'google', {
      externalIdMetaKeys: ['google_lead_id'],
      formIdMetaKeys: ['form_id'],
    }),
  );
  const events = leads.map((lead) => ({ event_name: 'Lead', external_lead_id: lead.external_lead_id }));

  return { verified: true, channel: 'google', leads, events };
}
