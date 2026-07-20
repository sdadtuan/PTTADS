import {
  BadRequestException,
  Injectable,
  NotFoundException,
} from '@nestjs/common';
import { catalogTs } from '../catalog/catalog-slug.util';
import { LeadsRepository } from '../leads/leads.repository';
import { LeadsWriteService } from '../leads/leads-write.service';
import { LeadV1 } from '../leads/leads.types';
import { CrmLeadsSqliteRepository } from './crm-leads-sqlite.repository';
import {
  AssignLeadBody,
  CreateLeadActivityBody,
  LeadActivityRow,
  LeadAssignmentLogRow,
  LeadStatusLogRow,
} from './crm-leads-legacy.types';

@Injectable()
export class CrmLeadsLegacyService {
  constructor(
    private readonly sqlite: CrmLeadsSqliteRepository,
    private readonly leadsRepo: LeadsRepository,
    private readonly leadsWrite: LeadsWriteService,
  ) {}

  private async assertLead(leadId: number): Promise<void> {
    const pg = await this.leadsRepo.getLeadById(leadId);
    if (pg) return;
    if (!this.sqlite.leadExists(leadId)) {
      throw new NotFoundException({ error: 'Không tìm thấy lead.' });
    }
  }

  async listActivities(leadId: number, limit?: number): Promise<LeadActivityRow[]> {
    await this.assertLead(leadId);
    return this.sqlite.listActivities(leadId, limit ?? 100);
  }

  async createActivity(
    leadId: number,
    body: CreateLeadActivityBody,
    actor: string,
    userId: number | null,
  ): Promise<{ activity: LeadActivityRow }> {
    await this.assertLead(leadId);
    const activity = this.sqlite.createActivity(leadId, body, actor, userId);
    return { activity };
  }

  async auditLogs(
    leadId: number,
  ): Promise<{ status_logs: LeadStatusLogRow[]; assignment_logs: LeadAssignmentLogRow[] }> {
    await this.assertLead(leadId);
    return {
      status_logs: this.sqlite.listStatusLogs(leadId),
      assignment_logs: this.sqlite.listAssignmentLogs(leadId),
    };
  }

  async assignLead(
    leadId: number,
    body: AssignLeadBody,
    actor: string,
  ): Promise<{ lead: LeadV1 }> {
    const toId = Number(body.to_user_id ?? body.owner_id ?? 0);
    const reason = String(body.reason ?? '').trim();
    if (!toId) {
      throw new BadRequestException({ error: 'to_user_id không hợp lệ' });
    }
    if (!reason) {
      throw new BadRequestException({ error: 'Cần ghi lý do phân lại.' });
    }
    if (!this.sqlite.staffExists(toId)) {
      throw new BadRequestException({ error: 'Nhân viên không hợp lệ hoặc đã ngưng.' });
    }
    await this.assertLead(leadId);

    const fromId = this.sqlite.getLeadOwnerId(leadId);
    const ts = catalogTs();
    const lead = await this.leadsWrite.patchLead(
      leadId,
      { owner_id: toId, assigned_by: actor },
      actor,
    );

    if (this.sqlite.leadExists(leadId)) {
      this.sqlite.syncOwner(leadId, toId, actor, ts);
      this.sqlite.logAssignment(leadId, fromId, toId, reason, actor, ts);
      this.sqlite.createActivity(
        leadId,
        { activity_type: 'system', content: `Phân lại lead: ${reason}` },
        actor,
        toId,
      );
    }

    return { lead };
  }

  async mirrorPatchAudit(
    leadId: number,
    prev: LeadV1,
    next: LeadV1,
    actor: string,
    note = '',
  ): Promise<void> {
    if (!this.sqlite.leadExists(leadId)) return;
    const ts = catalogTs();
    if (next.status && prev.status !== next.status) {
      this.sqlite.syncStatus(leadId, next.status, actor, ts);
      this.sqlite.logStatusChange(leadId, prev.status, next.status, actor, note, ts);
    }
    if (prev.owner_id !== next.owner_id && next.owner_id != null) {
      this.sqlite.syncOwner(leadId, next.owner_id, actor, ts);
      this.sqlite.logAssignment(
        leadId,
        prev.owner_id ?? null,
        next.owner_id,
        note || 'Cập nhật owner qua ops-web',
        actor,
        ts,
      );
    }
  }
}
