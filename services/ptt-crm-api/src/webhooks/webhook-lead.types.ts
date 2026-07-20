export type WebhookLeadChannel = 'meta' | 'zalo' | 'google';

export interface LegacyLeadRow {
  full_name?: string;
  name?: string;
  phone?: string;
  phone_number?: string;
  email?: string;
  source?: string;
  utm_campaign?: string;
  campaign_id?: string;
  oa_id?: string;
  need?: string;
  product_interest?: string;
  region?: string;
  meta?: Record<string, unknown>;
  external_lead_id?: string;
}

export interface NormalizedLeadPayload {
  client_id: string;
  channel: WebhookLeadChannel;
  external_lead_id: string;
  idempotency_key: string;
  occurred_at: string;
  contact: { full_name?: string | null; phone?: string | null; email?: string | null };
  fields: Record<string, string>;
  external_form_id?: string | null;
  external_campaign_id?: string | null;
  utm?: { source?: string | null; campaign?: string | null };
  raw: Record<string, unknown>;
}

export interface WebhookParseResultBase {
  verified: boolean;
  reject_reason?: string;
  challenge?: string | number;
  leads: NormalizedLeadPayload[];
  events: Array<{ event_name: string; external_lead_id: string }>;
}
