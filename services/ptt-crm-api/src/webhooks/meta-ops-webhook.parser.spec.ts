import { readFileSync } from 'fs';
import { join } from 'path';
import {
  isAccountDisabledStatus,
  isAdDisapprovedStatus,
  normalizeAdAccountId,
  parseOpsWebhookChanges,
} from './meta-ops-webhook.parser';

describe('meta-ops-webhook.parser', () => {
  it('normalizes ad account id', () => {
    expect(normalizeAdAccountId('1234567890')).toBe('act_1234567890');
    expect(normalizeAdAccountId('act_999')).toBe('act_999');
  });

  it('detects disabled account status', () => {
    expect(isAccountDisabledStatus(2)).toBe(true);
    expect(isAccountDisabledStatus('disabled')).toBe(true);
    expect(isAccountDisabledStatus('ACTIVE')).toBe(false);
    expect(isAccountDisabledStatus(1)).toBe(false);
  });

  it('detects disapproved ad status', () => {
    expect(isAdDisapprovedStatus('DISAPPROVED')).toBe(true);
    expect(isAdDisapprovedStatus('ACTIVE')).toBe(false);
  });

  it('parses account disabled fixture', () => {
    const fixturePath = join(
      __dirname,
      '../../../../tests/fixtures/channels/meta/webhook_account_disabled.json',
    );
    const payload = JSON.parse(readFileSync(fixturePath, 'utf8')) as Record<string, unknown>;
    const events = parseOpsWebhookChanges(payload);
    expect(events).toHaveLength(1);
    expect(events[0].event_type).toBe('meta_account_disabled');
    expect(events[0].external_account_id).toBe('act_1234567890');
  });

  it('parses ad disapproved change', () => {
    const events = parseOpsWebhookChanges({
      object: 'ad_account',
      entry: [
        {
          id: '123',
          changes: [
            {
              field: 'ads',
              value: {
                ad_id: 'ad_999',
                effective_status: 'DISAPPROVED',
                campaign_id: 'camp_1',
                account_id: 'act_123',
              },
            },
          ],
        },
      ],
    });
    expect(events).toHaveLength(1);
    expect(events[0].event_type).toBe('ad_disapproved');
    expect(events[0].external_ad_id).toBe('ad_999');
  });
});
