import {
  buildFacebookHubClientsCsv,
  resolveFacebookHubDateWindow,
} from './facebook-hub.util';

describe('resolveFacebookHubDateWindow', () => {
  it('uses window days ending at date_to', () => {
    const w = resolveFacebookHubDateWindow({ days: 7, dateTo: '2026-07-20' });
    expect(w.dateTo).toBe('2026-07-20');
    expect(w.dateFrom).toBe('2026-07-14');
    expect(w.windowDays).toBe(7);
  });

  it('honors explicit date_from and date_to', () => {
    const w = resolveFacebookHubDateWindow({
      dateFrom: '2026-07-01',
      dateTo: '2026-07-15',
    });
    expect(w.dateFrom).toBe('2026-07-01');
    expect(w.dateTo).toBe('2026-07-15');
    expect(w.windowDays).toBe(15);
  });
});

describe('buildFacebookHubClientsCsv', () => {
  it('includes BOM and header row', () => {
    const csv = buildFacebookHubClientsCsv(
      [
        {
          id: '550e8400-e29b-41d4-a716-446655440000',
          code: 'TCLT',
          name: 'Test Client',
          status: 'active',
          owner_am_id: null,
          meta_account_count: 1,
          spend: 1000000,
          leads_crm: 10,
          cpl: 100000,
          campaigns: 2,
          unmapped_campaigns: 0,
          over_target_rows: 0,
          meta_has_token: true,
          token_status: 'valid',
        },
      ],
      { dateFrom: '2026-07-01', dateTo: '2026-07-07' },
    );
    expect(csv.startsWith('\uFEFFclient_id,')).toBe(true);
    expect(csv).toContain('TCLT');
    expect(csv).toContain('2026-07-01');
  });
});
