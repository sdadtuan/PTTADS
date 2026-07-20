import { createHmac } from 'crypto';
import {
  legacyRowToNormalizedLead,
  parseFacebookWebhookJson,
  parseFacebookWebhookPayload,
  parseMetaWebhook,
  verifyFacebookSignature,
} from './meta-webhook.parser';

describe('meta-webhook.parser', () => {
  it('verifyFacebookSignature accepts sha256', () => {
    const body = Buffer.from('{"object":"page"}');
    const secret = 'test-secret';
    const digest = createHmac('sha256', secret).update(body).digest('hex');
    expect(verifyFacebookSignature(body, `sha256=${digest}`, [secret])).toBe(true);
  });

  it('hub subscribe challenge when verify token matches', async () => {
    const out = await parseMetaWebhook({
      headers: {},
      rawBody: Buffer.alloc(0),
      query: {
        'hub.mode': 'subscribe',
        'hub.verify_token': 'tok-123',
        'hub.challenge': '999',
      },
      clientId: '',
      config: {
        verifyToken: 'tok-123',
        appSecrets: [],
        pageAccessToken: '',
        graphApiVersion: 'v19.0',
      },
    });
    expect(out.verified).toBe(true);
    expect(out.challenge).toBe('999');
  });

  it('normalizes direct lead payload', async () => {
    const payload = {
      full_name: 'Test User',
      phone: '0901111222',
      email: 'a@example.com',
      meta: { facebook_leadgen_id: '123' },
    };
    const body = Buffer.from(JSON.stringify(payload));
    const out = await parseMetaWebhook({
      headers: { 'x-hub-signature-256': 'sha256=skip' },
      rawBody: body,
      query: {},
      clientId: '550e8400-e29b-41d4-a716-446655440000',
      config: {
        verifyToken: '',
        appSecrets: [],
        pageAccessToken: '',
        graphApiVersion: 'v19.0',
      },
    });
    expect(out.verified).toBe(true);
    expect(out.leads).toHaveLength(1);
    expect(out.leads[0].external_lead_id).toBe('123');
    expect(out.leads[0].client_id).toBe('550e8400-e29b-41d4-a716-446655440000');
  });

  it('legacyRowToNormalizedLead builds idempotency key', () => {
    const lead = legacyRowToNormalizedLead(
      {
        full_name: 'A',
        phone: '090',
        meta: { facebook_leadgen_id: 'fb-1' },
        source: 'facebook',
      },
      'client-1',
    );
    expect(lead.channel).toBe('meta');
    expect(lead.idempotency_key).toHaveLength(64);
  });

  it('parseFacebookWebhookJson handles invalid json', () => {
    expect(parseFacebookWebhookJson(Buffer.from('not-json'))).toEqual({});
  });

  it('parseFacebookWebhookPayload pending when no graph token', async () => {
    const payload = {
      entry: [
        {
          changes: [{ field: 'leadgen', value: { leadgen_id: '999', page_id: '1', form_id: 'F' } }],
        },
      ],
    };
    const rows = await parseFacebookWebhookPayload(payload, {
      verifyToken: '',
      appSecrets: [],
      pageAccessToken: '',
      graphApiVersion: 'v19.0',
    });
    expect(rows).toHaveLength(1);
    expect(rows[0].meta?.facebook_leadgen_id).toBe('999');
  });
});
