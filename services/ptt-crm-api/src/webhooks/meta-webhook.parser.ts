import { createHmac, timingSafeEqual } from 'crypto';
import {
  cleanEnv,
  idempotencyKey,
  legacyRowToNormalizedLead as sharedLegacyRowToNormalizedLead,
  parseWebhookJson,
} from './webhook-lead.mapper';
import type { LegacyLeadRow, NormalizedLeadPayload } from './webhook-lead.types';

export type { LegacyLeadRow, NormalizedLeadPayload } from './webhook-lead.types';

export interface MetaWebhookConfig {
  verifyToken: string;
  appSecrets: string[];
  pageAccessToken: string;
  graphApiVersion: string;
}

export interface MetaParseResult {
  verified: boolean;
  reject_reason?: string;
  challenge?: string | number;
  channel: 'meta';
  leads: NormalizedLeadPayload[];
  events: Array<{ event_name: string; external_lead_id: string }>;
}

export function metaConfigFromEnv(): MetaWebhookConfig {
  const secrets: string[] = [];
  for (const key of ['CRM_FACEBOOK_APP_SECRET', 'FACEBOOK_APP_SECRET']) {
    const s = cleanEnv(process.env[key]);
    if (s && !secrets.includes(s)) secrets.push(s);
  }
  return {
    verifyToken: cleanEnv(process.env.CRM_FACEBOOK_VERIFY_TOKEN ?? process.env.FACEBOOK_VERIFY_TOKEN),
    appSecrets: secrets,
    pageAccessToken: cleanEnv(
      process.env.CRM_FACEBOOK_PAGE_ACCESS_TOKEN ?? process.env.FACEBOOK_PAGE_ACCESS_TOKEN,
    ),
    graphApiVersion: cleanEnv(process.env.CRM_FACEBOOK_GRAPH_VERSION) || 'v19.0',
  };
}

export function legacyRowToNormalizedLead(row: LegacyLeadRow, clientId: string): NormalizedLeadPayload {
  return sharedLegacyRowToNormalizedLead(row, clientId, 'meta', {
    externalIdMetaKeys: ['facebook_leadgen_id'],
    formIdMetaKeys: ['facebook_form_id'],
  });
}

function signatureCandidates(header: string | undefined): Array<{ algo: 'sha256' | 'sha1'; digest: string }> {
  const sig = String(header ?? '').trim();
  if (!sig) return [];
  const low = sig.toLowerCase();
  if (low.startsWith('sha256=')) return [{ algo: 'sha256', digest: sig.split('=')[1]?.trim() ?? '' }];
  if (low.startsWith('sha1=')) return [{ algo: 'sha1', digest: sig.split('=')[1]?.trim() ?? '' }];
  return [];
}

export function verifyFacebookSignature(rawBody: Buffer, signatureHeader: string | undefined, secrets: string[]): boolean {
  if (!secrets.length) return true;
  const cands = signatureCandidates(signatureHeader);
  if (!cands.length) return false;
  for (const secret of secrets) {
    for (const { algo, digest } of cands) {
      const expected = createHmac(algo, secret).update(rawBody).digest('hex');
      try {
        if (timingSafeEqual(Buffer.from(expected), Buffer.from(digest))) return true;
      } catch {
        continue;
      }
    }
  }
  return false;
}

export function parseFacebookWebhookJson(rawBody: Buffer): Record<string, unknown> {
  return parseWebhookJson(rawBody);
}

export async function fetchFacebookLeadFromGraph(
  leadgenId: string,
  config: MetaWebhookConfig,
): Promise<LegacyLeadRow> {
  const token = config.pageAccessToken;
  if (!token) {
    return {
      full_name: '',
      phone: '',
      email: '',
      meta: { facebook_leadgen_id: leadgenId, fetch: 'pending_token' },
    };
  }
  const url = `https://graph.facebook.com/${config.graphApiVersion}/${encodeURIComponent(leadgenId)}?fields=id,created_time,field_data&access_token=${encodeURIComponent(token)}`;
  try {
    const res = await fetch(url, { signal: AbortSignal.timeout(15000) });
    if (!res.ok) {
      return {
        full_name: '',
        phone: '',
        email: '',
        meta: { facebook_leadgen_id: leadgenId, fetch: 'graph_error', status: res.status },
      };
    }
    const data = (await res.json()) as { field_data?: Array<{ name?: string; values?: string[] }> };
    const fields: Record<string, string> = {};
    for (const item of data.field_data ?? []) {
      const name = String(item.name ?? '').trim().toLowerCase();
      const val = item.values?.[0];
      if (name && val) fields[name] = String(val);
    }
    return {
      full_name: fields.full_name || fields.name || fields.ho_ten || '',
      phone: fields.phone_number || fields.phone || fields.sdt || '',
      email: fields.email || '',
      meta: { facebook_leadgen_id: leadgenId, raw_field_data: fields },
    };
  } catch {
    return {
      full_name: '',
      phone: '',
      email: '',
      meta: { facebook_leadgen_id: leadgenId, fetch: 'graph_exception' },
    };
  }
}

export async function parseFacebookWebhookPayload(
  payload: Record<string, unknown>,
  config: MetaWebhookConfig,
): Promise<LegacyLeadRow[]> {
  const out: LegacyLeadRow[] = [];
  if (payload.full_name || payload.name || payload.phone || payload.email) {
    out.push({
      full_name: String(payload.full_name ?? payload.name ?? ''),
      phone: String(payload.phone ?? payload.phone_number ?? ''),
      email: String(payload.email ?? ''),
      source: 'facebook',
      meta:
        payload.meta && typeof payload.meta === 'object'
          ? (payload.meta as Record<string, unknown>)
          : { webhook: 'facebook' },
    });
    return out;
  }

  const entries = payload.entry;
  if (!Array.isArray(entries)) return out;

  for (const entry of entries) {
    if (!entry || typeof entry !== 'object') continue;
    const changes = (entry as { changes?: unknown }).changes;
    if (!Array.isArray(changes)) continue;
    for (const change of changes) {
      if (!change || typeof change !== 'object') continue;
      const ch = change as { field?: string; value?: Record<string, unknown> };
      if (ch.field !== 'leadgen') continue;
      const val = ch.value ?? {};
      const leadgenId = String(val.leadgen_id ?? '');
      if (!leadgenId) continue;
      let parsed = await fetchFacebookLeadFromGraph(leadgenId, config);
      if (!parsed.full_name && !parsed.phone && !parsed.email) {
        parsed = {
          full_name: '',
          phone: '',
          email: '',
          meta: { facebook_leadgen_id: leadgenId, fetch: 'pending_token' },
        };
      }
      parsed.source = 'facebook';
      parsed.meta = {
        ...(parsed.meta ?? {}),
        facebook_page_id: val.page_id,
        facebook_form_id: val.form_id,
        facebook_leadgen_id: leadgenId,
      };
      out.push(parsed);
    }
  }
  return out;
}

export async function parseMetaWebhook(input: {
  headers: Record<string, string | string[] | undefined>;
  rawBody: Buffer;
  query: Record<string, string>;
  clientId: string;
  config?: MetaWebhookConfig;
}): Promise<MetaParseResult> {
  const config = input.config ?? metaConfigFromEnv();
  const mode = input.query['hub.mode'] ?? input.query.hub_mode;
  if (mode === 'subscribe') {
    const token = input.query['hub.verify_token'] ?? input.query.hub_verify_token ?? '';
    if (token && token === config.verifyToken) {
      return {
        verified: true,
        challenge: input.query['hub.challenge'] ?? input.query.hub_challenge ?? '',
        channel: 'meta',
        leads: [],
        events: [],
      };
    }
    return { verified: false, reject_reason: 'Invalid verify token', channel: 'meta', leads: [], events: [] };
  }

  const sig =
    String(input.headers['x-hub-signature-256'] ?? input.headers['X-Hub-Signature-256'] ?? '') ||
    String(input.headers['x-hub-signature'] ?? input.headers['X-Hub-Signature'] ?? '');

  if (!verifyFacebookSignature(input.rawBody, sig, config.appSecrets)) {
    return { verified: false, reject_reason: 'Invalid Facebook signature', channel: 'meta', leads: [], events: [] };
  }

  const payload = parseFacebookWebhookJson(input.rawBody);
  const rows = await parseFacebookWebhookPayload(payload, config);
  const clientId = input.clientId || 'unknown';
  const leads = rows.map((row) => legacyRowToNormalizedLead(row, clientId));
  const events = leads.map((lead) => ({ event_name: 'Lead', external_lead_id: lead.external_lead_id }));

  return { verified: true, channel: 'meta', leads, events };
}

export function normalizeWebhookChannel(channel: string): string {
  const c = channel.trim().toLowerCase();
  if (c === 'facebook' || c === 'meta') return 'meta';
  return c;
}
