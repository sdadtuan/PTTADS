export const OFFBOARD_REASONS = [
  'contract_ended',
  'churn',
  'compliance',
  'other',
] as const;

export type OffboardReason = (typeof OFFBOARD_REASONS)[number];

export interface OffboardClientBody {
  reason?: string;
  note?: string;
  archive_data?: boolean;
}

export interface OffboardAuditRow {
  id: string;
  client_id: string;
  initiated_by: string;
  reason: string;
  note: string | null;
  tokens_revoked: number;
  portal_users_deactivated: number;
  previous_status: string | null;
  created_at: string;
}

export interface OffboardClientResponse {
  ok: boolean;
  client_id: string;
  status: string;
  tenant_locked: boolean;
  tokens_revoked: number;
  portal_users_deactivated: number;
  event_id: string | null;
  audit_id: string;
  idempotent?: boolean;
}

export interface OffboardAuditListResponse {
  ok: boolean;
  client_id: string;
  rows: OffboardAuditRow[];
}
