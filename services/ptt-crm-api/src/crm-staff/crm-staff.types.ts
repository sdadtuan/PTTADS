export interface CrmStaffRow {
  id: number;
  name: string;
  phone: string;
  email: string;
  job_title: string;
  department: string;
  internal_code: string;
  active: number;
  notes: string;
  sort_order: number;
  department_id: number | null;
  position_id: number | null;
  reports_to_id: number | null;
  employment_type: string;
  started_on: string;
  ended_on: string;
  created: string;
  updated_at: string;
  pipeline_case_count: number;
  dept_code: string;
  dept_name: string;
  reports_to_name: string;
  position_catalog_name: string;
  position_catalog_code: string;
  has_login?: boolean;
}

export interface CrmStaffSummaryMeta {
  staff_total: number;
  staff_active: number;
  staff_inactive: number;
  open_assigned_cases: number;
}

export interface PatchCrmStaffBody {
  name?: string;
  phone?: string;
  email?: string;
  job_title?: string;
}

export interface StaffImportRow {
  name: string;
  phone?: string;
  email?: string;
  internal_code?: string;
  job_title?: string;
}

export interface StaffImportBody {
  rows: StaffImportRow[];
}

export interface StaffLevelsPutBody {
  staff_levels: Array<Record<string, unknown>>;
}

export interface StaffCompetencyPutBody {
  competency?: Record<string, unknown>;
}

export interface CrmStaffWorkspaceCase {
  id: number;
  title: string;
  pipeline_stage: string;
  deal_value_vnd: number;
  status: string;
  assigned_staff_id: number | null;
  customer_id: number | null;
  customer_name: string;
  staff_name: string;
  created_at: string;
  updated_at: string;
  priority: string;
}

export interface CrmStaffWorkspaceResponse {
  staff: Record<string, unknown>;
  stats: {
    total_assigned: number;
    open: number;
    high_priority: number;
    sla_overdue: number;
    new_today: number;
    no_care_report: number;
  };
  cases: CrmStaffWorkspaceCase[];
}

const EMAIL_RE = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;

export function isValidEmail(email: string): boolean {
  if (!email) return true;
  return EMAIL_RE.test(email);
}

export function staffRowForApi(row: Record<string, unknown>): CrmStaffRow {
  const loginEnabled = Number(row.login_enabled ?? 0);
  const loginUsername = String(row.login_username ?? '').trim();
  return {
    id: Number(row.id),
    name: String(row.name ?? ''),
    phone: String(row.phone ?? ''),
    email: String(row.email ?? ''),
    job_title: String(row.job_title ?? ''),
    department: String(row.department ?? ''),
    internal_code: String(row.internal_code ?? ''),
    active: Number(row.active ?? 0),
    notes: String(row.notes ?? ''),
    sort_order: Number(row.sort_order ?? 0),
    department_id: row.department_id != null ? Number(row.department_id) : null,
    position_id: row.position_id != null ? Number(row.position_id) : null,
    reports_to_id: row.reports_to_id != null ? Number(row.reports_to_id) : null,
    employment_type: String(row.employment_type ?? ''),
    started_on: String(row.started_on ?? ''),
    ended_on: String(row.ended_on ?? ''),
    created: String(row.created ?? row.created_at ?? ''),
    updated_at: String(row.updated_at ?? ''),
    pipeline_case_count: Number(row.pipeline_case_count ?? 0),
    dept_code: String(row.dept_code ?? ''),
    dept_name: String(row.dept_name ?? ''),
    reports_to_name: String(row.reports_to_name ?? ''),
    position_catalog_name: String(row.position_catalog_name ?? ''),
    position_catalog_code: String(row.position_catalog_code ?? ''),
    has_login: loginEnabled === 1 && loginUsername.length > 0,
  };
}
