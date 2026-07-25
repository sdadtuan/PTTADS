import { AppConfigService } from './app-config.service';
import { ProdHStubAuditService } from './prod-h.stub-audit.service';

describe('ProdHStubAuditService', () => {
  const saved: Record<string, string | undefined> = {};

  beforeEach(() => {
    for (const key of [
      'NODE_ENV',
      'PTT_PRODUCTION',
      'PTT_ZALO_ADS_STUB',
      'PTT_CRM_API_AUTH_DISABLED',
      'PTT_PORTAL_ALLOW_STUB',
      'PTT_STAFF_ALLOW_STUB',
    ]) {
      saved[key] = process.env[key];
      delete process.env[key];
    }
  });

  afterEach(() => {
    for (const [key, val] of Object.entries(saved)) {
      if (val === undefined) delete process.env[key];
      else process.env[key] = val;
    }
  });

  it('passes in non-production env even with stub flags', () => {
    process.env.PTT_ZALO_ADS_STUB = '1';
    const svc = new ProdHStubAuditService(new AppConfigService());
    expect(svc.audit().ok).toBe(true);
  });

  it('flags stub env vars in production', () => {
    process.env.NODE_ENV = 'production';
    process.env.PTT_ZALO_ADS_STUB = '1';
    const svc = new ProdHStubAuditService(new AppConfigService());
    const out = svc.audit();
    expect(out.ok).toBe(false);
    expect(out.violations).toContain('PTT_ZALO_ADS_STUB=1');
  });

  it('flags auth disabled in production', () => {
    process.env.PTT_PRODUCTION = '1';
    process.env.PTT_CRM_API_AUTH_DISABLED = '1';
    const svc = new ProdHStubAuditService(new AppConfigService());
    expect(svc.audit().ok).toBe(false);
  });
});
