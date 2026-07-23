export type ContractStatus = 'draft' | 'active' | 'cancelled';
export type ApprovalStatus = 'pending' | 'approved' | 'rejected';

export interface ContractRow {
  id: number;
  customer_id: number;
  lead_id: number | null;
  case_id: number | null;
  agency_client_id: string;
  title: string;
  status: ContractStatus;
  amount_vnd: number;
  service_slug: string;
  signed_on: string;
  notes: string;
  created_at: string;
  updated_at: string;
}

export interface ContractApprovalRow {
  id: number;
  contract_id: number;
  lead_id: number;
  status: ApprovalStatus;
  requested_by: string;
  decided_by: string;
  amount_vnd: number;
  notes: string;
  decision_notes: string;
  created_at: string;
  decided_at: string;
}

export interface ReadinessCheck {
  key: string;
  ok: boolean;
  label: string;
  message?: string;
}

export interface ContractReadiness {
  ok: boolean;
  checks: ReadinessCheck[];
  contract: ContractRow | null;
  approval: ContractApprovalRow | null;
}

export interface CreateContractBody {
  title?: string;
  amount_vnd?: number;
  notes?: string;
}

export interface PatchContractBody {
  title?: string;
  amount_vnd?: number;
  notes?: string;
}

export interface SubmitContractBody {
  notes?: string;
}

export interface RejectApprovalBody {
  decision_notes?: string;
}
