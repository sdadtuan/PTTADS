import { leadRowToV1, pgRowToV1 } from './lead-v1.mapper';
import { LeadRow, PgLeadRow } from './leads.types';

describe('leadRowToV1', () => {
  it('matches Python contract for canonical row', () => {
    const row: LeadRow = {
      id: 1,
      full_name: 'Lead A',
      phone: '0901111111',
      email: '',
      status: 'new',
      source: 'facebook',
      owner_id: null,
      created_at: '2026-07-17',
      is_duplicate: 0,
      meta_json: JSON.stringify({
        agency_client_id: '550e8400-e29b-41d4-a716-446655440000',
        channel: 'meta',
        facebook_leadgen_id: 'fb-1',
      }),
    };

    expect(leadRowToV1(row)).toEqual({
      id: 1,
      full_name: 'Lead A',
      phone: '0901111111',
      email: '',
      status: 'new',
      source: 'facebook',
      channel: 'meta',
      client_id: '550e8400-e29b-41d4-a716-446655440000',
      campaign_id: null,
      external_lead_id: 'fb-1',
      owner_id: null,
      created_at: '2026-07-17',
      received_at: '2026-07-17',
      is_duplicate: false,
    });
  });
});

describe('pgRowToV1', () => {
  it('matches Python pg_row_to_v1 date-only formatting', () => {
    const row: PgLeadRow = {
      sqlite_lead_id: 1,
      full_name: 'Lead A',
      phone: '0901111111',
      email: '',
      status: 'new',
      source: 'facebook',
      owner_id: null,
      is_duplicate: false,
      agency_client_id: '550e8400-e29b-41d4-a716-446655440000',
      channel: 'meta',
      external_lead_id: 'fb-1',
      campaign_id: null,
      received_at: new Date('2026-07-17T00:00:00.000Z'),
      created_at: new Date('2026-07-17T00:00:00.000Z'),
    };

    expect(pgRowToV1(row)).toEqual({
      id: 1,
      full_name: 'Lead A',
      phone: '0901111111',
      email: '',
      status: 'new',
      source: 'facebook',
      channel: 'meta',
      client_id: '550e8400-e29b-41d4-a716-446655440000',
      campaign_id: null,
      external_lead_id: 'fb-1',
      owner_id: null,
      created_at: '2026-07-17',
      received_at: '2026-07-17',
      is_duplicate: false,
    });
  });
});
