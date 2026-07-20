import { createHash } from 'crypto';
import type { LegacyLeadRow, NormalizedLeadPayload, WebhookLeadChannel } from './webhook-lead.types';

export function cleanEnv(val: string | undefined): string {
  let s = String(val ?? '').trim();
  if (s.length >= 2 && (s.startsWith('"') || s.startsWith("'")) && s[0] === s.at(-1)) {
    s = s.slice(1, -1).trim();
  }
  return s.replace(/[\r\n\t]+/g, '');
}

export function idempotencyKey(channel: string, parts: Record<string, unknown>): string {
  const blob = JSON.stringify(parts, Object.keys(parts).sort());
  return createHash('sha256').update(`${channel}:${blob}`).digest('hex').slice(0, 64);
}

export function utcNowIso(): string {
  return new Date().toISOString().replace(/\.\d{3}Z$/, 'Z');
}

export function parseWebhookJson(rawBody: Buffer): Record<string, unknown> {
  if (!rawBody.length) return {};
  try {
    const data = JSON.parse(rawBody.toString('utf8')) as unknown;
    return data && typeof data === 'object' && !Array.isArray(data) ? (data as Record<string, unknown>) : {};
  } catch {
    return {};
  }
}

export function legacyRowToNormalizedLead(
  row: LegacyLeadRow,
  clientId: string,
  channel: WebhookLeadChannel,
  opts?: { externalIdMetaKeys?: string[]; formIdMetaKeys?: string[] },
): NormalizedLeadPayload {
  const meta = row.meta && typeof row.meta === 'object' ? { ...row.meta } : {};
  const externalIdKeys = opts?.externalIdMetaKeys ?? [];
  let externalLeadId = String(row.external_lead_id ?? '');
  for (const key of externalIdKeys) {
    const val = meta[key];
    if (val) {
      externalLeadId = String(val);
      break;
    }
  }
  if (!externalLeadId) {
    externalLeadId = idempotencyKey(channel, {
      phone: row.phone ?? row.phone_number,
      email: row.email,
      name: row.full_name ?? row.name,
    });
  }

  const formIdKeys = opts?.formIdMetaKeys ?? [];
  let externalFormId: string | null = null;
  for (const key of formIdKeys) {
    const val = meta[key];
    if (val) {
      externalFormId = String(val);
      break;
    }
  }

  const utmCampaign = String(row.utm_campaign ?? row.campaign_id ?? meta.utm_campaign ?? meta.campaign_id ?? '');
  const fields: Record<string, string> = {};
  for (const [key, val] of Object.entries(row)) {
    if (
      ['full_name', 'name', 'phone', 'phone_number', 'email', 'meta', 'source', 'utm_campaign', 'campaign_id'].includes(
        key,
      ) ||
      val == null
    ) {
      continue;
    }
    fields[key] = String(val);
  }

  return {
    client_id: clientId || 'unknown',
    channel,
    external_lead_id: externalLeadId,
    idempotency_key: idempotencyKey(channel, { external_lead_id: externalLeadId, client_id: clientId }),
    occurred_at: utcNowIso(),
    contact: {
      full_name: row.full_name ?? row.name ?? null,
      phone: row.phone ?? row.phone_number ?? null,
      email: row.email ?? null,
    },
    fields,
    external_form_id: externalFormId,
    external_campaign_id: utmCampaign || null,
    utm: { source: channel, campaign: utmCampaign || null },
    raw: row as Record<string, unknown>,
  };
}
