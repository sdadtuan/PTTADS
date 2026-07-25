import {
  buildSeoOAuthState,
  parseSeoOAuthState,
  seoOAuthConfigured,
} from './seo-oauth.util';

describe('seo-oauth.util', () => {
  const envBackup = process.env;

  beforeEach(() => {
    process.env = { ...envBackup };
  });

  afterAll(() => {
    process.env = envBackup;
  });

  it('reports not configured when env missing', () => {
    delete process.env.PTT_GSC_OAUTH_CLIENT_ID;
    expect(seoOAuthConfigured('gsc')).toBe(false);
  });

  it('round-trips oauth state', () => {
    const state = buildSeoOAuthState({
      customerId: 42,
      provider: 'gsc',
      siteUrl: 'https://example.com/',
    });
    const parsed = parseSeoOAuthState(state);
    expect(parsed.customer_id).toBe(42);
    expect(parsed.provider).toBe('gsc');
    expect(parsed.site_url).toBe('https://example.com/');
  });
});
