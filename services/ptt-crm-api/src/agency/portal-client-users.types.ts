export type PortalClientRole = 'viewer' | 'approver';

export interface PortalClientUserPublic {
  id: string;
  email: string;
  role: PortalClientRole;
  active: boolean;
  last_login_at: string | null;
  created_at: string;
  updated_at: string;
}

export interface PortalClientUsersListResponse {
  ok: boolean;
  client_id: string;
  users: PortalClientUserPublic[];
  table_ready: boolean;
}

export interface CreatePortalClientUserBody {
  email: string;
  password?: string;
  role?: PortalClientRole;
}

export interface CreatePortalClientUserResponse {
  ok: boolean;
  user: PortalClientUserPublic;
  /** Present when server generated password (create or reset). Show once to AM for handover. */
  temporary_password?: string;
}

export interface UpdatePortalClientUserBody {
  role?: PortalClientRole;
  active?: boolean;
}

export interface ResetPortalClientUserPasswordBody {
  password?: string;
}

export interface ResetPortalClientUserPasswordResponse {
  ok: boolean;
  temporary_password?: string;
}
