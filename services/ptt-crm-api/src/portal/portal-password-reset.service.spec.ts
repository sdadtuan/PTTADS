import { BadRequestException, ForbiddenException } from '@nestjs/common';
import { PortalPasswordResetService } from './portal-password-reset.service';

describe('PortalPasswordResetService', () => {
  const repo = {
    tablesReady: jest.fn(),
    findActiveUserByEmail: jest.fn(),
    findUserById: jest.fn(),
    invalidateUserTokens: jest.fn(),
    insertToken: jest.fn(),
    findValidToken: jest.fn(),
    markTokenUsed: jest.fn(),
    updatePassword: jest.fn(),
  };
  const notify = {
    sendResetEmail: jest.fn(),
  };
  const tenantLock = {
    assertPortalTenantActive: jest.fn(),
  };
  const config = {
    portalPublicUrl: 'https://portal.test',
    portalResetTtlMin: 60,
    portalEmailNotifyEnabled: false,
  };

  const service = new PortalPasswordResetService(
    repo as never,
    notify as never,
    tenantLock as never,
    config as never,
  );

  beforeEach(() => {
    jest.resetAllMocks();
    repo.tablesReady.mockResolvedValue(true);
    tenantLock.assertPortalTenantActive.mockResolvedValue(undefined);
    notify.sendResetEmail.mockResolvedValue({ ok: true, stub: true });
  });

  it('forgotPassword returns generic message when user missing', async () => {
    repo.findActiveUserByEmail.mockResolvedValue(null);
    const out = await service.forgotPassword('missing@test.local');
    expect(out.ok).toBe(true);
    expect(out.message).toContain('Nếu email tồn tại');
    expect(repo.insertToken).not.toHaveBeenCalled();
  });

  it('forgotPassword creates token and sends email', async () => {
    repo.findActiveUserByEmail.mockResolvedValue({
      id: 'u1',
      client_id: 'c1',
      email: 'user@test.local',
      password_hash: 'hash',
    });
    const out = await service.forgotPassword('user@test.local');
    expect(out.ok).toBe(true);
    expect(repo.invalidateUserTokens).toHaveBeenCalledWith('u1');
    expect(repo.insertToken).toHaveBeenCalled();
    expect(notify.sendResetEmail).toHaveBeenCalled();
    expect(out.reset_url).toBeTruthy();
  });

  it('forgotPassword hides archived tenant like missing email', async () => {
    repo.findActiveUserByEmail.mockResolvedValue({
      id: 'u1',
      client_id: 'c1',
      email: 'user@test.local',
      password_hash: 'hash',
    });
    tenantLock.assertPortalTenantActive.mockRejectedValue(
      new ForbiddenException({ error: 'tenant_archived' }),
    );
    const out = await service.forgotPassword('user@test.local');
    expect(out.ok).toBe(true);
    expect(repo.insertToken).not.toHaveBeenCalled();
  });

  it('resetPassword rejects short password', async () => {
    await expect(service.resetPassword('token', 'short')).rejects.toBeInstanceOf(BadRequestException);
  });

  it('changePassword rejects wrong current password', async () => {
    repo.findUserById.mockResolvedValue({
      id: 'u1',
      client_id: 'c1',
      email: 'user@test.local',
      password_hash: 'scrypt:abc:def',
    });
    await expect(service.changePassword('u1', 'c1', 'wrong', 'newpassword1')).rejects.toMatchObject({
      response: { error: 'invalid_current_password' },
    });
  });
});
