import {
  BadRequestException,
  ForbiddenException,
  Injectable,
  NotFoundException,
  ServiceUnavailableException,
} from '@nestjs/common';
import { AgencySideEffectsService } from './agency-side-effects.service';
import { ClientOffboardRepository } from './client-offboard.repository';
import {
  OFFBOARD_REASONS,
  OffboardAuditListResponse,
  OffboardClientBody,
  OffboardClientResponse,
} from './client-offboard.types';

@Injectable()
export class ClientOffboardService {
  constructor(
    private readonly repo: ClientOffboardRepository,
    private readonly sideEffects: AgencySideEffectsService,
  ) {}

  async offboardClient(
    clientId: string,
    body: OffboardClientBody,
    initiatedBy: string,
  ): Promise<OffboardClientResponse> {
    if (!(await this.repo.tablesReady())) {
      throw new ServiceUnavailableException({ ok: false, error: 'offboard_tables_not_ready' });
    }
    if (!(await this.repo.clientExists(clientId))) {
      throw new NotFoundException({ error: 'Not found' });
    }

    const reason = (body.reason?.trim() || 'contract_ended').slice(0, 64);
    if (!reason) {
      throw new BadRequestException({ error: 'invalid_reason', allowed: OFFBOARD_REASONS });
    }
    const note = body.note?.trim() || null;

    let outcome;
    try {
      outcome = await this.repo.runOffboardTransaction({
        clientId,
        initiatedBy,
        reason,
        note,
      });
    } catch (err) {
      const message = err instanceof Error ? err.message : String(err);
      if (message === 'client_not_found') {
        throw new NotFoundException({ error: 'Not found' });
      }
      if (message === 'offboard_tables_not_ready') {
        throw new ServiceUnavailableException({ ok: false, error: message });
      }
      throw err;
    }

    let eventId: string | null = null;
    if (!outcome.idempotent) {
      eventId = await this.sideEffects.onClientOffboarded(clientId, {
        client_id: clientId,
        reason,
        note,
        previous_status: outcome.previousStatus,
        tokens_revoked: outcome.tokensRevoked,
        portal_users_deactivated: outcome.portalUsersDeactivated,
        initiated_by: initiatedBy,
        archive_data: body.archive_data !== false,
      });
    }

    return {
      ok: true,
      client_id: clientId,
      status: 'archived',
      tenant_locked: true,
      tokens_revoked: outcome.tokensRevoked,
      portal_users_deactivated: outcome.portalUsersDeactivated,
      event_id: eventId,
      audit_id: outcome.audit.id,
      idempotent: outcome.idempotent,
    };
  }

  async getLockState(clientId: string): Promise<{ status: string; tenant_locked: boolean } | null> {
    return this.repo.getClientLockState(clientId);
  }

  async listAudit(clientId: string): Promise<OffboardAuditListResponse> {
    if (!(await this.repo.clientExists(clientId))) {
      throw new NotFoundException({ error: 'Not found' });
    }
    const rows = await this.repo.listAudit(clientId);
    return { ok: true, client_id: clientId, rows };
  }

  async assertClientWritable(clientId: string): Promise<void> {
    if (!(await this.repo.tenantLockedColumnReady())) {
      return;
    }
    if (await this.repo.isTenantLocked(clientId)) {
      throw new ForbiddenException({ error: 'tenant_archived', client_id: clientId });
    }
  }
}
