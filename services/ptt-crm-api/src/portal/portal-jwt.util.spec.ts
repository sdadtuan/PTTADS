import { signPortalJwt, verifyPortalJwt } from './portal-jwt.util';

describe('portal-jwt.util', () => {
  const secret = 'unit-test-secret';

  it('signs and verifies portal JWT', () => {
    const token = signPortalJwt(
      {
        sub: 'user-1',
        email: 'a@test.local',
        client_id: '550e8400-e29b-41d4-a716-446655440000',
        role: 'viewer',
      },
      secret,
      3600,
    );
    const payload = verifyPortalJwt(token, secret);
    expect(payload).not.toBeNull();
    expect(payload?.client_id).toBe('550e8400-e29b-41d4-a716-446655440000');
  });

  it('rejects tampered token', () => {
    const token = signPortalJwt(
      {
        sub: 'user-1',
        email: 'a@test.local',
        client_id: '550e8400-e29b-41d4-a716-446655440000',
        role: 'viewer',
      },
      secret,
      3600,
    );
    const bad = token.slice(0, -4) + 'xxxx';
    expect(verifyPortalJwt(bad, secret)).toBeNull();
  });
});
