import * as crypto from 'crypto';

export interface EmailWebhookEvent {
  event?: string;
  email?: string;
  timestamp?: number | string;
  url?: string;
  send_id?: string;
  custom_args?: Record<string, string>;
  unique_args?: Record<string, string>;
  [key: string]: unknown;
}

export interface EmailWebhookParseResult {
  verified: boolean;
  reject_reason?: string;
  events: EmailWebhookEvent[];
}

export function parseEmailWebhook(params: {
  headers: Record<string, string | string[] | undefined>;
  rawBody: Buffer;
  clientId?: string;
  verify?: boolean;
}): EmailWebhookParseResult {
  const bodyText = params.rawBody.toString('utf8') || '[]';
  let payload: unknown;
  try {
    payload = JSON.parse(bodyText);
  } catch {
    return { verified: false, reject_reason: 'invalid_json', events: [] };
  }

  const events: EmailWebhookEvent[] = Array.isArray(payload)
    ? (payload as EmailWebhookEvent[])
    : payload && typeof payload === 'object' && Array.isArray((payload as { events?: unknown }).events)
      ? ((payload as { events: EmailWebhookEvent[] }).events ?? [])
      : payload && typeof payload === 'object'
        ? [payload as EmailWebhookEvent]
        : [];

  if (params.verify && !verifySendGridSignature(params.headers, params.rawBody)) {
    return { verified: false, reject_reason: 'signature_invalid', events: [] };
  }

  const clientId = params.clientId?.trim();
  const normalized = events.map((evt) => {
    const out = { ...evt };
    if (clientId) {
      out.client_id = clientId;
    }
    return out;
  });

  return { verified: true, events: normalized };
}

function verifySendGridSignature(
  headers: Record<string, string | string[] | undefined>,
  rawBody: Buffer,
): boolean {
  const publicKey = (process.env.SENDGRID_WEBHOOK_VERIFICATION_KEY ?? '').trim();
  if (!publicKey) {
    return false;
  }
  const signature = headerValue(headers, 'x-twilio-email-event-webhook-signature');
  const timestamp = headerValue(headers, 'x-twilio-email-event-webhook-timestamp');
  if (!signature || !timestamp) {
    return false;
  }
  try {
    const signed = Buffer.concat([Buffer.from(timestamp), rawBody]);
    const digest = crypto.createHmac('sha256', publicKey).update(signed).digest('base64');
    return crypto.timingSafeEqual(Buffer.from(digest), Buffer.from(signature));
  } catch {
    return false;
  }
}

function headerValue(
  headers: Record<string, string | string[] | undefined>,
  name: string,
): string {
  const direct = headers[name];
  if (typeof direct === 'string') return direct;
  if (Array.isArray(direct)) return direct.join(',');
  const lower = headers[name.toLowerCase()];
  if (typeof lower === 'string') return lower;
  if (Array.isArray(lower)) return lower.join(',');
  return '';
}

export function normalizeWebhookChannel(channel: string): string {
  return String(channel || '').trim().toLowerCase();
}
