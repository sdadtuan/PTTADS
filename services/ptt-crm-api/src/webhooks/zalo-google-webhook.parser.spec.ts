import { createHmac } from 'crypto';
import { parseGoogleWebhookPayload, parseGoogleWebhook } from './google-webhook.parser';
import { parseZaloWebhookPayload, parseZaloWebhook, verifyZaloSignature } from './zalo-webhook.parser';

describe('zalo-webhook.parser', () => {
  it('verifyZaloSignature accepts valid hmac', () => {
    const body = Buffer.from('{"event_name":"user_submit_info"}');
    const secret = 'zalo-secret';
    const digest = createHmac('sha256', secret).update(body).digest('hex');
    expect(verifyZaloSignature(body, digest, secret)).toBe(true);
  });

  it('parses user_submit_info payload', () => {
    const payload = {
      event_name: 'user_submit_info',
      app_id: '12345',
      oa_id: 'OA_001',
      user_id: 'U001',
      info: {
        name: 'Nguyen Van A',
        phone: '0901234567',
        campaign_id: 'ZALO_CAMP_01',
      },
    };
    const rows = parseZaloWebhookPayload(payload);
    expect(rows).toHaveLength(1);
    expect(rows[0].full_name).toBe('Nguyen Van A');
    expect(rows[0].phone).toBe('0901234567');
    expect(rows[0].source).toBe('zalo');
  });

  it('parseZaloWebhook normalizes lead', () => {
    const payload = {
      event_name: 'user_submit_info',
      info: { name: 'A', phone: '090' },
    };
    const body = Buffer.from(JSON.stringify(payload));
    const out = parseZaloWebhook({
      headers: {},
      rawBody: body,
      clientId: 'client-zalo',
      config: { webhookSecret: '' },
    });
    expect(out.verified).toBe(true);
    expect(out.leads).toHaveLength(1);
    expect(out.leads[0].channel).toBe('zalo');
    expect(out.leads[0].client_id).toBe('client-zalo');
  });
});

describe('google-webhook.parser', () => {
  it('parses direct lead payload', () => {
    const rows = parseGoogleWebhookPayload({
      full_name: 'Google Lead',
      phone: '0909999888',
      email: 'g@test.local',
      meta: { google_lead_id: 'gl-1' },
    });
    expect(rows).toHaveLength(1);
    expect(rows[0].full_name).toBe('Google Lead');
  });

  it('parses user_column_data lead form payload', () => {
    const rows = parseGoogleWebhookPayload({
      lead_id: 'lead-123',
      campaign_id: '999',
      form_id: '555',
      user_column_data: [
        { column_name: 'Full Name', string_value: 'Test User' },
        { column_name: 'User Phone', string_value: '0901111222' },
        { column_name: 'User Email', string_value: 'a@example.com' },
      ],
    });
    expect(rows).toHaveLength(1);
    expect(rows[0].full_name).toBe('Test User');
    expect(rows[0].meta?.google_lead_id).toBe('lead-123');
  });

  it('parseGoogleWebhook rejects invalid key when configured', () => {
    const body = Buffer.from(JSON.stringify({ google_key: 'wrong', full_name: 'X' }));
    const out = parseGoogleWebhook({
      headers: {},
      rawBody: body,
      clientId: 'c1',
      config: { leadWebhookKey: 'expected-key' },
    });
    expect(out.verified).toBe(false);
    expect(out.reject_reason).toBe('Invalid Google webhook key');
  });
});
