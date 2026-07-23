import { Injectable } from '@nestjs/common';
import { SopAutoStartService } from '../sop/sop-auto-start.service';
import { LeadsContractSqliteRepository } from './leads-contract-sqlite.repository';
import type {
  ContractReadiness,
  ContractRow,
  ContractApprovalRow,
  CreateContractBody,
  PatchContractBody,
} from './contract.types';

@Injectable()
export class LeadsContractService {
  constructor(
    private readonly repo: LeadsContractSqliteRepository,
    private readonly sopAutoStart: SopAutoStartService,
  ) {}

  getReadiness(leadId: number): ContractReadiness {
    return this.repo.getReadiness(leadId);
  }

  getContractForLead(leadId: number): { contract: ContractRow | null; approval: ContractApprovalRow | null } {
    return this.repo.getContractForLead(leadId);
  }

  createDraft(leadId: number, body: CreateContractBody, actor: string): ContractRow {
    return this.repo.createDraftContract(leadId, body, actor);
  }

  patchContract(contractId: number, leadId: number, body: PatchContractBody): ContractRow {
    return this.repo.patchContract(contractId, leadId, body);
  }

  submit(contractId: number, leadId: number, actor: string, notes: string): ContractApprovalRow {
    return this.repo.submitForApproval(contractId, leadId, actor, notes);
  }

  listPendingApprovals(limit?: number) {
    return { approvals: this.repo.listPendingApprovals(limit ?? 50) };
  }

  listByClient(clientId: string, limit?: number) {
    return { contracts: this.repo.listContractsByClient(clientId, limit ?? 50) };
  }

  reject(approvalId: number, actor: string, decisionNotes: string) {
    return this.repo.rejectApproval(approvalId, actor, decisionNotes);
  }

  approve(approvalId: number, actor: string) {
    const result = this.repo.approveAndPromote(approvalId, actor);
    const sop = this.sopAutoStart.maybeStartOnLifecyclePromote({
      lifecycleId: result.lifecycle_id,
      contractId: result.contract.id,
      serviceSlug: result.contract.service_slug ?? '',
    });
    return { ...result, sop_auto_start: sop };
  }
}
