import { ForbiddenException, NotFoundException, ServiceUnavailableException } from '@nestjs/common';
import { ClientOffboardService } from './client-offboard.service';

describe('ClientOffboardService', () => {
  const repo = {
    tablesReady: jest.fn(),
    clientExists: jest.fn(),
    runOffboardTransaction: jest.fn(),
    tenantLockedColumnReady: jest.fn(),
    isTenantLocked: jest.fn(),
    listAudit: jest.fn(),
  };
  const sideEffects = {
    onClientOffboarded: jest.fn(),
  };
  const service = new ClientOffboardService(repo as never, sideEffects as never);

  beforeEach(() => {
    jest.resetAllMocks();
    repo.tablesReady.mockResolvedValue(true);
    repo.clientExists.mockResolvedValue(true);
    repo.tenantLockedColumnReady.mockResolvedValue(true);
    repo.isTenantLocked.mockResolvedValue(false);
  });

  it('assertClientWritable allows unlocked tenant', async () => {
    await expect(service.assertClientWritable('client-1')).resolves.toBeUndefined();
  });

  it('assertPortalTenantActive blocks locked tenant', async () => {
    repo.isTenantLocked.mockResolvedValue(true);
    await expect(service.assertPortalTenantActive('client-1')).rejects.toBeInstanceOf(ForbiddenException);
    await expect(service.assertPortalTenantActive('client-1')).rejects.toMatchObject({
      response: { error: 'tenant_archived', client_id: 'client-1' },
    });
  });

  it('offboard is idempotent when already archived', async () => {
    repo.runOffboardTransaction.mockResolvedValue({
      audit: { id: 'audit-1' },
      tokensRevoked: 2,
      portalUsersDeactivated: 1,
      previousStatus: 'active',
      idempotent: true,
    });
    const out = await service.offboardClient('client-1', { reason: 'churn' }, 'am@pttads.vn');
    expect(out.idempotent).toBe(true);
    expect(out.audit_id).toBe('audit-1');
    expect(sideEffects.onClientOffboarded).not.toHaveBeenCalled();
  });

  it('offboard emits event on first run', async () => {
    repo.runOffboardTransaction.mockResolvedValue({
      audit: { id: 'audit-2' },
      tokensRevoked: 1,
      portalUsersDeactivated: 1,
      previousStatus: 'active',
      idempotent: false,
    });
    sideEffects.onClientOffboarded.mockResolvedValue('evt-1');
    const out = await service.offboardClient('client-1', { reason: 'other', note: 'test' }, 'am@pttads.vn');
    expect(out.event_id).toBe('evt-1');
    expect(sideEffects.onClientOffboarded).toHaveBeenCalled();
  });

  it('offboard fails when DDL not ready', async () => {
    repo.tablesReady.mockResolvedValue(false);
    await expect(service.offboardClient('client-1', {}, 'staff')).rejects.toBeInstanceOf(
      ServiceUnavailableException,
    );
  });

  it('listAudit 404 when client missing', async () => {
    repo.clientExists.mockResolvedValue(false);
    await expect(service.listAudit('missing')).rejects.toBeInstanceOf(NotFoundException);
  });
});
