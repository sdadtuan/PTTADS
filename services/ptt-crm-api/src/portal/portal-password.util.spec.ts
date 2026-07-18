import { hashPortalPassword, verifyPortalPassword } from './portal-password.util';

describe('portal-password.util', () => {
  it('hashes and verifies scrypt passwords', () => {
    const hash = hashPortalPassword('demo123');
    expect(hash.startsWith('scrypt:')).toBe(true);
    expect(verifyPortalPassword('demo123', hash)).toBe(true);
    expect(verifyPortalPassword('wrong', hash)).toBe(false);
  });

  it('rejects plain: passwords in production by default', () => {
    const prev = process.env.NODE_ENV;
    process.env.NODE_ENV = 'production';
    delete process.env.PTT_PORTAL_ALLOW_PLAIN_PASSWORD;
    expect(verifyPortalPassword('x', 'plain:x')).toBe(false);
    process.env.NODE_ENV = prev;
  });
});
