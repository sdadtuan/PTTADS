import { checkZaloAdsPilot, zaloAdsPilotStatus } from './zalo-ads-pilot.util';

describe('zalo-ads-pilot.util', () => {
  const env = process.env;

  beforeEach(() => {
    process.env = { ...env };
    delete process.env.PTT_ZALO_ADS_STUB;
    delete process.env.PTT_ZALO_ADS_PILOT;
    delete process.env.PTT_ZALO_ADS_PILOT_CLIENTS;
    delete process.env.PTT_ZALO_INSIGHTS_SYNC;
    delete process.env.PTT_ZALO_APP_ID;
    delete process.env.PTT_ZALO_APP_SECRET;
    delete process.env.PTT_ZALO_OAUTH_REDIRECT_URI;
  });

  afterAll(() => {
    process.env = env;
  });

  it('checkZaloAdsPilot allows stub mode', () => {
    process.env.PTT_ZALO_ADS_STUB = '1';
    const out = checkZaloAdsPilot('client-1');
    expect(out.allowed).toBe(true);
    expect(out.stub_mode).toBe(true);
  });

  it('checkZaloAdsPilot allows all clients in production mode (pilot off, stub off)', () => {
    const out = checkZaloAdsPilot('client-1');
    expect(out.allowed).toBe(true);
    expect(out.pilot_mode).toBe(false);
    expect(out.production_mode).toBe(true);
    expect(out.warning).toBeNull();
  });

  it('checkZaloAdsPilot respects pilot client allowlist', () => {
    process.env.PTT_ZALO_ADS_PILOT = '1';
    process.env.PTT_ZALO_ADS_PILOT_CLIENTS = 'allowed-client';
    expect(checkZaloAdsPilot('allowed-client').allowed).toBe(true);
    expect(checkZaloAdsPilot('other-client').allowed).toBe(false);
  });

  it('zaloAdsPilotStatus reports oauth and sync flags', () => {
    process.env.PTT_ZALO_ADS_STUB = '1';
    process.env.PTT_ZALO_INSIGHTS_SYNC = '1';
    process.env.PTT_ZALO_APP_ID = 'app';
    process.env.PTT_ZALO_APP_SECRET = 'secret';
    process.env.PTT_ZALO_OAUTH_REDIRECT_URI = 'https://example.com/callback';
    const status = zaloAdsPilotStatus();
    expect(status.stub_mode).toBe(true);
    expect(status.insights_sync_enabled).toBe(true);
    expect(status.oauth_configured).toBe(true);
  });
});
